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

import "testing"

func TestH2CProtocols(t *testing.T) {
	protocols := h2cProtocols()
	if !protocols.HTTP1() {
		t.Error("HTTP/1 should be enabled")
	}
	if !protocols.UnencryptedHTTP2() {
		t.Error("unencrypted HTTP/2 should be enabled")
	}
	if protocols.HTTP2() {
		t.Error("HTTP/2 over TLS should use the server defaults")
	}
}
