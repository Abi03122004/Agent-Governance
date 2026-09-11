# ADR 0006: Decoupling Policy Decisions from Execution Lifecycle States

## Status
Accepted

## Context
Many prototype agent security frameworks conflate the governance policy decision (whether an action is permitted) with the execution lifecycle state (whether an action is queued, running, succeeded, or failed). 

For example, equating `ALLOW` directly to "executed" or treating a network timeout as a "policy denial" creates ambiguity in audit trails, race conditions in state transitions, and leaves human approval workflows ill-defined.

## Decision
We enforce strict conceptual and architectural decoupling between:
1. **Policy Decision Dimension**:
   - Represents the governance verdict rendered by the policy engine.
   - States: `EVALUATING`, `ALLOW`, `BLOCK`, `REQUIRE_APPROVAL`, `SUSPEND`.
   - Immutable once evaluated for a specific action hash.
2. **Execution Lifecycle State Dimension**:
   - Represents the physical execution status managed by the execution broker.
   - States: `SUBMITTED`, `AWAITING_APPROVAL`, `APPROVED`, `REJECTED`, `SCHEDULED`, `EXECUTING`, `SUCCEEDED`, `FAILED`, `CANCELLED`.

An action cannot enter `SCHEDULED` or `EXECUTING` without a prerequisite Policy Decision of `ALLOW` (or `REQUIRE_APPROVAL` followed by a validated human approval transition to `APPROVED`).

## Consequences
### Positive
- Clear, unambiguous audit logs: Auditors can distinguish between an unauthorized attempt (`BLOCK`) vs an approved action that suffered a network timeout (`FAILED`).
- Clean handling of asynchronous long-running tools and human approvals.
- Prevents invalid state jumps (e.g., executing an unapproved or blocked action).

### Negative / Trade-offs
- Requires managing two related state attributes on execution records.
