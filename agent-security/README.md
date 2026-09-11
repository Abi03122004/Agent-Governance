# Agent Security Runtime Governance Package

Core domain models, cryptographic canonical hashing, execution state machines, deterministic decision engines, and security invariants for the Autonomous AI Agent Security & Runtime Governance Platform.

## Core Invariants Enforced
1. **Four Explicit Decisions**: `ALLOW`, `BLOCK`, `REQUIRE_APPROVAL`, `SUSPEND`.
2. **Deterministic Priority (Rule #9)**: Deterministic policy rules always take precedence. Secondary AI risk evaluations can tighten or escalate a decision (`ALLOW` $\to$ `REQUIRE_APPROVAL`/`BLOCK`), but can never override a deterministic denial.
3. **Decoupled Lifecycle (ADR 0006)**: Policy decisions are strictly decoupled from execution lifecycle states.
4. **Cryptographic Approval Binding (ADR 0004)**: Approvals bind to the canonical $SHA-256$ hash of the action payload, preventing argument tampering (TOCTOU) and approval replays.
5. **Zero Credential Logging (Rule #7)**: Automated redaction of authorization headers, tokens, and secret fields in audit payloads.
