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
	"net"
	"strconv"
	"time"

	runtimev1alpha1 "github.com/volcano-sh/agentcube/pkg/apis/runtime/v1alpha1"
	"github.com/volcano-sh/agentcube/pkg/common/types"
	"github.com/volcano-sh/agentcube/pkg/workloadmanager/agentsandbox"
	metav1 "k8s.io/apimachinery/pkg/apis/meta/v1"
)

const (
	defaultSandboxReadyProbeTimeout  = 15 * time.Second
	defaultSandboxReadyProbeInterval = 1 * time.Second
	defaultSandboxReadyDialTimeout   = 1 * time.Second

	sandboxStatusReady    = "ready"
	sandboxStatusNotReady = "not-ready"
)

var sandboxEntrypointDial = func(ctx context.Context, endpoint string, timeout time.Duration) error {
	dialer := &net.Dialer{Timeout: timeout}
	conn, err := dialer.DialContext(ctx, "tcp", endpoint)
	if err != nil {
		return err
	}
	return conn.Close()
}

func buildSandboxPlaceHolder(sandboxCR agentsandbox.Object, entry *sandboxEntry) *types.SandboxInfo {
	var expiresAt time.Time
	if shutdownTime := agentsandbox.SandboxShutdownTime(sandboxCR); shutdownTime != nil {
		expiresAt = shutdownTime.Time
	} else {
		expiresAt = time.Now().Add(DefaultSandboxTTL)
	}
	idleTimeout := entry.IdleTimeout
	if idleTimeout == 0 {
		idleTimeout = DefaultSandboxIdleTimeout
	}
	return &types.SandboxInfo{
		Kind:             entry.Kind,
		SessionID:        entry.SessionID,
		OwnerID:          entry.OwnerID,
		SandboxNamespace: sandboxCR.GetNamespace(),
		Name:             sandboxCR.GetName(),
		ExpiresAt:        expiresAt,
		Status:           "creating",
		IdleTimeout:      metav1.Duration{Duration: idleTimeout},
	}
}

func buildSandboxInfo(sandbox agentsandbox.Object, podIP string, entry *sandboxEntry) *types.SandboxInfo {
	createdAt := sandbox.GetCreationTimestamp().Time
	expiresAt := createdAt.Add(DefaultSandboxTTL)
	if shutdownTime := agentsandbox.SandboxShutdownTime(sandbox); shutdownTime != nil {
		expiresAt = shutdownTime.Time
	}
	accesses := make([]types.SandboxEntryPoint, 0, len(entry.Ports))
	for _, port := range entry.Ports {
		accesses = append(accesses, types.SandboxEntryPoint{
			Path:     port.PathPrefix,
			Protocol: string(port.Protocol),
			Endpoint: net.JoinHostPort(podIP, strconv.Itoa(int(port.Port))),
		})
	}
	idleTimeout := entry.IdleTimeout
	if idleTimeout == 0 {
		idleTimeout = DefaultSandboxIdleTimeout
	}
	return &types.SandboxInfo{
		Kind:             entry.Kind,
		SandboxID:        string(sandbox.GetUID()),
		Name:             sandbox.GetName(),
		SandboxNamespace: sandbox.GetNamespace(),
		EntryPoints:      accesses,
		SessionID:        entry.SessionID,
		OwnerID:          entry.OwnerID,
		CreatedAt:        createdAt,
		ExpiresAt:        expiresAt,
		Status:           getSandboxStatus(sandbox),
		IdleTimeout:      metav1.Duration{Duration: idleTimeout},
	}
}

// getSandboxStatus extracts status from Sandbox CRD conditions.
// Returns sandboxStatusReady when the sandbox is ready, sandboxStatusNotReady otherwise.
func getSandboxStatus(sandbox agentsandbox.Object) string {
	if agentsandbox.SandboxStatus(sandbox) == sandboxStatusReady {
		return sandboxStatusReady
	}
	return sandboxStatusNotReady
}

func (s *Server) waitForSandboxEntryPointsReady(ctx context.Context, podIP string, entry *sandboxEntry) error {
	if entry == nil || len(entry.Ports) == 0 {
		return nil
	}

	probeTimeout := defaultSandboxReadyProbeTimeout
	probeInterval := defaultSandboxReadyProbeInterval
	if s != nil && s.config != nil {
		if s.config.SandboxReadyProbeTimeout > 0 {
			probeTimeout = s.config.SandboxReadyProbeTimeout
		}
		if s.config.SandboxReadyProbeInterval > 0 {
			probeInterval = s.config.SandboxReadyProbeInterval
		}
	}

	probeCtx, cancel := context.WithTimeout(ctx, probeTimeout)
	defer cancel()

	var lastErr error
	for {
		lastErr = probeSandboxEntryPoints(probeCtx, podIP, entry.Ports, probeInterval)
		if lastErr == nil {
			return nil
		}

		select {
		case <-probeCtx.Done():
			return fmt.Errorf("sandbox entrypoints not ready before timeout: %w", lastErr)
		case <-time.After(probeInterval):
		}
	}
}

func probeSandboxEntryPoints(ctx context.Context, podIP string, ports []runtimev1alpha1.TargetPort, probeInterval time.Duration) error {
	dialTimeout := probeInterval
	if dialTimeout <= 0 || dialTimeout > defaultSandboxReadyDialTimeout {
		dialTimeout = defaultSandboxReadyDialTimeout
	}

	for _, port := range ports {
		endpoint := net.JoinHostPort(podIP, strconv.Itoa(int(port.Port)))
		if err := sandboxEntrypointDial(ctx, endpoint, dialTimeout); err != nil {
			return fmt.Errorf("entrypoint %s not reachable: %w", endpoint, err)
		}
	}

	return nil
}
