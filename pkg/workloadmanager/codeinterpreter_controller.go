/*
Copyright The Volcano Authors.

Licensed under the Apache License, Version 2.0 (the "License");
you may not use this file except in compliance with the License.
You may obtain a copy of the License at

    http://www.apache.org/licenses/LICENSE-2.0

Unless required by applicable law or agreed to in writing, software
distributed under the License is distributed on an "AS IS" BASIS,
WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
See the License for the specific language governing permissions and
limitations under the License.
*/

package workloadmanager

import (
	"context"
	"fmt"
	"reflect"
	"time"

	corev1 "k8s.io/api/core/v1"
	"k8s.io/apimachinery/pkg/api/errors"
	apimeta "k8s.io/apimachinery/pkg/api/meta"
	metav1 "k8s.io/apimachinery/pkg/apis/meta/v1"
	"k8s.io/apimachinery/pkg/runtime"
	"k8s.io/apimachinery/pkg/types"
	ctrl "sigs.k8s.io/controller-runtime"
	"sigs.k8s.io/controller-runtime/pkg/builder"
	"sigs.k8s.io/controller-runtime/pkg/client"
	"sigs.k8s.io/controller-runtime/pkg/controller/controllerutil"
	"sigs.k8s.io/controller-runtime/pkg/log"
	"sigs.k8s.io/controller-runtime/pkg/predicate"

	runtimev1alpha1 "github.com/volcano-sh/agentcube/pkg/apis/runtime/v1alpha1"
	"github.com/volcano-sh/agentcube/pkg/workloadmanager/agentsandbox"
)

// CodeInterpreterReconciler reconciles a CodeInterpreter object
type CodeInterpreterReconciler struct {
	client.Client
	Scheme *runtime.Scheme
}

// Reconcile is part of the main kubernetes reconciliation loop which aims to
// move the current state of the cluster closer to the desired state.
func (r *CodeInterpreterReconciler) Reconcile(ctx context.Context, req ctrl.Request) (ctrl.Result, error) {
	logger := log.FromContext(ctx)

	codeInterpreter := &runtimev1alpha1.CodeInterpreter{}
	if err := r.Get(ctx, req.NamespacedName, codeInterpreter); err != nil {
		if errors.IsNotFound(err) {
			return ctrl.Result{}, nil
		}
		return ctrl.Result{}, err
	}

	// Manage SandboxTemplate and SandboxWarmPool if configured
	if codeInterpreter.Spec.WarmPoolSize != nil && *codeInterpreter.Spec.WarmPoolSize > 0 {
		// Ensure SandboxTemplate exists (required for SandboxWarmPool)
		result, err := r.ensureSandboxTemplate(ctx, codeInterpreter)
		if err != nil {
			logger.Error(err, "failed to ensure SandboxTemplate")
			return ctrl.Result{}, err
		}
		if result.RequeueAfter > 0 {
			return result, nil
		}
		// Ensure SandboxWarmPool exists
		if err := r.ensureSandboxWarmPool(ctx, codeInterpreter); err != nil {
			logger.Error(err, "failed to ensure SandboxWarmPool")
			return ctrl.Result{}, err
		}
	} else {
		// Delete SandboxWarmPool if WarmPoolSize is 0 or nil
		if err := r.deleteSandboxWarmPool(ctx, codeInterpreter); err != nil {
			logger.Error(err, "failed to delete SandboxWarmPool")
			return ctrl.Result{}, err
		}
		// Delete SandboxTemplate if WarmPoolSize is 0 or nil
		if err := r.deleteSandboxTemplate(ctx, codeInterpreter); err != nil {
			logger.Error(err, "failed to delete SandboxTemplate")
			return ctrl.Result{}, err
		}
	}

	// Update status with ready condition
	if err := r.updateStatus(ctx, codeInterpreter); err != nil {
		logger.Error(err, "failed to update status")
		return ctrl.Result{}, err
	}

	return ctrl.Result{}, nil
}

// updateStatus updates the CodeInterpreter status. It skips the API write
// when the status is already up-to-date to avoid triggering a new watch event
// that would re-enqueue the object unnecessarily.
func (r *CodeInterpreterReconciler) updateStatus(ctx context.Context, ci *runtimev1alpha1.CodeInterpreter) error {
	existing := apimeta.FindStatusCondition(ci.Status.Conditions, "Ready")
	if ci.Status.Ready &&
		existing != nil &&
		existing.Status == metav1.ConditionTrue &&
		existing.ObservedGeneration == ci.Generation {
		return nil
	}

	ci.Status.Ready = true
	// SetStatusCondition only updates LastTransitionTime when the condition
	// Status actually changes, preventing spurious status writes that would
	// trigger an infinite reconciliation loop.
	apimeta.SetStatusCondition(&ci.Status.Conditions, metav1.Condition{
		Type:               "Ready",
		Status:             metav1.ConditionTrue,
		Reason:             "Reconciled",
		Message:            "CodeInterpreter is ready",
		ObservedGeneration: ci.Generation,
	})

	return r.Status().Update(ctx, ci)
}

