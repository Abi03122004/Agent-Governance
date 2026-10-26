# Autonomous AI Agent Security & Runtime Governance Platform

A high-assurance, pre-execution security runtime gateway and governance control plane for autonomous AI agents.

Every agent action is authenticated, normalized, evaluated against deterministic security policies, and enforced **before** any physical tool or side-effect execution occurs.

```text
AI Agent ──► Security Runtime Gateway ──► Policy Decision
                                                │
                                       ┌────────┴────────┐
                                       ▼                 ▼
                                     BLOCK             ALLOW
                                       │                 │
                                  Zero Tool              ▼
                                  Execution        Tool Execution
                                       │                 │
                                       └────────┬────────┘
                                                ▼
                                       Realtime Activity
                                                ▼
                                        Next.js Dashboard
```

---

## Core Security Invariants

1. **Pre-Execution Enforcement**: The control plane sits directly in the execution path. Blocked actions never invoke underlying tools ($\text{Execution Count} \equiv 0$).
2. **Derived Identity**: Identity (`agent_id`, `organization_id`, `project_id`) is derived strictly from cryptographic bearer credentials, never from client-asserted request bodies.
3. **Strict Multi-Tenant Isolation**: Tenant sandboxing guarantees that agents and users in Organization A cannot access or invoke resources belonging to Organization B.
4. **Deterministic Policy Boundary**: Policies are deterministic and testable. No non-deterministic LLM sits on the critical enforcement boundary.
5. **Action Digest Integrity**: Canonical $SHA-256$ digests prevent argument tampering and replay attacks.
6. **Single-Use Execution Authorizations**: Allowed actions receive short-lived, single-use execution tokens re-verified at execution time.

---

## Architecture Overview

```text
                    ┌─────────────────────────┐
                    │    Next.js Dashboard    │
                    │      (Port 3000)        │
                    └────────────┬────────────┘
                                 │ HTTP / WebSocket
                                 ▼
                    ┌─────────────────────────┐
                    │   FastAPI Security GW   │
                    │      (Port 8000)        │
                    └────────────┬────────────┘
                                 │
                ┌────────────────┼────────────────┐
                ▼                ▼                ▼
         PostgreSQL 16        Redis 7       Policy Engine
      (Tenant & Audit)    (Rate Limits)           │
                                           ┌──────┴──────┐
                                           ▼             ▼
                                         ALLOW         BLOCK
                                           │             │
                                           ▼             ▼
                                       Safe Tool     Tool NEVER
                                       Execution      Executes
```

---

## 1. Prerequisites

- **Docker & Docker Compose** (Recommended for full stack)
- **Python 3.11+** (For local backend development & test runner)
- **Node.js 20+ & npm** (For local frontend development)

---

## 2. Quick Start with Docker Compose

Run the entire platform (PostgreSQL, Redis, FastAPI Backend, Next.js Dashboard) with a single command:

```bash
docker compose up --build
```

