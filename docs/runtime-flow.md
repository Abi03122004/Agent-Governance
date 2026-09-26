# Runtime Flow & Mediation Lifecycle

## 1. High-Level Flow Diagram

```mermaid
sequenceDiagram
    autonumber
    participant Agent as Autonomous Agent
    participant GW as Runtime Security Gateway
    participant DB as Platform DB / Identity
    participant PE as Policy Engine
    participant Broker as Secure Execution Broker
    participant Tool as Target Tool / External API
    participant Stream as Realtime WebSocket / Dashboard

    Agent->>GW: 1. POST /api/v1/runtime/sessions (Bearer Token)
    GW->>DB: 2. Authenticate Credential & Load Agent Scope
    DB-->>GW: Verified Identity (Org, Project, Agent ID)
    GW-->>Agent: Session Created (session_id)

    Agent->>GW: 3. POST /api/v1/runtime/actions/evaluate (Action Contract)
    GW->>GW: 4. Validate Session & Normalize Contract
    GW->>GW: 5. Generate SHA-256 Action Digest
    GW->>PE: 6. Evaluate Deterministic Security Policies

    alt Policy Decision == ALLOW
        PE-->>GW: Decision: ALLOW (Reason: AUTHORIZED_ACTION)
        GW->>DB: Record Action & Issue Single-Use Authorization Token
        GW->>Stream: Broadcast Activity Event (ALLOW, EVALUATED)
        GW-->>Agent: {decision: "ALLOW", action_id: "...", execution_authorization: "..."}
        
        Agent->>GW: 7. POST /api/v1/runtime/actions/{action_id}/execute (Auth Token)
        GW->>GW: 8. Verify Digest, Non-Expired Token & Agent Active
        GW->>Broker: 9. Dispatch to Safe Execution Broker
        Broker->>Tool: 10. Execute Tool
        Tool-->>Broker: Tool Result
        Broker-->>GW: Sanitized Result
        GW->>DB: Update Execution Status -> EXECUTED
        GW->>Stream: Broadcast Execution Event (EXECUTED)
        GW-->>Agent: {status: "EXECUTED", result: "..."}

    else Policy Decision == BLOCK
        PE-->>GW: Decision: BLOCK (Reason: DESTRUCTIVE_OPERATION_DENIED)
        GW->>DB: Record Action (No Execution Authorization Issued)
        GW->>Stream: Broadcast Activity Event (BLOCK, BLOCKED)
        GW-->>Agent: {decision: "BLOCK", execution_authorization: null}
        Note over Broker,Tool: Tool execution count remains ZERO.

    else Policy Decision == REQUIRE_APPROVAL
        PE-->>GW: Decision: REQUIRE_APPROVAL
        GW->>DB: Record Action (Execution Paused)
        GW->>Stream: Broadcast Activity Event (REQUIRE_APPROVAL, EVALUATED)
        GW-->>Agent: {decision: "REQUIRE_APPROVAL", execution_authorization: null}
        Note over Broker,Tool: Awaiting human reviewer sign-off.
    end
```

---

## 2. Step-by-Step Lifecycle

### Step 1: Identity & Authentication
- Agents provide a secret bearer credential.
- Gateway hashes the credential and matches it against database records.
- Verifies `is_active`, `expires_at`, and `agent.status != 'revoked'`.
- Derives `organization_id` and `project_id` strictly from the credential.

### Step 2: Session Establishment
- Binds an ephemeral `session_id` to the agent identity.
- Sets expiration and tracking metadata.

### Step 3: Action Normalization & Cryptographic Digest
- Validates the incoming action contract (`tool`, `operation`, `resource`, `arguments`, `purpose`).
- Canonicalizes arguments into deterministic JSON representation.
- Calculates `action_digest = sha256(canonical_payload)`.

### Step 4: Deterministic Policy Evaluation
- **Agent Suspension Check**: If agent status is `suspended`, verdict is `SUSPEND` / `BLOCK`.
- **Resource Scope Check**: Restricted prefixes (`secrets/`, `credentials/`) yield `BLOCK`.
- **Destructive Mutation Check**: Destructive operations (`delete`, `drop`) yield `BLOCK`.
- **Production Mutation Check**: State changes in production yield `REQUIRE_APPROVAL`.
- **Safe Permitted Operations**: Low-risk operations on allowed resources yield `ALLOW`.

### Step 5: Execution Authorization & Pre-Execution Re-verification
- For `ALLOW` decisions, creates an ephemeral, single-use `execution_authorization` token.
- When `/execute` is called, the Gateway re-verifies:
  1. Agent is still active (not suspended during the window).
  2. Token is unexpired and unconsumed.
  3. Action digest matches the evaluated action.
  4. Session remains active.

### Step 6: Tool Execution & Telemetry Emission
- Safe tool executes inside the isolated broker.
- Sanitized results are returned to the agent.
- Runtime activity is persisted in PostgreSQL and broadcast live via WebSocket to the Next.js Dashboard.
