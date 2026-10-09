/**
 * Type definitions for Agent Governance Frontend Control Plane
 */

export type PolicyDecision = "ALLOW" | "BLOCK" | "REQUIRE_APPROVAL" | "SUSPEND";

export type AgentStatus = "active" | "suspended" | "revoked";

export type SessionStatus = "active" | "completed" | "terminated";

export interface StatsData {
  active_agents: number;
  suspended_agents: number;
  actions_today: number;
  total_actions: number;
  allowed: number;
  blocked: number;
  pending_approval: number;
  suspended: number;
}

export interface MonitoredAgent {
  agent_id: string;
  name: string;
  organization_id: string;
  project_id: string;
  environment: string;
  status: AgentStatus | string;
  last_activity: string | null;
  action_count: number;
}

export interface SessionData {
  session_id: string;
  organization_id: string;
  project_id: string;
  agent_id: string;
  status: SessionStatus | string;
  started_at: string;
}

export interface PolicyRule {
  id: string;
  name: string;
  decision: PolicyDecision | string;
  condition: string;
  description: string;
  priority: number;
  status: string;
}

export interface ActivityItem {
  id: string;
  action_id: string;
  agent_id: string;
  organization_id: string;
  project_id: string;
  tool: string;
  operation: string;
  resource: string;
  decision: PolicyDecision | string;
  reason_code: string;
  action_digest: string;
  execution_status: string;
  created_at: string;
}

export interface SystemReadiness {
  status: "ready" | "degraded" | "down";
  database: boolean;
  redis: boolean;
  timestamp: string;
}
