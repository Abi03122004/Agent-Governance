"use client";

import React, { useEffect, useState } from "react";

interface AgentDetailProps {
  agentId: string;
  onClose: () => void;
  apiBaseUrl: string;
  onAgentStatusChanged: () => void;
}

interface AgentInfo {
  id: string;
  organization_id: string;
  project_id: string;
  name: string;
  owner: string;
  environment: string;
  purpose: string | null;
  status: string;
  created_at: string;
  updated_at: string;
}

interface SessionInfo {
  session_id: string;
  status: string;
  started_at: string;
  ended_at: string | null;
}

interface ActionInfo {
  action_id: string;
  session_id: string;
  tool: string;
  operation: string;
  resource: string;
  decision: string;
  execution_status: string;
  action_digest: string;
  correlation_id: string | null;
  timestamp: string;
}

export const AgentDetailModal: React.FC<AgentDetailProps> = ({
  agentId,
  onClose,
  apiBaseUrl,
  onAgentStatusChanged,
}) => {
  const [loading, setLoading] = useState(true);
  const [agent, setAgent] = useState<AgentInfo | null>(null);
  const [sessions, setSessions] = useState<SessionInfo[]>([]);
  const [actions, setActions] = useState<ActionInfo[]>([]);
  const [updatingStatus, setUpdatingStatus] = useState(false);

  useEffect(() => {
    const fetchDetail = async () => {
      try {
        setLoading(true);
        const res = await fetch(`${apiBaseUrl}/api/v1/monitoring/agents/${agentId}`);
        if (res.ok) {
          const data = await res.json();
          setAgent(data.agent);
          setSessions(data.sessions || []);
          setActions(data.recent_actions || []);
        }
      } catch (err) {
        console.error("Failed to load agent details", err);
      } finally {
        setLoading(false);
      }
    };
    fetchDetail();
  }, [agentId, apiBaseUrl]);

  const toggleStatus = async () => {
    if (!agent) return;
    const newStatus = agent.status === "active" ? "suspended" : "active";
    try {
      setUpdatingStatus(true);
      const res = await fetch(`${apiBaseUrl}/api/v1/agents/${agent.id}`, {
        method: "PATCH",
        headers: {
          "Content-Type": "application/json",
          "X-User-Email": "security_admin@enterprise.internal",
        },
        body: JSON.stringify({ status: newStatus }),
      });
      if (res.ok) {
        setAgent({ ...agent, status: newStatus });
        onAgentStatusChanged();
      }
    } catch (err) {
      console.error("Failed to update status", err);
    } finally {
      setUpdatingStatus(false);
    }
  };

  const getBadgeClass = (decision: string) => {
    switch (decision) {
      case "ALLOW":
        return "badge-allow";
      case "BLOCK":
        return "badge-block";
      case "REQUIRE_APPROVAL":
        return "badge-approval";
      default:
        return "badge-suspend";
    }
  };

  return (
    <div
      style={{
        position: "fixed",
        top: 0,
        left: 0,
        right: 0,
        bottom: 0,
        backgroundColor: "rgba(13, 17, 23, 0.85)",
        display: "flex",
        alignItems: "center",
        justifyContent: "center",
        zIndex: 1000,
        padding: "16px",
      }}
      onClick={onClose}
    >
      <div
        style={{
          width: "100%",
          maxWidth: "800px",
          maxHeight: "88vh",
          overflowY: "auto",
          background: "var(--panel-bg)",
          border: "1px solid var(--border-rule)",
          borderRadius: "4px",
          padding: "20px 24px",
          display: "flex",
          flexDirection: "column",
          gap: "18px",
          boxShadow: "0 12px 28px rgba(0,0,0,0.6)",
        }}
        onClick={(e) => e.stopPropagation()}
      >
        {/* Header */}
        <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", borderBottom: "1px solid var(--border-rule)", paddingBottom: "12px" }}>
          <div style={{ display: "flex", alignItems: "center", gap: "10px" }}>
            <span style={{ fontSize: "1.2rem" }}>🤖</span>
            <div>
              <h2 style={{ fontSize: "1rem", fontWeight: 600, color: "var(--text-primary)" }}>
                {loading ? "Loading Agent..." : agent?.name || agentId}
              </h2>
              <span className="code-pill">
                {agentId}
              </span>
            </div>
          </div>
          <button
            className="btn btn-ghost"
            onClick={onClose}
            style={{ fontSize: "0.85rem", padding: "4px 8px" }}
          >
            ✕
          </button>
        </div>

        {loading ? (
          <div style={{ textAlign: "center", padding: "32px", color: "var(--text-muted)", fontSize: "0.8125rem" }}>
            Loading telemetry and activity history...
          </div>
        ) : agent ? (
          <>
            {/* Identity Grid */}
            <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(180px, 1fr))", gap: "10px" }}>
              <div style={{ background: "var(--surface-plate)", border: "1px solid var(--border-rule)", padding: "10px 12px", borderRadius: "3px" }}>
                <div style={{ fontSize: "0.6875rem", color: "var(--text-muted)", fontFamily: "var(--font-mono)" }}>ORGANIZATION</div>
                <div style={{ fontWeight: 500, color: "var(--text-primary)", fontSize: "0.8125rem", marginTop: "2px" }}>{agent.organization_id}</div>
              </div>
              <div style={{ background: "var(--surface-plate)", border: "1px solid var(--border-rule)", padding: "10px 12px", borderRadius: "3px" }}>
                <div style={{ fontSize: "0.6875rem", color: "var(--text-muted)", fontFamily: "var(--font-mono)" }}>PROJECT</div>
                <div style={{ fontWeight: 500, color: "var(--text-primary)", fontSize: "0.8125rem", marginTop: "2px" }}>{agent.project_id}</div>
              </div>
              <div style={{ background: "var(--surface-plate)", border: "1px solid var(--border-rule)", padding: "10px 12px", borderRadius: "3px" }}>
                <div style={{ fontSize: "0.6875rem", color: "var(--text-muted)", fontFamily: "var(--font-mono)" }}>ENVIRONMENT</div>
                <div style={{ fontWeight: 600, color: "#79C0FF", fontSize: "0.8125rem", textTransform: "uppercase", marginTop: "2px" }}>{agent.environment}</div>
              </div>
              <div style={{ background: "var(--surface-plate)", border: "1px solid var(--border-rule)", padding: "10px 12px", borderRadius: "3px" }}>
                <div style={{ fontSize: "0.6875rem", color: "var(--text-muted)", fontFamily: "var(--font-mono)" }}>OWNER</div>
                <div style={{ fontWeight: 500, color: "var(--text-primary)", fontSize: "0.8125rem", marginTop: "2px" }}>{agent.owner}</div>
              </div>
              <div style={{ background: "var(--surface-plate)", border: "1px solid var(--border-rule)", padding: "10px 12px", borderRadius: "3px", gridColumn: "span 2" }}>
                <div style={{ fontSize: "0.6875rem", color: "var(--text-muted)", fontFamily: "var(--font-mono)" }}>CAPABILITY SCOPE</div>
                <div style={{ color: "var(--text-secondary)", fontSize: "0.8125rem", marginTop: "2px", maxWidth: "65ch" }}>{agent.purpose || "General autonomous tasks"}</div>
              </div>
              <div style={{ background: "var(--surface-plate)", border: "1px solid var(--border-rule)", padding: "10px 12px", borderRadius: "3px", display: "flex", alignItems: "center", justifyContent: "space-between" }}>
                <div>
                  <div style={{ fontSize: "0.6875rem", color: "var(--text-muted)", fontFamily: "var(--font-mono)" }}>STATUS</div>
                  <span className={`badge ${agent.status === "active" ? "badge-allow" : "badge-block"}`} style={{ marginTop: "4px" }}>
                    {agent.status.toUpperCase()}
                  </span>
                </div>
                <button
                  className={agent.status === "active" ? "btn btn-danger" : "btn btn-primary"}
                  onClick={toggleStatus}
                  disabled={updatingStatus}
                  style={{ fontSize: "0.75rem", padding: "5px 10px" }}
                >
                  {updatingStatus ? "Updating..." : agent.status === "active" ? "Suspend Agent" : "Activate Agent"}
                </button>
              </div>
            </div>

            {/* Sessions Table */}
            <div>
              <h3 style={{ fontSize: "0.875rem", fontWeight: 600, color: "var(--text-primary)", marginBottom: "8px" }}>
                Runtime Sessions ({sessions.length})
              </h3>
              {sessions.length === 0 ? (
                <div style={{ color: "var(--text-muted)", fontSize: "0.75rem", padding: "10px", background: "var(--surface-plate)", border: "1px solid var(--border-rule)", borderRadius: "3px" }}>
                  No active or past sessions found.
                </div>
              ) : (
                <div style={{ overflowX: "auto", maxHeight: "150px", border: "1px solid var(--border-rule)", borderRadius: "3px" }}>
                  <table style={{ width: "100%", borderCollapse: "collapse", fontSize: "0.78rem", textAlign: "left" }}>
                    <thead>
                      <tr style={{ color: "var(--text-muted)", borderBottom: "1px solid var(--border-rule)" }}>
                        <th style={{ padding: "6px 10px" }}>Session ID</th>
                        <th style={{ padding: "6px 10px" }}>Status</th>
                        <th style={{ padding: "6px 10px" }}>Started At</th>
                      </tr>
                    </thead>
                    <tbody>
                      {sessions.map((s) => (
                        <tr key={s.session_id} style={{ borderBottom: "1px solid var(--border-subtle)" }}>
                          <td style={{ padding: "6px 10px", fontFamily: "var(--font-mono)", color: "#79C0FF" }}>{s.session_id}</td>
                          <td style={{ padding: "6px 10px" }}>
                            <span className={`badge ${s.status === "active" ? "badge-allow" : "badge-block"}`}>
                              {s.status}
                            </span>
                          </td>
                          <td style={{ padding: "6px 10px", color: "var(--text-muted)", fontFamily: "var(--font-mono)" }}>
                            {new Date(s.started_at).toLocaleTimeString()}
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              )}
            </div>

            {/* Recent Actions */}
            <div>
              <h3 style={{ fontSize: "0.875rem", fontWeight: 600, color: "var(--text-primary)", marginBottom: "8px" }}>
                Recent Evaluated Actions ({actions.length})
              </h3>
              {actions.length === 0 ? (
                <div style={{ color: "var(--text-muted)", fontSize: "0.75rem", padding: "10px", background: "var(--surface-plate)", border: "1px solid var(--border-rule)", borderRadius: "3px" }}>
                  No mediated actions recorded yet.
                </div>
              ) : (
                <div style={{ overflowX: "auto", maxHeight: "220px", border: "1px solid var(--border-rule)", borderRadius: "3px" }}>
                  <table style={{ width: "100%", borderCollapse: "collapse", fontSize: "0.78rem", textAlign: "left" }}>
                    <thead>
                      <tr style={{ color: "var(--text-muted)", borderBottom: "1px solid var(--border-rule)" }}>
                        <th style={{ padding: "6px 10px" }}>Time</th>
                        <th style={{ padding: "6px 10px" }}>Tool & Op</th>
                        <th style={{ padding: "6px 10px" }}>Resource</th>
                        <th style={{ padding: "6px 10px" }}>Decision</th>
                        <th style={{ padding: "6px 10px" }}>Execution</th>
                        <th style={{ padding: "6px 10px" }}>Digest</th>
                      </tr>
                    </thead>
                    <tbody>
                      {actions.map((act) => (
                        <tr key={act.action_id} style={{ borderBottom: "1px solid var(--border-subtle)" }}>
                          <td style={{ padding: "6px 10px", color: "var(--text-muted)", fontFamily: "var(--font-mono)" }}>
                            {new Date(act.timestamp).toLocaleTimeString()}
                          </td>
                          <td style={{ padding: "6px 10px" }}>
                            <span className="code-pill">{act.tool}.{act.operation}</span>
                          </td>
                          <td style={{ padding: "6px 10px", color: "var(--text-secondary)" }}>{act.resource}</td>
                          <td style={{ padding: "6px 10px" }}>
                            <span className={`badge ${getBadgeClass(act.decision)}`}>
                              {act.decision}
                            </span>
                          </td>
                          <td style={{ padding: "6px 10px", color: act.execution_status === "EXECUTED" ? "var(--status-allow-fg)" : "var(--text-muted)", fontFamily: "var(--font-mono)", fontSize: "0.72rem" }}>
                            {act.execution_status}
                          </td>
                          <td style={{ padding: "6px 10px", fontFamily: "var(--font-mono)", fontSize: "0.7rem", color: "#79C0FF" }}>
                            {act.action_digest ? act.action_digest.slice(0, 10) + "..." : "-"}
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              )}
            </div>
          </>
        ) : (
          <div style={{ color: "var(--status-block-fg)", textAlign: "center" }}>
            Could not find agent with id: {agentId}
          </div>
        )}
      </div>
    </div>
  );
};
