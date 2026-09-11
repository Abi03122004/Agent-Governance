# ADR 0004: Approval Cryptographic Binding and Lifecycle

## Status
Accepted

## Context
When a high-risk action yields `REQUIRE_APPROVAL`, an authorized human operator reviews and confirms the action. In naive implementations:
- Approvals are modeled as generic boolean flags or simple status updates (`approved: true` on an action ID).
- An attacker can modify tool arguments after the human approves (Time-of-Check to Time-of-Use / TOCTOU), causing the broker to execute unintended parameters with approved status.
- Stolen or replayed approval tokens could be used to authorize future, unrelated actions.

## Decision
We mandate **Cryptographic Hash Binding** and single-use lifecycle guarantees for all approvals:
1. **Canonical Action Hash**:
   - The platform calculates a canonical $SHA-256$ digest of the action:
     $$\text{ActionHash} = \text{SHA256}(\text{CanonicalJSON}(\{ \text{tenant\_id}, \text{project\_id}, \text{agent\_id}, \text{session\_id}, \text{task\_id}, \text{tool\_name}, \text{arguments} \}))$$
2. **Cryptographic Approval Token**:
   - The approval record binds strictly to this `ActionHash`, the authorized `approver_id`, and a short expiration timestamp ($TTL \le 15\text{ minutes}$).
   - Any modification to arguments (even whitespace or field ordering) alters the canonical hash and invalidates the approval token.
3. **Atomic Single-Use Consumption**:
   - Approvals transition through an atomic state machine: `PENDING` $\to$ `APPROVED` $\to$ `CONSUMED`.
   - The execution broker validates and atomically transitions the approval to `CONSUMED` inside a database transaction before dispatching the upstream call, eliminating replay attacks.

## Consequences
### Positive
- Completely eliminates argument tampering post-approval (TOCTOU).
- Eliminates replay attacks across different actions, sessions, or tasks.
- Produces non-repudiable audit evidence linking human identity to the exact payload executed.

### Negative / Trade-offs
- Requires deterministic canonical serialization (e.g., RFC 8785 JSON Canonicalization Scheme).
- Small computational overhead for canonicalization and hashing (sub-millisecond).
