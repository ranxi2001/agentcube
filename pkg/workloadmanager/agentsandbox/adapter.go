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

// Package agentsandbox isolates AgentCube from agent-sandbox API shape changes.
package agentsandbox

import (
	"fmt"

	corev1 "k8s.io/api/core/v1"
	metav1 "k8s.io/apimachinery/pkg/apis/meta/v1"
	"k8s.io/apimachinery/pkg/runtime"
	"k8s.io/apimachinery/pkg/runtime/schema"
	"sigs.k8s.io/controller-runtime/pkg/client"

	"github.com/volcano-sh/agentcube/pkg/common/types"
	sandboxv1alpha1 "sigs.k8s.io/agent-sandbox/api/v1alpha1"
	sandboxv1beta1 "sigs.k8s.io/agent-sandbox/api/v1beta1"
	extensionsv1alpha1 "sigs.k8s.io/agent-sandbox/extensions/api/v1alpha1"
	extensionsv1beta1 "sigs.k8s.io/agent-sandbox/extensions/api/v1beta1"
)

var (
	SandboxGVR = schema.GroupVersionResource{
		Group:    "agents.x-k8s.io",
		Version:  "v1beta1",
		Resource: "sandboxes",
	}
	SandboxClaimGVR = schema.GroupVersionResource{
		Group:    "extensions.agents.x-k8s.io",
		Version:  "v1beta1",
		Resource: "sandboxclaims",
	}
)

const (
	statusReady    = "ready"
	statusNotReady = "not-ready"
)

type Object interface {
	runtime.Object
	metav1.Object
}

type SandboxParams struct {
	Namespace      string
	Name           string
	ShutdownTime   metav1.Time
	PodSpec        corev1.PodSpec
	PodLabels      map[string]string
	PodAnnotations map[string]string
	Labels         map[string]string
	Annotations    map[string]string
}

type SandboxClaimParams struct {
	Namespace      string
	Name           string
	WarmPoolName   string
	Labels         map[string]string
	Annotations    map[string]string
	OwnerReference *metav1.OwnerReference
}

func AddToScheme(scheme *runtime.Scheme) error {
	if err := sandboxv1alpha1.AddToScheme(scheme); err != nil {
		return fmt.Errorf("add agent-sandbox v1alpha1 core scheme: %w", err)
	}
	if err := extensionsv1alpha1.AddToScheme(scheme); err != nil {
		return fmt.Errorf("add agent-sandbox v1alpha1 extensions scheme: %w", err)
	}
	if err := sandboxv1beta1.AddToScheme(scheme); err != nil {
		return fmt.Errorf("add agent-sandbox v1beta1 core scheme: %w", err)
	}
	if err := extensionsv1beta1.AddToScheme(scheme); err != nil {
		return fmt.Errorf("add agent-sandbox v1beta1 extensions scheme: %w", err)
	}
	return nil
}

func NewSandboxObject() client.Object {
	return &sandboxv1beta1.Sandbox{}
}

func NewSandboxClaimObject() client.Object {
	return &extensionsv1beta1.SandboxClaim{}
}

func NewSandboxTemplateObject() client.Object {
	return &extensionsv1beta1.SandboxTemplate{}
}

func NewSandboxWarmPoolObject() client.Object {
	return &extensionsv1beta1.SandboxWarmPool{}
}

func NewSandbox(params SandboxParams) Object {
	return &sandboxv1beta1.Sandbox{
		TypeMeta: metav1.TypeMeta{
			APIVersion: sandboxv1beta1.GroupVersion.String(),
			Kind:       types.SandboxKind,
		},
		ObjectMeta: metav1.ObjectMeta{
			Name:        params.Name,
			Namespace:   params.Namespace,
			Labels:      params.Labels,
			Annotations: params.Annotations,
		},
		Spec: sandboxv1beta1.SandboxSpec{
			PodTemplate: sandboxv1beta1.PodTemplate{
				Spec: params.PodSpec,
				ObjectMeta: sandboxv1beta1.PodMetadata{
					Labels:      params.PodLabels,
					Annotations: params.PodAnnotations,
				},
			},
			Lifecycle: sandboxv1beta1.Lifecycle{
				ShutdownTime: &params.ShutdownTime,
			},
			OperatingMode: sandboxv1beta1.SandboxOperatingModeRunning,
		},
	}
}