// ensureSandboxTemplate ensures that a SandboxTemplate exists for this CodeInterpreter
func (r *CodeInterpreterReconciler) ensureSandboxTemplate(ctx context.Context, ci *runtimev1alpha1.CodeInterpreter) (ctrl.Result, error) {
	logger := log.FromContext(ctx)

	// Check if public key is cached before creating SandboxTemplate that requires it
	// Skip this check if authMode is "none" (custom images that don't use PicoD auth)
	if ci.Spec.AuthMode != runtimev1alpha1.AuthModeNone && !IsPublicKeyCached() {
		logger.Info("waiting for public key to be cached from Router Secret; ensure Router has started and created the identity Secret")
		return ctrl.Result{RequeueAfter: 5 * time.Second}, nil
	}

	template := ci.Spec.Template
	if template == nil {
		return ctrl.Result{}, fmt.Errorf("template is required")
	}

	templateName := ci.Name
	sandboxTemplate := agentsandbox.NewSandboxTemplateObject()
	err := r.Get(ctx, types.NamespacedName{Name: templateName, Namespace: ci.Namespace}, sandboxTemplate)

	// Convert CodeInterpreterSandboxTemplate to PodTemplate
	podSpec := r.convertToPodSpec(template, ci)

	if errors.IsNotFound(err) {
		// Create new SandboxTemplate
		sandboxTemplate = agentsandbox.NewSandboxTemplate(ci.Namespace, templateName, podSpec)

		// Set owner reference
		if err := controllerutil.SetControllerReference(ci, sandboxTemplate, r.Scheme); err != nil {
			return ctrl.Result{}, fmt.Errorf("failed to set controller reference: %w", err)
		}

		if err := r.Create(ctx, sandboxTemplate); err != nil {
			if !errors.IsAlreadyExists(err) {
				return ctrl.Result{}, fmt.Errorf("failed to create SandboxTemplate: %w", err)
			}
		}
		return ctrl.Result{}, nil
	} else if err != nil {
		return ctrl.Result{}, fmt.Errorf("failed to get SandboxTemplate: %w", err)
	}

	// Update existing SandboxTemplate if needed
	if existingPodSpec, ok := agentsandbox.SandboxTemplatePodSpec(sandboxTemplate); !ok {
		return ctrl.Result{}, fmt.Errorf("unexpected SandboxTemplate object type %T", sandboxTemplate)
	} else if !r.podTemplateEqual(existingPodSpec, podSpec) {
		if ok := agentsandbox.SetSandboxTemplatePodSpec(sandboxTemplate, podSpec); !ok {
			return ctrl.Result{}, fmt.Errorf("unexpected SandboxTemplate object type %T", sandboxTemplate)
		}
		if err := r.Update(ctx, sandboxTemplate); err != nil {
			return ctrl.Result{}, fmt.Errorf("failed to update SandboxTemplate: %w", err)
		}
	}

	return ctrl.Result{}, nil
}

// ensureSandboxWarmPool ensures that a SandboxWarmPool exists for this CodeInterpreter
func (r *CodeInterpreterReconciler) ensureSandboxWarmPool(ctx context.Context, ci *runtimev1alpha1.CodeInterpreter) error {
	if ci.Spec.WarmPoolSize == nil || *ci.Spec.WarmPoolSize == 0 {
		return nil
	}

	templateName := ci.Name
	warmPoolName := ci.Name
	warmPool := agentsandbox.NewSandboxWarmPoolObject()
	err := r.Get(ctx, types.NamespacedName{Name: warmPoolName, Namespace: ci.Namespace}, warmPool)

	if errors.IsNotFound(err) {
		// Create new SandboxWarmPool
		warmPool = agentsandbox.NewSandboxWarmPool(ci.Namespace, warmPoolName, templateName, *ci.Spec.WarmPoolSize)

		// Set owner reference
		if err := controllerutil.SetControllerReference(ci, warmPool, r.Scheme); err != nil {
			return fmt.Errorf("failed to set controller reference: %w", err)
		}

		if err := r.Create(ctx, warmPool); err != nil {
			if !errors.IsAlreadyExists(err) {
				return fmt.Errorf("failed to create SandboxWarmPool: %w", err)
			}
		}
		return nil
	} else if err != nil {
		return fmt.Errorf("failed to get SandboxWarmPool: %w", err)
	}

	// Update existing SandboxWarmPool if needed
	needsUpdate := false
	replicas, currentTemplateName, ok := agentsandbox.SandboxWarmPoolSpec(warmPool)
	if !ok {
		return fmt.Errorf("unexpected SandboxWarmPool object type %T", warmPool)
	}
	if replicas != *ci.Spec.WarmPoolSize {
		replicas = *ci.Spec.WarmPoolSize
		needsUpdate = true
	}
	if currentTemplateName != templateName {
		currentTemplateName = templateName
		needsUpdate = true
	}

	if needsUpdate {
		if ok := agentsandbox.SetSandboxWarmPoolSpec(warmPool, replicas, currentTemplateName); !ok {
			return fmt.Errorf("unexpected SandboxWarmPool object type %T", warmPool)
		}
		if err := r.Update(ctx, warmPool); err != nil {
			return fmt.Errorf("failed to update SandboxWarmPool: %w", err)
		}
	}

	return nil
}

