# ADR 0003: Fail-Secure Runtime Mediation Defaults

## Status
Accepted

## Context
In distributed microservice architectures, dependencies periodically experience degradation, network partitions, and outages. When an AI agent attempts to invoke a tool, but a governance platform component (policy database, session store, or audit collector) is unavailable, the system must decide whether to fail-open (prioritizing operational continuity) or fail-closed (prioritizing security containment).

Autonomous AI agents possess self-directed agency and can execute irreversible external side-effects (e.g., executing financial transactions, wiping tables, sending external messages).

## Decision
We enforce a strict **Fail-Secure (Fail-Closed)** default across the Runtime Enforcement Plane:
1. **Policy Engine Unreachable**: Default verdict is `BLOCK`. No unvalidated action may be dispatched.
2. **Identity / Session Service Unreachable**: Default verdict is `BLOCK`. No unauthenticated or unverified agent session may execute.
3. **Database / Budget Counter Unreachable**: Default verdict is `BLOCK`. No unmetered actions may run when quota states are unknown.
4. **Audit Dispatcher Failure**:
   - Transient spikes are absorbed by a bounded in-memory buffer (maximum 5 seconds / 1,000 events).
   - If the audit buffer fills to capacity and audit records cannot be persisted, the gateway trips a circuit breaker and renders `BLOCK` on all subsequent actions until audit storage recovers.

## Consequences
### Positive
- Zero probability of unauthorized actions or budget breaches during infrastructure degradation.
- Ensures absolute compliance with regulatory and security audit mandates (no un-audited executions).

### Negative / Trade-offs
- Agent operations may be temporarily interrupted if governance infrastructure suffers a total outage. High availability (redundant nodes, active-active read replicas) is mandatory to minimize blast radius.
