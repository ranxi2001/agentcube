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
	"testing"

	"github.com/stretchr/testify/require"
	"github.com/volcano-sh/agentcube/pkg/workloadmanager/agentsandbox"
	metav1 "k8s.io/apimachinery/pkg/apis/meta/v1"
	"k8s.io/apimachinery/pkg/runtime"
	"k8s.io/apimachinery/pkg/types"
	ctrl "sigs.k8s.io/controller-runtime"
	"sigs.k8s.io/controller-runtime/pkg/client/fake"

	sandboxv1beta1 "sigs.k8s.io/agent-sandbox/api/v1beta1"
	extensionsv1beta1 "sigs.k8s.io/agent-sandbox/extensions/api/v1beta1"
)

func TestSandboxClaimReconcilerNotifiesAdoptedSandbox(t *testing.T) {
	scheme := runtime.NewScheme()
	require.NoError(t, agentsandbox.AddToScheme(scheme))

	claim := &extensionsv1beta1.SandboxClaim{
		ObjectMeta: metav1.ObjectMeta{Name: "claim-1", Namespace: "ns-1"},
		Status: extensionsv1beta1.SandboxClaimStatus{
			Conditions: []metav1.Condition{{
				Type:   string(sandboxv1beta1.SandboxConditionReady),
				Status: metav1.ConditionTrue,
			}},
			SandboxStatus: extensionsv1beta1.SandboxStatus{
				Name: "warm-sandbox-1",
			},
		},
	}
	sandbox := &sandboxv1beta1.Sandbox{
		ObjectMeta: metav1.ObjectMeta{Name: "warm-sandbox-1", Namespace: "ns-1"},
		Status: sandboxv1beta1.SandboxStatus{Conditions: []metav1.Condition{{
			Type:   string(sandboxv1beta1.SandboxConditionReady),
			Status: metav1.ConditionTrue,
		}}},
	}

	reconciler := &SandboxClaimReconciler{
		Client: fake.NewClientBuilder().WithScheme(scheme).WithObjects(claim, sandbox).Build(),
		Scheme: scheme,
	}
	resultChan := reconciler.WatchSandboxClaimOnce(context.Background(), "ns-1", "claim-1")

	result, err := reconciler.Reconcile(context.Background(), ctrl.Request{
		NamespacedName: types.NamespacedName{Namespace: "ns-1", Name: "claim-1"},
	})
	require.NoError(t, err)
	require.Zero(t, result.RequeueAfter)

	select {
	case update := <-resultChan:
		require.Equal(t, "warm-sandbox-1", update.Sandbox.GetName())
	default:
		t.Fatal("expected sandbox claim watcher notification")
	}
}
