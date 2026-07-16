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
	"encoding/json"
	"net/http"
	"net/http/httptest"
	"testing"

	"github.com/stretchr/testify/assert"
	"github.com/stretchr/testify/require"
	corev1 "k8s.io/api/core/v1"
	metav1 "k8s.io/apimachinery/pkg/apis/meta/v1"
	"k8s.io/client-go/kubernetes"
	"k8s.io/client-go/rest"
)

func createTestPod(name, namespace string, phase corev1.PodPhase, podIP string) *corev1.Pod {
	return &corev1.Pod{
		TypeMeta: metav1.TypeMeta{APIVersion: "v1", Kind: "Pod"},
		ObjectMeta: metav1.ObjectMeta{
			Name:      name,
			Namespace: namespace,
		},
		Status: corev1.PodStatus{
			Phase: phase,
			PodIP: podIP,
		},
	}
}

func newK8sClientForPod(t *testing.T, podName string, pod *corev1.Pod) *K8sClient {
	t.Helper()
	expectedPath := "/api/v1/namespaces/test-namespace/pods/" + podName
	apiServer := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		if r.Method != http.MethodGet || r.URL.Path != expectedPath {
			http.NotFound(w, r)
			return
		}
		if pod == nil {
			http.NotFound(w, r)
			return
		}
		w.Header().Set("Content-Type", "application/json")
		if err := json.NewEncoder(w).Encode(pod); err != nil {
			t.Errorf("encode pod response: %v", err)
		}
	}))
	t.Cleanup(apiServer.Close)

	clientset, err := kubernetes.NewForConfig(&rest.Config{Host: apiServer.URL})
	require.NoError(t, err)
	return &K8sClient{clientset: clientset}
}

func TestGetSandboxPodIPFallsBackToSandboxName(t *testing.T) {
	pod := createTestPod("test-sandbox", "test-namespace", corev1.PodRunning, "10.0.0.1")
	client := newK8sClientForPod(t, "test-sandbox", pod)

	ip, err := client.GetSandboxPodIP(context.Background(), "test-namespace", "test-sandbox", "")

	assert.NoError(t, err)
	assert.Equal(t, "10.0.0.1", ip)
}

func TestGetSandboxPodIPReadsNamedPodFromLiveAPI(t *testing.T) {
	pod := createTestPod("warm-pool-pod", "test-namespace", corev1.PodRunning, "10.0.0.2")
	client := newK8sClientForPod(t, "warm-pool-pod", pod)

	ip, err := client.GetSandboxPodIP(context.Background(), "test-namespace", "warm-pool-sandbox", "warm-pool-pod")

	assert.NoError(t, err)
	assert.Equal(t, "10.0.0.2", ip)
}

func TestGetSandboxPodIP_PodNotFound(t *testing.T) {
	client := newK8sClientForPod(t, "test-sandbox", nil)

	ip, err := client.GetSandboxPodIP(context.Background(), "test-namespace", "test-sandbox", "")

	assert.Error(t, err)
	assert.Empty(t, ip)
	assert.Contains(t, err.Error(), "failed to get sandbox pod test-namespace/test-sandbox")
}

func TestGetSandboxPodIP_InvalidPodStatus(t *testing.T) {
	testCases := []struct {
		name   string
		phase  corev1.PodPhase
		podIP  string
		errMsg string
	}{
		{
			name:   "pod not running",
			phase:  corev1.PodPending,
			podIP:  "10.0.0.1",
			errMsg: "pod not running yet",
		},
		{
			name:   "pod without IP",
			phase:  corev1.PodRunning,
			podIP:  "",
			errMsg: "pod IP not assigned yet",
		},
	}

	for _, tc := range testCases {
		t.Run(tc.name, func(t *testing.T) {
			pod := createTestPod("test-sandbox", "test-namespace", tc.phase, tc.podIP)
			client := newK8sClientForPod(t, "test-sandbox", pod)

			ip, err := client.GetSandboxPodIP(context.Background(), "test-namespace", "test-sandbox", "")

			assert.Error(t, err)
			assert.Empty(t, ip)
			assert.Contains(t, err.Error(), tc.errMsg, "Error message should indicate the issue")
		})
	}
}
