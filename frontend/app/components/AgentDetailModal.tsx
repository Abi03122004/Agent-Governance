"use client";

import React, { useEffect, useState } from "react";
import { api } from "../../lib/api";
import { HumanPurgeModal } from "./HumanPurgeModal";

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
  framework?: string;
  llm_provider?: string;
  connection_status?: string;
  last_seen_at?: string | null;
  governed_requests_count?: number;
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
  onAgentStatusChanged,
}) => {
  const [loading, setLoading] = useState(true);
  const [agent, setAgent] = useState<AgentInfo | null>(null);
  const [sessions, setSessions] = useState<SessionInfo[]>([]);
  const [actions, setActions] = useState<ActionInfo[]>([]);
  const [updatingStatus, setUpdatingStatus] = useState(false);
  const [rotatingKey, setRotatingKey] = useState(false);
  const [newSecret, setNewSecret] = useState<string | null>(null);
  const [copiedSecret, setCopiedSecret] = useState(false);
  const [isDeleteModalOpen, setIsDeleteModalOpen] = useState(false);

  const handleRotateKey = async () => {
    if (!agent) return;
    try {
      setRotatingKey(true);
      const data = await api.rotateAgentCredential(agent.id);
      setNewSecret(data.plaintext_secret);
      onAgentStatusChanged();
    } catch (err) {
      console.error("Failed to rotate key", err);
    } finally {
      setRotatingKey(false);
    }
  };

  useEffect(() => {
    const fetchDetail = async () => {
      try {
        setLoading(true);
        const data = (await api.getAgent(agentId)) as unknown as {
          agent: AgentInfo;
          sessions?: SessionInfo[];
          recent_actions?: ActionInfo[];
        };
        if (data && data.agent) {
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
  }, [agentId]);

  const toggleStatus = async () => {
    if (!agent) return;
    const newStatus = agent.status === "active" ? "suspended" : "active";
    try {
      setUpdatingStatus(true);
      await api.updateAgentStatus(agent.id, newStatus);
      setAgent({ ...agent, status: newStatus });
      onAgentStatusChanged();
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
        inset: 0,
        backgroundColor: "rgba(0, 0, 0, 0.85)",
        backdropFilter: "blur(8px)",
        display: "flex",
        alignItems: "center",
        justifyContent: "center",
        zIndex: 1000,
        padding: "20px",
      }}
      onClick={onClose}
    >
      <div
        style={{
          width: "100%",
          maxWidth: "840px",
          maxHeight: "90vh",
          overflowY: "auto",
          background: "#18171B",
          border: "1px solid #262529",
          borderRadius: "22px",
          padding: "24px 28px",
          display: "flex",
          flexDirection: "column",
          gap: "20px",
          boxShadow: "0 24px 48px rgba(0,0,0,0.7), 0 0 20px rgba(255, 73, 47, 0.12)",
        }}
        onClick={(e) => e.stopPropagation()}
      >
        {/* Header */}
        <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", borderBottom: "1px solid #262529", paddingBottom: "14px" }}>
          <div style={{ display: "flex", alignItems: "center", gap: "12px" }}>
            <div
              style={{
                width: "42px",
                height: "42px",
                borderRadius: "12px",
                background: "linear-gradient(135deg, #FF492F 0%, #FF7043 100%)",
                display: "flex",
                alignItems: "center",
                justifyContent: "center",
                color: "#FFFFFF",
                fontSize: "1.2rem",
                boxShadow: "0 0 16px rgba(255, 73, 47, 0.35)",
              }}
            >
              🤖
            </div>
            <div>
              <h2 style={{ fontSize: "1.05rem", fontWeight: 700, color: "#F5F5F5", margin: 0 }}>
                {loading ? "Loading Agent..." : agent?.name || agentId}
              </h2>
              <span className="code-pill" style={{ marginTop: "3px" }}>
                {agentId}
              </span>
            </div>
          </div>
          <button
            onClick={onClose}
            style={{
              background: "transparent",
              border: "none",
              color: "#858585",
              cursor: "pointer",
              fontSize: "1.2rem",
              padding: "4px",
            }}
            aria-label="Close"
          >
            ✕
          </button>
        </div>

        {loading ? (
          <div style={{ textAlign: "center", padding: "40px", color: "#858585", fontSize: "0.8125rem" }}>
            Loading telemetry and activity history...
          </div>
        ) : agent ? (
          <>
            {/* Identity Grid */}
            <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(180px, 1fr))", gap: "10px" }}>
              <div style={{ background: "#141316", border: "1px solid #262529", padding: "12px 14px", borderRadius: "12px" }}>
                <div style={{ fontSize: "0.6875rem", color: "#858585", fontFamily: "var(--font-mono)" }}>ORGANIZATION</div>
                <div style={{ fontWeight: 600, color: "#F5F5F5", fontSize: "0.8125rem", marginTop: "3px" }}>{agent.organization_id}</div>
              </div>
              <div style={{ background: "#141316", border: "1px solid #262529", padding: "12px 14px", borderRadius: "12px" }}>
                <div style={{ fontSize: "0.6875rem", color: "#858585", fontFamily: "var(--font-mono)" }}>PROJECT</div>
                <div style={{ fontWeight: 600, color: "#F5F5F5", fontSize: "0.8125rem", marginTop: "3px" }}>{agent.project_id}</div>
              </div>
              <div style={{ background: "#141316", border: "1px solid #262529", padding: "12px 14px", borderRadius: "12px" }}>
                <div style={{ fontSize: "0.6875rem", color: "#858585", fontFamily: "var(--font-mono)" }}>ENVIRONMENT</div>
                <div style={{ fontWeight: 700, color: "#FF7043", fontSize: "0.8125rem", textTransform: "uppercase", marginTop: "3px" }}>{agent.environment}</div>
              </div>
              <div style={{ background: "#141316", border: "1px solid #262529", padding: "12px 14px", borderRadius: "12px" }}>
                <div style={{ fontSize: "0.6875rem", color: "#858585", fontFamily: "var(--font-mono)" }}>OWNER</div>
                <div style={{ fontWeight: 600, color: "#F5F5F5", fontSize: "0.8125rem", marginTop: "3px" }}>{agent.owner}</div>
              </div>
              <div style={{ background: "#141316", border: "1px solid #262529", padding: "12px 14px", borderRadius: "12px" }}>
                <div style={{ fontSize: "0.6875rem", color: "#858585", fontFamily: "var(--font-mono)" }}>FRAMEWORK</div>
                <div style={{
                  fontWeight: 700,
                  color: agent.framework?.toLowerCase() === "langgraph"
                    ? "#10B981"
                    : agent.framework?.toLowerCase() === "openhands"
                    ? "#FF7043"
                    : "#A78BFA",
                  fontSize: "0.8125rem",
                  textTransform: "uppercase",
                  marginTop: "3px"
                }}>
                  {agent.framework || "custom"}
                </div>
              </div>
              <div style={{ background: "#141316", border: "1px solid #262529", padding: "12px 14px", borderRadius: "12px" }}>
                <div style={{ fontSize: "0.6875rem", color: "#858585", fontFamily: "var(--font-mono)" }}>CONNECTION STATUS</div>
                <div style={{ display: "inline-flex", alignItems: "center", gap: "6px", fontSize: "0.8125rem", color: agent.connection_status === "connected" ? "#10B981" : "#858585", marginTop: "3px", fontFamily: "var(--font-mono)" }}>
                  <span style={{ width: "6px", height: "6px", borderRadius: "50%", background: agent.connection_status === "connected" ? "#10B981" : "#52525A" }} />
                  {agent.connection_status || "registered"}
                </div>
              </div>
              <div style={{ background: "#141316", border: "1px solid #262529", padding: "12px 14px", borderRadius: "12px", gridColumn: "span 2" }}>
                <div style={{ fontSize: "0.6875rem", color: "#858585", fontFamily: "var(--font-mono)" }}>CAPABILITY SCOPE</div>
                <div style={{ color: "#A1A1A8", fontSize: "0.8125rem", marginTop: "3px" }}>{agent.purpose || "General autonomous tasks"}</div>
              </div>
              <div style={{ background: "#141316", border: "1px solid #262529", padding: "12px 14px", borderRadius: "12px", display: "flex", alignItems: "center", justifyContent: "space-between" }}>
                <div>
                  <div style={{ fontSize: "0.6875rem", color: "#858585", fontFamily: "var(--font-mono)" }}>STATUS</div>
                  <span className={`badge ${agent.status === "active" ? "badge-allow" : "badge-block"}`} style={{ marginTop: "4px" }}>
                    {agent.status.toUpperCase()}
                  </span>
                </div>
                <button
                  className={agent.status === "active" ? "btn btn-danger" : "btn btn-primary"}
                  onClick={toggleStatus}
                  disabled={updatingStatus}
                  style={{ fontSize: "0.75rem", padding: "5px 12px" }}
                >
                  {updatingStatus ? "Updating..." : agent.status === "active" ? "Suspend Agent" : "Activate Agent"}
                </button>
              </div>
            </div>

            {/* Cryptographic Credential Management */}
            <div style={{ background: "#141316", border: "1px solid #262529", padding: "14px 16px", borderRadius: "14px" }}>
              <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", flexWrap: "wrap", gap: "10px" }}>
                <div>
                  <div style={{ fontSize: "0.8125rem", fontWeight: 600, color: "#F5F5F5" }}>
                    Cryptographic Bearer Secret Key
                  </div>
                  <div style={{ fontSize: "0.72rem", color: "#858585", marginTop: "2px" }}>
                    Rotating secret generates a new high-entropy token and immediately deactivates previous active credentials.
                  </div>
                </div>
                <button
                  id="btn-rotate-agent-key"
                  className="btn btn-ghost"
                  onClick={handleRotateKey}
                  disabled={rotatingKey}
                  style={{ fontSize: "0.75rem", padding: "5px 12px", color: "#FF7043" }}
                >
                  {rotatingKey ? "Rotating..." : "🔄 Rotate Secret Key"}
                </button>
              </div>

              {newSecret && (
                <div style={{ marginTop: "12px", padding: "12px 14px", background: "rgba(255, 73, 47, 0.1)", border: "1px solid rgba(255, 73, 47, 0.3)", borderRadius: "10px" }}>
                  <div style={{ fontSize: "0.72rem", color: "#FF7043", fontWeight: 700, marginBottom: "6px" }}>
                    ⚠ NEW SECRET GENERATED (SINGLE VIEW — SAVE NOW):
                  </div>
                  <div style={{ display: "flex", alignItems: "center", gap: "8px" }}>
                    <code style={{ flex: 1, fontFamily: "var(--font-mono)", fontSize: "0.75rem", color: "#FF8A65", wordBreak: "break-all", background: "#0B0B0D", padding: "8px 10px", borderRadius: "8px", border: "1px solid #262529" }}>
                      {newSecret}
                    </code>
                    <button
                      className="btn btn-primary"
                      onClick={() => {
                        navigator.clipboard.writeText(newSecret);
                        setCopiedSecret(true);
                        setTimeout(() => setCopiedSecret(false), 3000);
                      }}
                      style={{ fontSize: "0.75rem", padding: "6px 14px", whiteSpace: "nowrap" }}
                    >
                      {copiedSecret ? "Copied!" : "Copy"}
                    </button>
                  </div>
                </div>
              )}
            </div>

            {/* Sessions Table */}
            <div>
              <h3 style={{ fontSize: "0.875rem", fontWeight: 600, color: "#F5F5F5", marginBottom: "8px" }}>
                Runtime Sessions ({sessions.length})
              </h3>
              {sessions.length === 0 ? (
                <div style={{ color: "#858585", fontSize: "0.75rem", padding: "14px", background: "#141316", border: "1px solid #262529", borderRadius: "10px", textAlign: "center" }}>
                  No active or past sessions found.
                </div>
              ) : (
                <div style={{ overflowX: "auto", maxHeight: "160px", border: "1px solid #262529", borderRadius: "12px" }}>
                  <table style={{ width: "100%", borderCollapse: "collapse", fontSize: "0.78rem", textAlign: "left" }}>
                    <thead>
                      <tr style={{ color: "#858585", borderBottom: "1px solid #262529", background: "#141316" }}>
                        <th style={{ padding: "8px 12px" }}>Session ID</th>
                        <th style={{ padding: "8px 12px" }}>Status</th>
                        <th style={{ padding: "8px 12px" }}>Started At</th>
                      </tr>
                    </thead>
                    <tbody>
                      {sessions.map((s) => (
                        <tr key={s.session_id} style={{ borderBottom: "1px solid rgba(255, 255, 255, 0.04)" }}>
                          <td style={{ padding: "8px 12px", fontFamily: "var(--font-mono)", color: "#FF7043" }}>{s.session_id}</td>
                          <td style={{ padding: "8px 12px" }}>
                            <span className={`badge ${s.status === "active" ? "badge-allow" : "badge-block"}`}>
                              {s.status}
                            </span>
                          </td>
                          <td style={{ padding: "8px 12px", color: "#858585", fontFamily: "var(--font-mono)" }}>
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
              <h3 style={{ fontSize: "0.875rem", fontWeight: 600, color: "#F5F5F5", marginBottom: "8px" }}>
                Recent Evaluated Actions ({actions.length})
              </h3>
              {actions.length === 0 ? (
                <div style={{ color: "#858585", fontSize: "0.75rem", padding: "14px", background: "#141316", border: "1px solid #262529", borderRadius: "10px", textAlign: "center" }}>
                  No mediated actions recorded yet.
                </div>
              ) : (
                <div style={{ overflowX: "auto", maxHeight: "200px", border: "1px solid #262529", borderRadius: "12px" }}>
                  <table style={{ width: "100%", borderCollapse: "collapse", fontSize: "0.78rem", textAlign: "left" }}>
                    <thead>
                      <tr style={{ color: "#858585", borderBottom: "1px solid #262529", background: "#141316" }}>
                        <th style={{ padding: "8px 12px" }}>Time</th>
                        <th style={{ padding: "8px 12px" }}>Tool &amp; Op</th>
                        <th style={{ padding: "8px 12px" }}>Resource</th>
                        <th style={{ padding: "8px 12px" }}>Decision</th>
                        <th style={{ padding: "8px 12px" }}>Execution</th>
                        <th style={{ padding: "8px 12px" }}>Digest</th>
                      </tr>
                    </thead>
                    <tbody>
                      {actions.map((act) => (
                        <tr key={act.action_id} style={{ borderBottom: "1px solid rgba(255, 255, 255, 0.04)" }}>
                          <td style={{ padding: "8px 12px", color: "#858585", fontFamily: "var(--font-mono)" }}>
                            {new Date(act.timestamp).toLocaleTimeString()}
                          </td>
                          <td style={{ padding: "8px 12px" }}>
                            <span className="code-pill">{act.tool}.{act.operation}</span>
                          </td>
                          <td style={{ padding: "8px 12px", color: "#A1A1A8" }}>{act.resource}</td>
                          <td style={{ padding: "8px 12px" }}>
                            <span className={`badge ${getBadgeClass(act.decision)}`}>
                              {act.decision}
                            </span>
                          </td>
                          <td style={{ padding: "8px 12px", color: act.execution_status === "EXECUTED" ? "#10B981" : "#858585", fontFamily: "var(--font-mono)", fontSize: "0.72rem" }}>
                            {act.execution_status}
                          </td>
                          <td style={{ padding: "8px 12px", fontFamily: "var(--font-mono)", fontSize: "0.7rem", color: "#A78BFA" }}>
                            {act.action_digest ? act.action_digest.slice(0, 10) + "..." : "-"}
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              )}
            </div>

            {/* Human Operator Danger Zone */}
            <div
              style={{
                marginTop: "10px",
                padding: "14px 16px",
                background: "rgba(255, 73, 47, 0.08)",
                border: "1px solid rgba(255, 73, 47, 0.25)",
                borderRadius: "14px",
                display: "flex",
                alignItems: "center",
                justifyContent: "space-between",
                flexWrap: "wrap",
                gap: "12px",
              }}
            >
              <div>
                <div style={{ fontSize: "0.8125rem", fontWeight: 700, color: "#FF492F", display: "flex", alignItems: "center", gap: "6px" }}>
                  <span>🛡️ HUMAN OPERATOR CONTROL:</span>
                  <span>Permanently Remove Agent</span>
                </div>
                <div style={{ fontSize: "0.72rem", color: "#858585", marginTop: "2px" }}>
                  Permanently purges agent identity, cascades credentials deletion, and cleans up historical sessions.
                </div>
              </div>
              <button
                id="btn-remove-agent-detail"
                className="btn btn-danger"
                onClick={() => setIsDeleteModalOpen(true)}
                style={{ fontSize: "0.75rem", padding: "6px 14px", display: "inline-flex", alignItems: "center", gap: "6px" }}
              >
                <span>✕</span>
                <span>Remove Agent Permanently</span>
              </button>
            </div>

            {/* Human Purge Confirmation Modal */}
            <HumanPurgeModal
              isOpen={isDeleteModalOpen}
              onClose={() => setIsDeleteModalOpen(false)}
              title="Permanently Remove Agent Identity"
              targetDescription={`Agent: ${agent.name} (${agent.id})`}
              warningNote="This will permanently delete the agent's identity, cryptographic keys, and cancel active runtime sessions. Autonomous agents are strictly blocked from invoking this deletion."
              actionButtonText="Authorize & Remove Agent"
              onConfirm={async (rationale) => {
                await api.deleteAgent(agent.id, rationale);
                onAgentStatusChanged();
                onClose();
              }}
            />
          </>
        ) : (
          <div style={{ color: "#FF492F", textAlign: "center" }}>
            Could not find agent with id: {agentId}
          </div>
        )}
      </div>
    </div>
  );
};
