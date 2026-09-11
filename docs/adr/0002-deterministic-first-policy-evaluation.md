# ADR 0002: Deterministic-First Policy Evaluation and AI Risk Escalation

## Status
Accepted

## Context
AI agents operate in probabilistic and dynamic environments. Security teams may employ secondary AI models, classifiers, or heuristic scorers to assess the risk of an agent's intent or parameter contents (e.g., detecting subtle social engineering or prompt drift).

However, relying on probabilistic AI models as primary security gatekeepers is unsafe:
- LLMs can be jailbroken, manipulated, or suffer from non-deterministic variance.
- If an AI classifier has authority to approve an action, an adversarial prompt could convince the classifier to permit a dangerous action.

## Decision
We establish the **Deterministic-First Invariant**:
1. **Deterministic Authority**: Hard boundary policies (tenant scoping, tool whitelists, parameter regexes, budget quotas, hard denial lists) are strictly deterministic and evaluated first.
2. **One-Way Escalation Rule**:
   - AI risk classifiers may **only tighten or escalate** a decision:
     - `ALLOW` $\to$ `REQUIRE_APPROVAL` (if elevated risk detected)
     - `ALLOW` $\to$ `BLOCK` or `SUSPEND` (if critical threat detected)
     - `REQUIRE_APPROVAL` $\to$ `BLOCK` (if malicious intent confirmed)
   - An AI risk assessment can **NEVER override a deterministic denial**. If deterministic evaluation yields `BLOCK` or `SUSPEND`, that decision is final and non-negotiable.
3. **Classifier Failure Posture**:
   - If the AI risk classifier is offline or times out, the system defaults to the deterministic baseline. It does not permit arbitrary operations simply because the classifier was unreachable.

## Consequences
### Positive
- Prevents adversarial jailbreaks of secondary AI classifiers from ever punching holes through deterministic firewall rules.
- Guarantees predictable, auditable, and mathematically sound security floors.
- Complies directly with safety invariant #9.

### Negative / Trade-offs
- Secondary classifiers cannot provide "exceptions" to hard policies; any exceptions must be explicitly modeled in deterministic policy configurations by authorized administrators.