func NewSandboxClaim(params SandboxClaimParams) Object {
	claim := &extensionsv1beta1.SandboxClaim{
		TypeMeta: metav1.TypeMeta{
			APIVersion: extensionsv1beta1.GroupVersion.String(),
			Kind:       types.SandboxClaimsKind,
		},
		ObjectMeta: metav1.ObjectMeta{
			Name:        params.Name,
			Namespace:   params.Namespace,
			Labels:      params.Labels,
			Annotations: params.Annotations,
		},
		Spec: extensionsv1beta1.SandboxClaimSpec{
			WarmPoolRef: extensionsv1beta1.SandboxWarmPoolRef{
				Name: params.WarmPoolName,
			},
		},
	}
	if params.OwnerReference != nil {
		claim.ObjectMeta.OwnerReferences = []metav1.OwnerReference{*params.OwnerReference}
	}
	return claim
}

func NewSandboxTemplate(namespace, name string, podSpec corev1.PodSpec) client.Object {
	return &extensionsv1beta1.SandboxTemplate{
		ObjectMeta: metav1.ObjectMeta{
			Name:      name,
			Namespace: namespace,
		},
		Spec: extensionsv1beta1.SandboxTemplateSpec{
			PodTemplate: sandboxv1beta1.PodTemplate{
				Spec: podSpec,
			},
			NetworkPolicyManagement: extensionsv1beta1.NetworkPolicyManagementUnmanaged,
		},
	}
}

func NewSandboxWarmPool(namespace, name, templateName string, replicas int32) client.Object {
	return &extensionsv1beta1.SandboxWarmPool{
		ObjectMeta: metav1.ObjectMeta{
			Name:      name,
			Namespace: namespace,
		},
		Spec: extensionsv1beta1.SandboxWarmPoolSpec{
			Replicas: replicas,
			TemplateRef: extensionsv1beta1.SandboxTemplateRef{
				Name: templateName,
			},
		},
	}
}

func SandboxPodName(sandbox Object) string {
	if sandbox == nil {
		return ""
	}
	if value := sandbox.GetAnnotations()[sandboxv1beta1.SandboxPodNameAnnotation]; value != "" {
		return value
	}
	return sandbox.GetAnnotations()[sandboxv1alpha1.SandboxPodNameAnnotation]
}

func SandboxShutdownTime(sandbox Object) *metav1.Time {
	if sandbox == nil {
		return nil
	}
	if typed, ok := sandbox.(*sandboxv1beta1.Sandbox); ok {
		return typed.Spec.Lifecycle.ShutdownTime
	}
	if typed, ok := sandbox.(*sandboxv1alpha1.Sandbox); ok {
		return typed.Spec.Lifecycle.ShutdownTime
	}
	return nil
}

func SandboxPodSpec(sandbox Object) (corev1.PodSpec, bool) {
	if typed, ok := sandbox.(*sandboxv1beta1.Sandbox); ok {
		return typed.Spec.PodTemplate.Spec, true
	}
	if typed, ok := sandbox.(*sandboxv1alpha1.Sandbox); ok {
		return typed.Spec.PodTemplate.Spec, true
	}
	return corev1.PodSpec{}, false
}

func SandboxPodLabels(sandbox Object) map[string]string {
	if typed, ok := sandbox.(*sandboxv1beta1.Sandbox); ok {
		return typed.Spec.PodTemplate.ObjectMeta.Labels
	}
	if typed, ok := sandbox.(*sandboxv1alpha1.Sandbox); ok {
		return typed.Spec.PodTemplate.ObjectMeta.Labels
	}
	return nil
}

func SandboxPodAnnotations(sandbox Object) map[string]string {
	if typed, ok := sandbox.(*sandboxv1beta1.Sandbox); ok {
		return typed.Spec.PodTemplate.ObjectMeta.Annotations
	}
	if typed, ok := sandbox.(*sandboxv1alpha1.Sandbox); ok {
		return typed.Spec.PodTemplate.ObjectMeta.Annotations
	}
	return nil
}

