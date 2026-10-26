/**
 * Central API Client for Agent Governance Backend
 */

import { getAdminHeaders } from "./auth";

const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

export async function fetchApi<T>(endpoint: string, options: RequestInit = {}): Promise<T> {
  const url = `${API_BASE}${endpoint.startsWith("/") ? endpoint : `/${endpoint}`}`;
  const authHeaders = getAdminHeaders();
  const res = await fetch(url, {
    ...options,
    headers: {
      "Content-Type": "application/json",
      ...authHeaders,
      ...(options.headers || {}),
    },
  });

  if (!res.ok) {
    const errorText = await res.text();
    throw new Error(`API error ${res.status}: ${errorText}`);
  }

  return res.json();
}

export const api = {
  getStats: (organizationId?: string) =>
    fetchApi<Record<string, unknown>>(
      `/api/v1/monitoring/stats${organizationId ? `?organization_id=${encodeURIComponent(organizationId)}` : ""}`
    ),
  getActivity: (limit = 100, organizationId?: string) =>
    fetchApi<Record<string, unknown>[]>(
      `/api/v1/monitoring/activity?limit=${limit}${organizationId ? `&organization_id=${encodeURIComponent(organizationId)}` : ""}`
    ),
  getAgents: (organizationId?: string) =>
    fetchApi<Record<string, unknown>[]>(
      `/api/v1/monitoring/agents${organizationId ? `?organization_id=${encodeURIComponent(organizationId)}` : ""}`
    ),
  getAgent: (agentId: string, organizationId?: string) =>
    fetchApi<Record<string, unknown>>(
      `/api/v1/monitoring/agents/${agentId}${organizationId ? `?organization_id=${encodeURIComponent(organizationId)}` : ""}`
    ),
  getOrganizations: () => fetchApi<{ id: string; name: string; status: string }[]>("/api/v1/organizations"),
  createAgent: (data: unknown) =>
    fetchApi("/api/v1/agents", {
      method: "POST",
      body: JSON.stringify(data),
    }),
  updateAgentStatus: (agentId: string, status: string) =>
    fetchApi(`/api/v1/agents/${agentId}`, {
      method: "PATCH",
      body: JSON.stringify({ status }),
    }),
  suspendAgent: (agentId: string) =>
    fetchApi(`/api/v1/agents/${agentId}`, {
      method: "PATCH",
      body: JSON.stringify({ status: "suspended" }),
    }),
  activateAgent: (agentId: string) =>
    fetchApi(`/api/v1/agents/${agentId}`, {
      method: "PATCH",
      body: JSON.stringify({ status: "active" }),
    }),
  rotateAgentCredential: (agentId: string) =>
    fetchApi<{ credential_id: string; plaintext_secret: string }>(`/api/v1/agents/${agentId}/credentials/rotate`, {
      method: "POST",
    }),
  getSessions: (organizationId?: string) =>
    fetchApi<Record<string, unknown>[]>(
      `/api/v1/sessions${organizationId ? `?organization_id=${encodeURIComponent(organizationId)}` : ""}`
    ),
  getPolicies: (organizationId?: string) =>
    fetchApi<Record<string, unknown>[]>(
      `/api/v1/monitoring/policies${organizationId ? `?organization_id=${encodeURIComponent(organizationId)}` : ""}`
    ),
  getApprovals: (status = "PENDING", organizationId?: string) =>
    fetchApi<Record<string, unknown>[]>(
      `/api/v1/approvals?status=${status}${organizationId ? `&organization_id=${encodeURIComponent(organizationId)}` : ""}`
    ),
  approveAction: (ticketId: string, rationale = "Approved via Dashboard") =>
    fetchApi(`/api/v1/approvals/${ticketId}/approve`, {
      method: "POST",
      body: JSON.stringify({ rationale }),
    }),
  rejectAction: (ticketId: string, rationale = "Rejected via Dashboard") =>
    fetchApi(`/api/v1/approvals/${ticketId}/reject`, {
      method: "POST",
      body: JSON.stringify({ rationale }),
    }),
  getAuditEvents: (limit = 100, organizationId?: string) =>
    fetchApi<Record<string, unknown>[]>(
      `/api/v1/audit/events?limit=${limit}${organizationId ? `&organization_id=${encodeURIComponent(organizationId)}` : ""}`
    ),
  verifyAuditChain: (organizationId?: string) =>
    fetchApi<{ verified: boolean; event_count: number; message: string }>(
      `/api/v1/audit/verify-chain${organizationId ? `?organization_id=${encodeURIComponent(organizationId)}` : ""}`
    ),
  getHealthLive: () => fetchApi("/health/live"),
  getHealthReady: () => fetchApi("/health/ready"),
  // Human-only Data Purge Actions
  deleteAgent: (agentId: string, rationale?: string) =>
    fetchApi<{ status: string; agent_id: string }>(
      `/api/v1/agents/${agentId}${rationale ? `?rationale=${encodeURIComponent(rationale)}` : ""}`,
      { method: "DELETE" }
    ),
  purgeInactiveAgents: (organizationId?: string, rationale?: string) =>
    fetchApi<{ status: string; count: number }>(
      `/api/v1/agents/purge-inactive?${organizationId ? `organization_id=${encodeURIComponent(organizationId)}&` : ""}${rationale ? `rationale=${encodeURIComponent(rationale)}` : ""}`,
      { method: "POST" }
    ),
  clearAuditLogs: (organizationId?: string, rationale?: string) =>
    fetchApi<{ status: string; purged_count: number; message: string }>(
      `/api/v1/audit/clear${organizationId ? `?organization_id=${encodeURIComponent(organizationId)}` : ""}`,
      {
        method: "POST",
        body: JSON.stringify({
          confirmation: "CONFIRM",
          rationale: rationale || "Human Operator Purge",
        }),
      }
    ),
  clearRuntimeActivity: (organizationId?: string, rationale?: string) =>
    fetchApi<{ status: string; purged_count: number; message: string }>(
      `/api/v1/monitoring/activity/clear${organizationId ? `?organization_id=${encodeURIComponent(organizationId)}` : ""}`,
      {
        method: "POST",
        body: JSON.stringify({
          confirmation: "CONFIRM",
          rationale: rationale || "Human Operator Activity Reset",
        }),
      }
    ),
  deleteActivities: (actionIds: string[], organizationId?: string) =>
    fetchApi<{ status: string; purged_count: number; message: string }>(
      `/api/v1/monitoring/activity/clear${organizationId ? `?organization_id=${encodeURIComponent(organizationId)}` : ""}`,
      {
        method: "POST",
        body: JSON.stringify({
          confirmation: "CONFIRM",
          rationale: "Human Operator Selective Action Deletion",
          action_ids: actionIds,
        }),
      }
    ),
  clearSessions: (organizationId?: string, rationale?: string) =>
    fetchApi<{ status: string; purged_count: number; message: string }>(
      `/api/v1/sessions/clear?confirmation=CONFIRM${organizationId ? `&organization_id=${encodeURIComponent(organizationId)}` : ""}${rationale ? `&rationale=${encodeURIComponent(rationale)}` : ""}`,
      { method: "POST" }
    ),
};

