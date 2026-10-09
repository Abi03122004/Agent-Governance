# Agent Security Runtime Governance Platform

Provider-neutral FastAPI gateway for governing agent actions before they reach a protected tool. It does not inspect private LLM reasoning or claim to monitor agents that do not call its runtime API.

## Run locally

```bash
docker compose up --build
```

The dashboard is at `http://localhost:3000`, the API at `http://localhost:8000`, and Swagger at `http://localhost:8000/docs`.

## Runtime protocol

1. Register an organization, project, and agent through the control-plane API, then create an agent credential. Store the returned secret in the agent's secret manager; it is shown only once.
2. The agent calls `POST /runtime/sessions` with `Authorization: Bearer <agent credential>`.
3. It submits only tool/action data to `POST /runtime/actions/evaluate`. Identity is derived from the credential, not request JSON.
4. An `ALLOW` response includes a short-lived, action-bound authorization. The demo tool is invoked with `POST /runtime/actions/{action_id}/execute`.
5. `BLOCK`, `REQUIRE_APPROVAL`, and `SUSPEND` responses have no execution authorization. They cannot reach the demo tool.

The `safe_echo` tool is intentionally harmless and is the only executable tool in this milestone. The `examples/` scripts demonstrate finance, support, and DevOps agents without an LLM provider.

Configure `NEXT_PUBLIC_DEVELOPMENT_ORGANIZATION_ID` and `NEXT_PUBLIC_DEVELOPMENT_USER_EMAIL` for the local dashboard. The monitoring API verifies that this development user belongs to the requested organization; production authentication should replace this header mechanism with OIDC.

## Core Invariants Enforced
1. **Four Explicit Decisions**: `ALLOW`, `BLOCK`, `REQUIRE_APPROVAL`, `SUSPEND`.
2. **Deterministic Priority (Rule #9)**: Deterministic policy rules always take precedence. Secondary AI risk evaluations can tighten or escalate a decision (`ALLOW` $\to$ `REQUIRE_APPROVAL`/`BLOCK`), but can never override a deterministic denial.
3. **Decoupled Lifecycle (ADR 0006)**: Policy decisions are strictly decoupled from execution lifecycle states.
4. **Cryptographic Approval Binding (ADR 0004)**: Approvals bind to the canonical $SHA-256$ hash of the action payload, preventing argument tampering (TOCTOU) and approval replays.
5. **Zero Credential Logging (Rule #7)**: Automated redaction of authorization headers, tokens, and secret fields in audit payloads.
