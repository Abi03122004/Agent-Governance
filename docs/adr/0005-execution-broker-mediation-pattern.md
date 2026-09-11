# ADR 0005: Secure Execution Broker Mediation Pattern

## Status
Accepted

## Context
AI agents need to query databases, call external REST APIs, interact with filesystems, and communicate with SaaS platforms. 
If an agent is given direct access to upstream credentials (e.g., Stripe API keys, Postgres DB passwords, AWS IAM keys), the security boundary collapses if the agent's prompt is compromised or if it hallucinates an unauthorized query. Furthermore, direct agent-to-upstream communication bypasses governance controls entirely.

## Decision
We mandate the **In-Line Execution Broker Pattern**:
1. **Zero Upstream Credentials for Agents**:
   - The agent environment contains zero target API keys, database credentials, or third-party tokens.
   - The agent is issued only an ephemeral, scoped session token valid solely against the Mediation Gateway.
2. **Broker-Mediated Dispatch**:
   - The Secure Execution Broker is the sole entity possessing network connectivity and credentials to upstream enterprise systems.
   - Upon receiving an `ALLOW` decision (or validated cryptographic approval), the Broker retrieves the upstream secret from the Secret Vault, constructs the outbound request, and executes it.
3. **Dual-Sided Inspection**:
   - The Broker inspects outgoing arguments against parameter schemas.
   - The Broker inspects incoming upstream responses, redacting sensitive secrets, PII, and checking for output-poisoning markers before returning the result to the agent.

## Consequences
### Positive
- Total containment: Even a fully subverted agent cannot extract raw upstream credentials from its memory or environment.
- Complete visibility and auditability into all external interactions.
- Dynamic data masking and PII redaction enforced centrally.

### Negative / Trade-offs
- Network hop added to external tool calls (target latency overhead: $< 25\text{ ms}$).
- The Execution Broker is a high-privilege component requiring hardened security posture, minimal OS footprint, and strict internal access controls.