### Endpoints
- **Next.js Dashboard**: [http://localhost:3000](http://localhost:3000)
- **FastAPI Control Plane**: [http://localhost:8000](http://localhost:8000)
- **Swagger Documentation**: [http://localhost:8000/docs](http://localhost:8000/docs)
- **Liveness Health Check**: [http://localhost:8000/health/live](http://localhost:8000/health/live)
- **Readiness Health Check**: [http://localhost:8000/health/ready](http://localhost:8000/health/ready)

---

## 3. Local Development (Without Docker)

### Backend Setup

1. Navigate to the backend directory and set up a virtual environment:
   ```bash
   cd backend
   python -m venv .venv
   # Windows:
   .\.venv\Scripts\activate
   # Linux/macOS:
   source .venv/bin/activate
   pip install -e .
   ```

2. Configure environment variables:
   ```bash
   cp ../.env.example .env
   ```

3. Run migrations and start the server:
   ```bash
   uvicorn agent_security.main:app --host 0.0.0.0 --port 8000 --reload
   ```

### Frontend Setup

1. Navigate to the frontend directory:
   ```bash
   cd frontend
   npm install
   npm run dev
   ```
   Open [http://localhost:3000](http://localhost:3000) in your browser.

---

## 4. Running the Test Suite

The test suite thoroughly covers identity, credentials, tenant isolation, deterministic policy evaluation, action integrity, execution authorization, SSRF-safe connectors, indirect prompt injection defense, anomaly monitoring, and zero-execution enforcement:

```bash
cd backend
# Windows Powershell:
$env:PYTHONPATH='src'; .venv\Scripts\python.exe -m pytest -v
# Linux / macOS:
PYTHONPATH=src pytest -v
```

**All 88 unit, integration, and security tests pass cleanly (100% pass rate).**

---

## 5. Security Architecture & Defense Layers

- **Zero-Bypass Runtime Interceptor**: All tool operations pass through the gateway mediator before any side effect. Blocked operations return execution count $\equiv 0$.
- **SSRF-Safe Connector**: Prohibits private IP ranges (`10.0.0.0/8`, `172.16.0.0/12`, `192.168.0.0/16`), cloud metadata (`169.254.169.254`), loopbacks, IPv6 mapped variants, enforces redirect destination revalidation, DNS rebinding guards, and 5MB response caps.
- **Confinement & SQLi-Safe Connectors**: Chroot workspace confinement (`SafeFileConnector`) with path traversal prevention and dotfile blocking (`.env`, `id_rsa`, `.pem`). Parameterized database connector (`SafeDatabaseConnector`) blocking destructive DDL and SQL injection patterns.
- **Outbound Data Loss Prevention (DLP)**: Automatic classification labels (`RESTRICTED`, `CONFIDENTIAL`, `INTERNAL`, `PUBLIC`) and sensitive key / PII redaction (`[REDACTED_SECRET]`, SSN, credit cards).
- **Indirect Prompt Injection Defense**: `InjectionDetector` scans for DAN jailbreaks, system role overrides, exfiltration triggers, and chat template smuggling (`<|im_start|>`, `[INST]`, `<<SYS>>`). Untrusted external data is encapsulated within `<untrusted_tool_output>` blocks with cryptographic hashes and escaped delimiters.
- **Anomaly & Rate Spike Monitoring**: Sliding-window tracking in Redis (with in-memory fallback) alerting on rate spikes ($>30$ ops/min) and repeated policy blocks ($\ge 3$ blocks in 300s).
- **Human-in-the-Loop (HITL) Approvals**: Cryptographically signed execution tickets with strict separation of agent owner vs approver, and immediate expiry enforcement.
- **Cryptographic Audit Hash Chain**: Every audit event is chained via SHA-256 (`previous_event_hash -> event_hash`), tamper-evident, and verifiable in real-time via `/api/v1/audit/verify-chain`.

---

## 6. Multi-Agent Simulation & Verification Demo

The platform includes simulated independent agents communicating over HTTP with the runtime gateway:

- **Finance Agent**: Permitted database read (`ALLOW`); destructive delete attempt is blocked (`BLOCK`).
- **Support Agent**: Customer ticket lookup (`ALLOW`).
- **DevOps Agent**: Production mutation requiring human sign-off (`REQUIRE_APPROVAL`).
- **Research Agent**: Literature review (`ALLOW`); credential theft attempt is blocked (`BLOCK`).

### Run the Master 8-Step Demo

Ensure the backend is running, then execute:

```bash
python agents/run_demo.py
```

### Run Standalone Agents

Each agent can also be executed independently:

```bash
python agents/finance_agent.py
python agents/support_agent.py
python agents/devops_agent.py
python agents/research_agent.py
```

---

## 7. End-to-End Demo Scenario Flow

1. **Bootstrap & Register**: Automatically creates `Enterprise Autonomous Fleet` organization, `Core Ops` project, reviewer user, and registers 4 agents (Finance, Support, DevOps, Research).
2. **Issue Credentials**: Issues cryptographically hashed credentials for each agent.
3. **Establish Sessions**: Each agent authenticates via Bearer token to establish an isolated runtime session.
4. **Finance Read (`ALLOW`)**: Requesting `database.read` evaluates to `ALLOW`, single-use authorization token is issued, and tool executes.
5. **Finance Delete (`BLOCK`)**: Requesting `database.delete` evaluates to `BLOCK`. Zero authorization token is issued. Tool execution count remains strictly 0.
6. **DevOps Mutation & HITL Sign-Off (`REQUIRE_APPROVAL`)**: Staging deployment mutation evaluates to `REQUIRE_APPROVAL`. Automatic execution is frozen until an authorized reviewer (`reviewer@enterprise.internal`) approves the ticket.
7. **Research Protected Secrets Attempt (`BLOCK`)**: Unauthorized secrets retrieval is intercepted and blocked at the gateway.
8. **Emergency Suspension (`SUSPEND`)**: Finance Agent is suspended via administrative control. Subsequent actions are immediately halted at the gateway.
9. **Realtime Dashboard Monitoring & Audit Chain**: Telemetry and cryptographic SHA-256 audit ledger verify complete tamper-free state.

---

## 8. Next.js Dashboard Features

- **Mission Control Overview**: Realtime metric cards (`Active Agents`, `Actions Today`, `Allowed`, `Blocked`, `Pending Approval`, `Suspended`).
- **Live Interception Stream**: Instant visual updates via WebSocket (`/api/v1/monitoring/ws/activity`) with short-polling fallback. Distinct visual badges for `ALLOW`, `BLOCK`, `REQUIRE_APPROVAL`, `SUSPEND`.
- **HITL Approval Queue**: Real-time pending approval widget allowing security operators to inspect canonical action hashes, review arguments, and submit Approve/Reject decisions with audit rationale.
- **Cryptographic Audit Ledger**: Immutable audit log table with one-click live SHA-256 hash chain verification (`/api/v1/audit/verify-chain`).
- **Agent Credentials & Rotation**: Agent details modal with one-time credential display, copy-to-clipboard, and instant credential rotation with old secret revocation.
- **Agents Management**: Complete agent identity table with status toggle (`Suspend` / `Activate`) and deep inspection modal.
- **Sessions Inspector**: Table of all active and historical agent runtime sessions.
- **Runtime Activity Table**: Detailed audit record including cryptographic action digests and correlation IDs.
- **Policy Guardrails**: Inspection of active deterministic policies and trigger conditions.
- **Emergency Global Kill Switch**: One-click administrative kill switch freezing all outbound agent actions.

---

## 8. Documentation Index

- [docs/architecture.md](docs/architecture.md): Control Plane vs Runtime Enforcement Plane, In-Line Mediation architecture.
- [docs/security-model.md](docs/security-model.md): Security boundary invariants, tenant isolation, and zero-execution proof.
- [docs/runtime-flow.md](docs/runtime-flow.md): Sequence diagrams and step-by-step action mediation lifecycle.
- [docs/api.md](docs/api.md): Complete REST & WebSocket API specification and Swagger taxonomy.