// deleteSandboxWarmPool deletes the SandboxWarmPool if it exists
func (r *CodeInterpreterReconciler) deleteSandboxWarmPool(ctx context.Context, ci *runtimev1alpha1.CodeInterpreter) error {
	warmPoolName := ci.Name
	warmPool := agentsandbox.NewSandboxWarmPoolObject()
	err := r.Get(ctx, types.NamespacedName{Name: warmPoolName, Namespace: ci.Namespace}, warmPool)
	if errors.IsNotFound(err) {
		return nil
	} else if err != nil {
		return fmt.Errorf("failed to get SandboxWarmPool: %w", err)
	}

	if err := r.Delete(ctx, warmPool); err != nil {
		if !errors.IsNotFound(err) {
			return fmt.Errorf("failed to delete SandboxWarmPool: %w", err)
		}
	}

	return nil
}

// deleteSandboxTemplate deletes the SandboxTemplate if it exists
func (r *CodeInterpreterReconciler) deleteSandboxTemplate(ctx context.Context, ci *runtimev1alpha1.CodeInterpreter) error {
	templateName := ci.Name
	sandboxTemplate := agentsandbox.NewSandboxTemplateObject()
	err := r.Get(ctx, types.NamespacedName{Name: templateName, Namespace: ci.Namespace}, sandboxTemplate)
	if errors.IsNotFound(err) {
		return nil
	} else if err != nil {
		return fmt.Errorf("failed to get SandboxTemplate: %w", err)
	}

	if err := r.Delete(ctx, sandboxTemplate); err != nil {
		if !errors.IsNotFound(err) {
			return fmt.Errorf("failed to delete SandboxTemplate: %w", err)
		}
	}

	return nil
}

// convertToPodSpec converts CodeInterpreterSandboxTemplate to the pod spec used by agent-sandbox.
func (r *CodeInterpreterReconciler) convertToPodSpec(template *runtimev1alpha1.CodeInterpreterSandboxTemplate, ci *runtimev1alpha1.CodeInterpreter) corev1.PodSpec {
	// Normalize RuntimeClassName: if it's an empty string, set it to nil
	runtimeClassName := template.RuntimeClassName
	if runtimeClassName != nil && *runtimeClassName == "" {
		runtimeClassName = nil
	}

	// Build environment variables - create a copy to avoid mutating the cached object
	envVars := make([]corev1.EnvVar, len(template.Environment))
	copy(envVars, template.Environment)
	// Only inject public key for picod auth mode (default behavior)
	if ci.Spec.AuthMode != runtimev1alpha1.AuthModeNone {
		envVars = append(envVars, corev1.EnvVar{
			Name:  "PICOD_AUTH_PUBLIC_KEY",
			Value: GetCachedPublicKey(),
		})
	}

	// Build pod spec
	podSpec := corev1.PodSpec{
		ImagePullSecrets: template.ImagePullSecrets,
		Containers: []corev1.Container{
			{
				Name:            "codeinterpreter",
				Image:           template.Image,
				ImagePullPolicy: template.ImagePullPolicy,
				Command:         template.Command,
				Args:            template.Args,
				Env:             envVars,
				Resources:       template.Resources,
			},
		},
		RuntimeClassName: runtimeClassName,
	}

	return podSpec
}

// podTemplateEqual checks if two PodTemplates are equal
func (r *CodeInterpreterReconciler) podTemplateEqual(a, b corev1.PodSpec) bool {
	// Use reflect.DeepEqual for a comprehensive comparison.
	return reflect.DeepEqual(a, b)
}

// SetupWithManager sets up the controller with the Manager.
// GenerationChangedPredicate filters out status-only update events so that
// the controller is not re-enqueued by its own status writes.
func (r *CodeInterpreterReconciler) SetupWithManager(mgr ctrl.Manager) error {
	return ctrl.NewControllerManagedBy(mgr).
		For(&runtimev1alpha1.CodeInterpreter{}, builder.WithPredicates(predicate.GenerationChangedPredicate{})).
		Complete(r)
}
