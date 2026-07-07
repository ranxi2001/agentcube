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

package agentsandbox

import (
	"testing"
	"time"

	corev1 "k8s.io/api/core/v1"
	metav1 "k8s.io/apimachinery/pkg/apis/meta/v1"
	sandboxv1alpha1 "sigs.k8s.io/agent-sandbox/api/v1alpha1"
	sandboxv1beta1 "sigs.k8s.io/agent-sandbox/api/v1beta1"
	extensionsv1alpha1 "sigs.k8s.io/agent-sandbox/extensions/api/v1alpha1"
	extensionsv1beta1 "sigs.k8s.io/agent-sandbox/extensions/api/v1beta1"
)

func TestNewSandboxUsesV1Beta1RunningMode(t *testing.T) {
	shutdownTime := metav1.NewTime(time.Now().Add(time.Hour))
	obj := NewSandbox(SandboxParams{
		Namespace:    "default",
		Name:         "sandbox-1",
		ShutdownTime: shutdownTime,
		PodSpec: corev1.PodSpec{
			Containers: []corev1.Container{{Name: "main", Image: "busybox"}},
		},
		PodLabels:   map[string]string{"session": "s1"},
		Labels:      map[string]string{"managed-by": "agentcube"},
		Annotations: map[string]string{"idle": "15m"},
	})

	sandbox, ok := obj.(*sandboxv1beta1.Sandbox)
	if !ok {
		t.Fatalf("expected v1beta1 Sandbox, got %T", obj)
	}
	if sandbox.APIVersion != sandboxv1beta1.GroupVersion.String() {
		t.Fatalf("expected apiVersion %q, got %q", sandboxv1beta1.GroupVersion.String(), sandbox.APIVersion)
	}
	if sandbox.Spec.OperatingMode != sandboxv1beta1.SandboxOperatingModeRunning {
		t.Fatalf("expected operatingMode Running, got %q", sandbox.Spec.OperatingMode)
	}
	if sandbox.Spec.Lifecycle.ShutdownTime == nil {
		t.Fatal("expected shutdownTime to be set")
	}
	if sandbox.Spec.PodTemplate.ObjectMeta.Labels["session"] != "s1" {
		t.Fatalf("expected pod label to be preserved")
	}
}

func TestNewSandboxClaimUsesWarmPoolRef(t *testing.T) {
	obj := NewSandboxClaim(SandboxClaimParams{
		Namespace:    "default",
		Name:         "claim-1",
		WarmPoolName: "pool-1",
		Labels:       map[string]string{"session": "s1"},
	})

	claim, ok := obj.(*extensionsv1beta1.SandboxClaim)
	if !ok {
		t.Fatalf("expected v1beta1 SandboxClaim, got %T", obj)
	}
	if claim.APIVersion != extensionsv1beta1.GroupVersion.String() {
		t.Fatalf("expected apiVersion %q, got %q", extensionsv1beta1.GroupVersion.String(), claim.APIVersion)
	}
	if claim.Spec.WarmPoolRef.Name != "pool-1" {
		t.Fatalf("expected warmPoolRef pool-1, got %q", claim.Spec.WarmPoolRef.Name)
	}
	if got := SandboxClaimWarmPoolName(claim); got != "pool-1" {
		t.Fatalf("expected helper warm pool pool-1, got %q", got)
	}
}

