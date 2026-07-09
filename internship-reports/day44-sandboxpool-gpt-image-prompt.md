Generate a polished 16:9 technical architecture infographic for an open-source proposal review report.

Theme: AgentCube SandboxPool Architecture.

Use a clean cloud-native / Kubernetes control-plane visual style: light background, crisp boxes, subtle grid, professional colors, clear arrows, no decorative blobs, no cartoon style.

The image must show this architecture:

Title text:
AgentCube SandboxPool Architecture

Subtitle text:
Slow Resource Track / K8s-native Capacity Control Plane

Left section title:
Global Policy Layer

Left section components:
- K8s API Server / etcd
- SandboxPoolClass
- SandboxPool Controller
- per-node SandboxPool

Right section title:
Node Execution Layer

Right section components:
- placeholder-agent
- Static Pod / mirror Pod
- kubelet + RuntimeClass
- node-ctl
- actual sandboxes

Important arrows:
- Operator creates SandboxPoolClass
- Controller creates per-node SandboxPool
- placeholder-agent watches SandboxPool
- placeholder-agent writes Static Pod manifest
- kubelet creates mirror Pod
- RuntimeClass routes CRI calls to placeholder-agent
- placeholder-agent applies resource policy to node-ctl
- node-ctl manages actual sandboxes
- status conditions return to SandboxPool and Controller computes Phase

Bottom strip title:
Review Focus

Bottom strip items:
Static Pod accounting
InPlace resize
stale heartbeat
endpoint source of truth

Design constraints:
- Keep the text readable and not too small.
- Use English labels exactly as listed above where possible.
- Use a balanced left-to-right layout with two main swimlanes.
- Make it look like a report-ready architecture diagram, not a marketing poster.
- Do not add unrelated logos.
