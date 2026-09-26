# API Specification & Endpoints

All APIs are versioned under `/api/v1` and organized into Swagger tags.

Swagger Documentation is available at:
`http://localhost:8000/docs`

---

## 1. Health Probes
| Method | Endpoint | Description |
|---|---|---|
| `GET` | `/health/live` | Process liveness probe. Returns 200 if API server is running. |
| `GET` | `/health/ready` | Dependency readiness probe. Validates PostgreSQL and Redis connectivity. |

---

## 2. Identity & Tenant Management
| Method | Endpoint | Description |
|---|---|---|
| `POST` | `/api/v1/organizations` | Create tenant organization (`id`, `name`). |
| `GET` | `/api/v1/organizations` | List organizations. |
| `POST` | `/api/v1/projects` | Create project bound to an organization. |
| `GET` | `/api/v1/projects` | List projects for an organization. |
| `POST` | `/api/v1/users` | Register human user (`id`, `email`, `display_name`). |
| `POST` | `/api/v1/users/memberships` | Assign user role (`administrator`, `security_operator`, `approver`, `viewer`). |

---

## 3. Agent Lifecycle & Credentials
| Method | Endpoint | Description |
|---|---|---|
| `POST` | `/api/v1/agents` | Register an autonomous agent under an organization and project. |
| `GET` | `/api/v1/agents` | List agents scoped by organization. |
| `GET` | `/api/v1/agents/{id}` | Retrieve agent identity metadata. |
| `PATCH` | `/api/v1/agents/{id}` | Update agent status (`active`, `suspended`, `revoked`). |
| `POST` | `/api/v1/agents/{id}/credentials` | Issue a cryptographic secret credential (displayed once). |
| `POST` | `/api/v1/agents/{id}/credentials/{cred_id}/revoke` | Revoke an issued agent credential. |

---

## 4. Sessions
| Method | Endpoint | Description |
|---|---|---|
| `POST` | `/api/v1/sessions` | Create a runtime session for an authenticated agent. |
| `GET` | `/api/v1/sessions` | List active and historical sessions. |
| `PATCH` | `/api/v1/sessions/{id}/terminate` | Terminate an active session. |

---

## 5. Runtime Mediation Gateway
| Method | Endpoint | Description |
|---|---|---|
| `POST` | `/api/v1/runtime/sessions` | Ephemeral session creation via Bearer credential. |
| `POST` | `/api/v1/runtime/actions/evaluate` | Evaluates an action contract against deterministic security policies. Returns decision (`ALLOW`, `BLOCK`, `REQUIRE_APPROVAL`, `SUSPEND`) and single-use `execution_authorization` token if allowed. |
| `POST` | `/api/v1/runtime/actions/{action_id}/execute` | Executes an authorized tool action. Validates single-use execution authorization token and action digest before invoking safe tools. |

---

## 6. Realtime Monitoring & Dashboard
| Method | Endpoint | Description |
|---|---|---|
| `GET` | `/api/v1/monitoring/stats` | Aggregated metrics: active agents, actions today, allowed, blocked, pending approval, suspended. |
| `GET` | `/api/v1/monitoring/agents` | List monitored agents with activity counts and last activity timestamps. |
| `GET` | `/api/v1/monitoring/agents/{id}` | Deep agent telemetry including associated sessions and recent actions. |
| `GET` | `/api/v1/monitoring/activity` | Paginated or live runtime activity stream. |
| `GET` | `/api/v1/monitoring/policies` | Active deterministic policy guardrails. |
| `WebSocket` | `/api/v1/monitoring/ws/activity` | Realtime event stream broadcasting all action evaluations and tool executions. |
