# ADR 0001: Separation of Control Plane and Runtime Enforcement Plane

## Status
Accepted

## Context
Autonomous AI agents require continuous, low-latency runtime mediation for every tool call, database interaction, and API request. At the same time, security administrators, compliance auditors, and human approvers require user interfaces, policy editors, approval dashboards, and compliance reporting tools. 

Coupling administrative governance workflows, audit indexing, and human approvals into the hot execution path introduces significant latency, availability dependencies, and an unnecessarily large attack surface.

## Decision
We strictly separate the platform into two distinct architectural planes:
1. **Runtime Enforcement Plane**:
   - High-throughput, low-latency, stateless proxy/sidecar and execution broker.
   - Evaluates cached deterministic policies, coordinates atomic rate limits, and proxies external requests.
   - Must operate with sub-millisecond to low-millisecond overhead.
   - Ingress endpoints exposed only to authenticated agent workloads.
2. **Control Plane**:
   - Administrative APIs and Web UI for tenant, project, agent, and policy management.
   - Human approval orchestration hub.
   - Long-term audit indexing, search, and compliance analytics.
   - Operates independently; temporary outages in the control plane UI do not degrade runtime policy enforcement for existing cached policies.

## Consequences
### Positive
- **Fault Isolation**: Control plane downtime (e.g., UI deployment or search cluster maintenance) does not take down the runtime gateway.
- **Independent Scaling**: Runtime proxies scale with agent tool-call traffic; control plane scales with administrative user load.
- **Security Segmentation**: Agent workloads have no network access to control plane management APIs.

### Negative / Trade-offs
- Requires policy distribution and synchronization mechanisms (e.g., policy version hashing, background pub/sub invalidation).
- Adds deployment complexity compared to a monolithic application.