func SandboxStatus(sandbox Object) string {
	if sandbox == nil {
		return statusNotReady
	}
	typed, ok := sandbox.(*sandboxv1beta1.Sandbox)
	if ok {
		for _, condition := range typed.Status.Conditions {
			if condition.Type == string(sandboxv1beta1.SandboxConditionReady) && condition.Status == metav1.ConditionTrue {
				return statusReady
			}
		}
	}
	if typed, ok := sandbox.(*sandboxv1alpha1.Sandbox); ok {
		for _, condition := range typed.Status.Conditions {
			if condition.Type == string(sandboxv1alpha1.SandboxConditionReady) && condition.Status == metav1.ConditionTrue {
				return statusReady
			}
		}
	}
	return statusNotReady
}

func SandboxClaimWarmPoolName(claim Object) string {
	typed, ok := claim.(*extensionsv1beta1.SandboxClaim)
	if !ok {
		if typed, ok := claim.(*extensionsv1alpha1.SandboxClaim); ok {
			return typed.Spec.TemplateRef.Name
		}
		return ""
	}
	return typed.Spec.WarmPoolRef.Name
}

func SandboxClaimSandboxName(claim Object) string {
	if typed, ok := claim.(*extensionsv1beta1.SandboxClaim); ok {
		return typed.Status.SandboxStatus.Name
	}
	if typed, ok := claim.(*extensionsv1alpha1.SandboxClaim); ok {
		return typed.Status.SandboxStatus.Name
	}
	return ""
}

func SandboxClaimPodIPs(claim Object) []string {
	if typed, ok := claim.(*extensionsv1beta1.SandboxClaim); ok {
		return typed.Status.SandboxStatus.PodIPs
	}
	if typed, ok := claim.(*extensionsv1alpha1.SandboxClaim); ok {
		return typed.Status.SandboxStatus.PodIPs
	}
	return nil
}

func SandboxClaimReady(claim Object) bool {
	if typed, ok := claim.(*extensionsv1beta1.SandboxClaim); ok {
		for _, condition := range typed.Status.Conditions {
			if condition.Type == string(sandboxv1beta1.SandboxConditionReady) && condition.Status == metav1.ConditionTrue {
				return true
			}
		}
		return false
	}
	if typed, ok := claim.(*extensionsv1alpha1.SandboxClaim); ok {
		for _, condition := range typed.Status.Conditions {
			if condition.Type == string(sandboxv1alpha1.SandboxConditionReady) && condition.Status == metav1.ConditionTrue {
				return true
			}
		}
	}
	return false
}

func SandboxTemplatePodSpec(obj client.Object) (corev1.PodSpec, bool) {
	typed, ok := obj.(*extensionsv1beta1.SandboxTemplate)
	if !ok {
		return corev1.PodSpec{}, false
	}
	return typed.Spec.PodTemplate.Spec, true
}

func SetSandboxTemplatePodSpec(obj client.Object, podSpec corev1.PodSpec) bool {
	typed, ok := obj.(*extensionsv1beta1.SandboxTemplate)
	if !ok {
		return false
	}
	typed.Spec.PodTemplate.Spec = podSpec
	typed.Spec.NetworkPolicyManagement = extensionsv1beta1.NetworkPolicyManagementUnmanaged
	return true
}

func SandboxWarmPoolSpec(obj client.Object) (replicas int32, templateName string, ok bool) {
	typed, ok := obj.(*extensionsv1beta1.SandboxWarmPool)
	if !ok {
		return 0, "", false
	}
	return typed.Spec.Replicas, typed.Spec.TemplateRef.Name, true
}

func SetSandboxWarmPoolSpec(obj client.Object, replicas int32, templateName string) bool {
	typed, ok := obj.(*extensionsv1beta1.SandboxWarmPool)
	if !ok {
		return false
	}
	typed.Spec.Replicas = replicas
	typed.Spec.TemplateRef.Name = templateName
	return true
}

func PodTemplateSpec(podSpec corev1.PodSpec) sandboxv1beta1.PodTemplate {
	return sandboxv1beta1.PodTemplate{Spec: podSpec}
}
