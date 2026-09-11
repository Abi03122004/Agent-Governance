# Phase Checklist & Acceptance Test Matrix
## Autonomous AI Agent Security & Runtime Governance Platform

**Document Version:** 1.0.0  
**Phase:** Phase 0 (Scope & Security Architecture)  
**Status:** Approved Engineering Baseline  

---

## 1. Project Phase Checklist

| Phase | Title | Core Objectives | Status |
| :--- | :--- | :--- | :--- |
| **Phase 0** | **Scope & Security Architecture** | Define requirements, threat model, ADRs, PRD, domain contracts, lifecycle state machine, and test matrix. | **COMPLETED (Current)** |
| **Phase 1** | **Core Contracts & Policy Engine** | Typed domain schemas, canonical JSON hashing, deterministic ABAC/RBAC engine, parameter validators. | Planned (Next) |
| **Phase 2** | **In-Line Mediation Broker** | Protocol proxy (REST/MCP), secret vault integration, broker execution, credential isolation, response redaction. | Planned |
| **Phase 3** | **Cryptographic Approval Hub** | Human-in-the-loop API & WebSocket, canonical hash signing, single-use token consumption, TTL expiration. | Planned |
| **Phase 4** | **Budget & Concurrency Governor** | Atomic two-phase reservation in Redis/PostgreSQL, token/dollar spend counters, rate limiting. | Planned |
| **Phase 5** | **Tamper-Evident Audit Trail** | Cryptographic hash chaining, zero-credential redacting logger, WORM replication interface, audit query API. | Planned |
| **Phase 6** | **AI Risk Advisor & Kill Switch** | Secondary LLM drift detector, one-way risk escalation guardrail, instant session freeze kill switch. | Planned |
| **Phase 7** | **Control Plane UI & End-to-End Hardening**| Web dashboard, end-to-end integration tests, high-concurrency benchmarks, compliance reporting. | Planned |

---

## 2. Initial Acceptance-Test Matrix (ATM)

| Test ID | Category | Threat / Requirement Mapped | Test Description & Invariant Verified | Phase 0 Status | Target Phase |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **ATM-DEC-01** | Decision Semantics | 4 Core Verdicts | Verify decision engine produces exclusively `ALLOW`, `BLOCK`, `REQUIRE_APPROVAL`, `SUSPEND`. | **PASSED** (Unit Contract) | Phase 0 / 1 |
| **ATM-DEC-02** | Rule Precedence | Rule #9 (Deterministic Priority) | AI risk score cannot override a deterministic `BLOCK` or `SUSPEND`. AI score can only tighten (`ALLOW` $\to$ `REQUIRE_APPROVAL`/`BLOCK`). | **PASSED** (Unit Contract) | Phase 0 / 1 |
| **ATM-STA-01** | State Decoupling | ADR 0006 | Policy decision is strictly decoupled from execution state. An action cannot execute if decision is `BLOCK` or `REQUIRE_APPROVAL` (unapproved). | **PASSED** (Unit Contract) | Phase 0 / 1 |
| **ATM-STA-02** | State Transitions | Lifecycle State Machine | Verify valid transitions (`SUBMITTED` $\to$ `SCHEDULED` $\to$ `EXECUTING` $\to$ `SUCCEEDED`/`FAILED`) and reject invalid transitions (`SUBMITTED` $\to$ `SUCCEEDED`). | **PASSED** (Unit Contract) | Phase 0 / 1 |
| **ATM-HSH-01** | Tamper Detection | Threat Scenario 5 (TOCTOU) | Any change to tool arguments (even whitespace or ordering) changes the canonical $SHA-256$ hash and invalidates the approval token. | **PASSED** (Unit Contract) | Phase 0 / 1 |
| **ATM-APP-01** | Approval Replay | Threat Scenario 5 (Replay) | Approval tokens are single-use; attempting to consume the same approval twice fails with `ApprovalAlreadyConsumedException`. | **PASSED** (Unit Contract) | Phase 0 / 3 |
| **ATM-APP-02** | Approval Expiry | Threat Scenario 5 (TTL) | Expired approvals ($t > \text{expires\_at}$) are rejected automatically with `ApprovalExpiredException`. | **PASSED** (Unit Contract) | Phase 0 / 3 |
| **ATM-ISO-01** | Tenant Isolation | Threat Scenario 2 (Cross-Tenant) | Tenant ID extracted from token must strictly match target action; cross-tenant argument mismatch is rejected with `TenantMismatchException`. | **PASSED** (Unit Contract) | Phase 0 / 1 |
| **ATM-SEC-01** | Credential Zero-Log | Rule #7 (Zero Log Creds) | Audit event serializers automatically redact Authorization headers, API keys, passwords, and secret fields. | **PASSED** (Unit Contract) | Phase 0 / 5 |
| **ATM-SEC-02** | Fail-Secure Outage | ADR 0003 & Section 7 | Policy engine outage or database error falls back to `BLOCK` by default (never fail-open). | Planned | Phase 1 / 2 |
| **ATM-BRO-01** | In-line Mediation | Threat Scenario 1 (Bypass) | Agent has zero upstream credentials; execution broker injects secrets on egress only. | Planned | Phase 2 |
| **ATM-QTA-01** | Concurrent Budgets | Threat Scenario 6 (Race) | 50 concurrent requests cannot exceed account spending quota using two-phase atomic reservation. | Planned | Phase 4 |
| **ATM-AUD-01** | Audit Hash Chain | Threat Scenario 8 (Tampering) | Modifying any audit log record in storage breaks cryptographic hash chain verification. | Planned | Phase 5 |
| **ATM-KIL-01** | Kill Switch | ADR 0006 & PRD Section 5 | Invoking kill switch sets agent state to `SUSPENDED` and aborts all pending actions immediately. | Planned | Phase 6 |