func TestSandboxClaimStatusHelpers(t *testing.T) {
	v1beta1Claim := &extensionsv1beta1.SandboxClaim{
		Status: extensionsv1beta1.SandboxClaimStatus{
			Conditions: []metav1.Condition{{
				Type:   string(sandboxv1beta1.SandboxConditionReady),
				Status: metav1.ConditionTrue,
			}},
			SandboxStatus: extensionsv1beta1.SandboxStatus{
				Name:   "sandbox-beta",
				PodIPs: []string{"10.0.0.1"},
			},
		},
	}

	if !SandboxClaimReady(v1beta1Claim) {
		t.Fatalf("expected v1beta1 claim to be ready")
	}
	if got := SandboxClaimSandboxName(v1beta1Claim); got != "sandbox-beta" {
		t.Fatalf("expected sandbox-beta, got %q", got)
	}
	if got := SandboxClaimPodIPs(v1beta1Claim); len(got) != 1 || got[0] != "10.0.0.1" {
		t.Fatalf("expected v1beta1 pod IP helper to work, got %#v", got)
	}

	v1alpha1Claim := &extensionsv1alpha1.SandboxClaim{
		Status: extensionsv1alpha1.SandboxClaimStatus{
			Conditions: []metav1.Condition{{
				Type:   string(sandboxv1alpha1.SandboxConditionReady),
				Status: metav1.ConditionTrue,
			}},
			SandboxStatus: extensionsv1alpha1.SandboxStatus{
				Name:   "sandbox-alpha",
				PodIPs: []string{"10.0.0.2"},
			},
		},
	}

	if !SandboxClaimReady(v1alpha1Claim) {
		t.Fatalf("expected v1alpha1 claim to be ready")
	}
	if got := SandboxClaimSandboxName(v1alpha1Claim); got != "sandbox-alpha" {
		t.Fatalf("expected sandbox-alpha, got %q", got)
	}
	if got := SandboxClaimPodIPs(v1alpha1Claim); len(got) != 1 || got[0] != "10.0.0.2" {
		t.Fatalf("expected v1alpha1 pod IP helper to work, got %#v", got)
	}
}

func TestNewSandboxTemplateKeepsNetworkPolicyUnmanaged(t *testing.T) {
	obj := NewSandboxTemplate("default", "template-1", corev1.PodSpec{
		Containers: []corev1.Container{{Name: "main", Image: "busybox"}},
	})

	template, ok := obj.(*extensionsv1beta1.SandboxTemplate)
	if !ok {
		t.Fatalf("expected v1beta1 SandboxTemplate, got %T", obj)
	}
	if template.Spec.NetworkPolicyManagement != extensionsv1beta1.NetworkPolicyManagementUnmanaged {
		t.Fatalf("expected networkPolicyManagement Unmanaged, got %q", template.Spec.NetworkPolicyManagement)
	}
}

func TestReadHelpersSupportV1Alpha1Sandbox(t *testing.T) {
	shutdownTime := metav1.NewTime(time.Now().Add(time.Hour))
	sandbox := &sandboxv1alpha1.Sandbox{
		ObjectMeta: metav1.ObjectMeta{
			Name: "sandbox-1",
			Annotations: map[string]string{
				sandboxv1alpha1.SandboxPodNameAnnotation: "pod-1",
			},
		},
		Spec: sandboxv1alpha1.SandboxSpec{
			Lifecycle: sandboxv1alpha1.Lifecycle{ShutdownTime: &shutdownTime},
			PodTemplate: sandboxv1alpha1.PodTemplate{
				Spec: corev1.PodSpec{
					Containers: []corev1.Container{{Name: "main", Image: "busybox"}},
				},
			},
		},
		Status: sandboxv1alpha1.SandboxStatus{Conditions: []metav1.Condition{{
			Type:   string(sandboxv1alpha1.SandboxConditionReady),
			Status: metav1.ConditionTrue,
		}}},
	}

	if got := SandboxPodName(sandbox); got != "pod-1" {
		t.Fatalf("expected pod-1, got %q", got)
	}
	if got := SandboxShutdownTime(sandbox); got == nil || !got.Equal(&shutdownTime) {
		t.Fatalf("expected shutdownTime helper to read v1alpha1 lifecycle")
	}
	if got := SandboxStatus(sandbox); got != "ready" {
		t.Fatalf("expected ready, got %q", got)
	}
	if podSpec, ok := SandboxPodSpec(sandbox); !ok || podSpec.Containers[0].Image != "busybox" {
		t.Fatalf("expected v1alpha1 pod spec helper to work")
	}
}
