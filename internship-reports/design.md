AgentCube Architecture Summary
Core Challenges Addressed
Conflict between K8s scheduling granularity and sandbox lifecycle demands
K8s's Pod creation process introduces high latency for sandbox instantiation
Kube-scheduler becomes overwhelmed by short-lived workloads
Native Pod model lacks support for snapshot recovery, pre-warming, and resource pooling
Inability to achieve sub-second startup times or local scheduling
Dual-layer Scheduling Model
First Layer (K8s)
Manages resource pools via SandboxWorkspace CRD
WorkspaceController provisions placeholder Pods for resource reservation
Reserves CPU/memory on nodes and maintains pool capacity
Second Layer (Sandbox System)
SandboxScheduler performs fine-grained scheduling within reserved resources
sandbox-runtime handles lifecycle management and resource isolation
Four-tier Architecture
Layer 1: K8s Foundation Layer
Node management, kube-scheduler, namespace/RBAC isolation
Layer 2: Resource Pool Control Layer
WorkspaceController manages resource reservations
ReservationManager tracks capacity and node distribution
Layer 3: Scheduler Control Layer
SandboxScheduler handles admission, placement, and recycling
Implements advanced policies (snapshot priority, local caching)
Layer 4: Node Data Plane
sandbox-runtime manages execution, snapshots, and resource monitoring
Integrates with network/storage layers
Dual Control Chains
Resource Pool Management Chain
SandboxWorkspace → WorkspaceController → Placeholder Pods
Maintains pool state and rebalances across nodes
Sandbox Lifecycle Chain
Sandbox API/CR → SandboxScheduler → sandbox-runtime
Drives instance creation/deletion and state reporting
Key Objects
SandboxWorkspace: Defines resource pool boundaries, quotas, and policies  
Sandbox: Represents individual sandbox instances with resource requests  
SandboxNodeState: Tracks node capacity (reserved/allocated/free) and runtime health
Core Module Responsibilities
WorkspaceController: Manages pool creation, node selection, and placeholder Pod lifecycle
SandboxScheduler: Executes scheduling decisions based on pool state
NodeAgent/RuntimeAdapter: Bridges control plane with runtime execution
sandbox-runtime: Handles sandbox creation, snapshots, and resource isolation
Critical Workflows
Workspace Creation
User declares pool → Controller selects nodes → Creates placeholder Pods
Pool becomes Ready when placeholder Pods are scheduled
Sandbox Scheduling
User submits request → Scheduler selects node based on pool state
NodeAgent invokes runtime to create sandbox instance
Node State Reporting
NodeAgent periodically collects runtime metrics
Updates SandboxNodeState for scheduler decision-making
This architecture decouples sandbox lifecycle management from K8s, enabling efficient resource pooling and rapid instantiation while maintaining Kubernetes compatibility.
内容由办公领域大模型生成，仅供参考