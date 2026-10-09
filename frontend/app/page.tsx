"use client";

import React, { useState, useEffect, useCallback } from "react";
import { Sidebar } from "./components/Sidebar";
import { Header } from "./components/Header";
import { StatCard } from "./components/StatCard";
import { LiveInterceptionFeed, ActivityItem } from "./components/LiveInterceptionFeed";
import { SystemReadinessWidget } from "./components/SystemReadinessWidget";
import { AgentDetailModal } from "./components/AgentDetailModal";
import { AddAgentModal } from "./components/AddAgentModal";

interface StatsData {
  active_agents: number;
  suspended_agents: number;
  actions_today: number;
  total_actions: number;
  allowed: number;
  blocked: number;
  pending_approval: number;
  suspended: number;
}

interface MonitoredAgent {
  agent_id: string;
  name: string;
  organization_id: string;
  project_id: string;
  environment: string;
  status: string;
  last_activity: string | null;
  action_count: number;
}

interface SessionData {
  session_id: string;
  organization_id: string;
  project_id: string;
  agent_id: string;
  status: string;
  started_at: string;
}

interface PolicyRule {
  id: string;
  name: string;
  decision: string;
  condition: string;
  description: string;
  priority: number;
  status: string;
}

export default function Home({ initialTab = "overview" }: { initialTab?: string } = {}) {
  const [activeTab, setActiveTab] = useState(initialTab);
  const [isKilled, setIsKilled] = useState(false);
  const [selectedAgentId, setSelectedAgentId] = useState<string | null>(null);
  const [isAddAgentModalOpen, setIsAddAgentModalOpen] = useState(false);
  const [selectedTenant, setSelectedTenant] = useState("org_enterprise");

  const apiBase = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

  // Data states
  const [stats, setStats] = useState<StatsData>({
    active_agents: 0,
    suspended_agents: 0,
    actions_today: 0,
    total_actions: 0,
    allowed: 0,
    blocked: 0,
    pending_approval: 0,
    suspended: 0,
  });

  const [activities, setActivities] = useState<ActivityItem[]>([]);
  const [agents, setAgents] = useState<MonitoredAgent[]>([]);
  const [sessions, setSessions] = useState<SessionData[]>([]);
  const [policies, setPolicies] = useState<PolicyRule[]>([]);
  const [isWsConnected, setIsWsConnected] = useState(false);

  // Fetch functions
  const fetchStats = useCallback(async () => {
    try {
      const res = await fetch(`${apiBase}/api/v1/monitoring/stats`);
      if (res.ok) {
        const data = await res.json();
        setStats(data);
      }
    } catch {
      // offline or initial load
    }
  }, [apiBase]);

  const fetchActivities = useCallback(async () => {
    try {
      const res = await fetch(`${apiBase}/api/v1/monitoring/activity?limit=100`);
      if (res.ok) {
        const data = await res.json();
        setActivities(data);
      }
    } catch {
      // offline
    }
  }, [apiBase]);

  const fetchAgents = useCallback(async () => {
    try {
      const res = await fetch(`${apiBase}/api/v1/monitoring/agents`);
      if (res.ok) {
        const data = await res.json();
        setAgents(data);
      }
    } catch {
      // offline
    }
  }, [apiBase]);

  const fetchSessions = useCallback(async () => {
    try {
      const res = await fetch(`${apiBase}/api/v1/sessions`);
      if (res.ok) {
        const data = await res.json();
        setSessions(data);
      }
    } catch {
      // offline
    }
  }, [apiBase]);

  const fetchPolicies = useCallback(async () => {
    try {
      const res = await fetch(`${apiBase}/api/v1/monitoring/policies`);
      if (res.ok) {
        const data = await res.json();
        setPolicies(data);
      }
    } catch {
      // offline
    }
  }, [apiBase]);

  const refreshAll = useCallback(() => {
    fetchStats();
    fetchActivities();
    fetchAgents();
    fetchSessions();
    fetchPolicies();
  }, [fetchStats, fetchActivities, fetchAgents, fetchSessions, fetchPolicies]);

  // Initial load and periodic polling
  useEffect(() => {
    const initTimer = setTimeout(() => {
      refreshAll();
    }, 0);
    const interval = setInterval(refreshAll, 6000);
    return () => {
      clearTimeout(initTimer);
      clearInterval(interval);
    };
  }, [refreshAll]);

  // WebSocket Live Stream
  useEffect(() => {
    const wsUrl = apiBase.replace(/^http/, "ws") + "/api/v1/monitoring/ws/activity";
    let ws: WebSocket | null = null;
    let reconnectTimeout: ReturnType<typeof setTimeout> | null = null;

    const connectWs = () => {
      try {
        ws = new WebSocket(wsUrl);

        ws.onopen = () => {
          setIsWsConnected(true);
        };

        ws.onmessage = (event) => {
          try {
            const raw = JSON.parse(event.data);
            const newAct: ActivityItem = {
              action_id: raw.action_id || `act_${Date.now()}`,
              timestamp: raw.timestamp || new Date().toISOString(),
              agent_id: raw.agent_id || "agent",
              tool: raw.tool || "tool",
              operation: raw.operation || "operation",
              resource: raw.resource || "resource",
              decision: raw.decision || "ALLOW",
              execution_status: raw.execution_status || raw.status || "EVALUATED",
              reason_code: raw.reason_code,
              action_digest: raw.action_digest,
              correlation_id: raw.correlation_id,
            };

            setActivities((prev) => [newAct, ...prev.slice(0, 99)]);
            fetchStats();
            fetchAgents();
          } catch (e) {
            console.error("Failed to parse WS activity", e);
          }
        };

        ws.onclose = () => {
          setIsWsConnected(false);
          reconnectTimeout = setTimeout(connectWs, 5000);
        };

        ws.onerror = () => {
          setIsWsConnected(false);
        };
      } catch {
        setIsWsConnected(false);
      }
    };

    connectWs();

    return () => {
      if (ws) ws.close();
      if (reconnectTimeout) clearTimeout(reconnectTimeout);
    };
  }, [apiBase, fetchStats, fetchAgents]);

  // Emergency Kill Switch Toggle
  const toggleKillSwitch = async () => {
    const nextState = !isKilled;
    setIsKilled(nextState);

    // If activating kill switch, suspend all agents
    if (nextState) {
      for (const ag of agents) {
        if (ag.status === "active") {
          try {
            await fetch(`${apiBase}/api/v1/agents/${ag.agent_id}`, {
              method: "PATCH",
              headers: {
                "Content-Type": "application/json",
                "X-User-Email": "security_admin@enterprise.internal",
              },
              body: JSON.stringify({ status: "suspended" }),
            });
          } catch {
            // ignore
          }
        }
      }
      refreshAll();
    }
  };

  const toggleAgentStatus = async (agentId: string, currentStatus: string) => {
    const nextStatus = currentStatus === "active" ? "suspended" : "active";
    try {
      await fetch(`${apiBase}/api/v1/agents/${agentId}`, {
        method: "PATCH",
        headers: {
          "Content-Type": "application/json",
          "X-User-Email": "security_admin@enterprise.internal",
        },
        body: JSON.stringify({ status: nextStatus }),
      });
      refreshAll();
    } catch (e) {
      console.error("Failed to update status", e);
    }
  };

  const handleAgentRegistered = (newAgent: MonitoredAgent) => {
    setAgents((prev) => {
      const existingIndex = prev.findIndex((a) => a.agent_id === newAgent.agent_id);
      if (existingIndex >= 0) {
        const copy = [...prev];
        copy[existingIndex] = newAgent;
        return copy;
      }
      return [newAgent, ...prev];
    });
    fetchAgents();
    fetchStats();
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
    <div style={{ display: "flex", minHeight: "100vh", background: "var(--canvas-bg)" }}>
      {/* 1. Left Fixed Navigation Sidebar */}
      <Sidebar
        activeTab={activeTab}
        onSelectTab={setActiveTab}
        activeAgentsCount={stats.active_agents}
        blockedCount={stats.blocked}
      />

      {/* 2. Main Content Area */}
      <div style={{ flex: 1, display: "flex", flexDirection: "column", minWidth: 0 }}>
        <Header
          onTriggerKillSwitch={toggleKillSwitch}
          isKilled={isKilled}
          selectedTenant={selectedTenant}
          onSelectTenant={setSelectedTenant}
        />

        <main id="main-content" style={{ padding: "20px 24px", display: "flex", flexDirection: "column", gap: "16px" }}>
          {/* Emergency Kill Switch Banner if Active */}
          {isKilled && (
            <div
              id="banner-kill-switch-active"
              style={{
                padding: "12px 18px",
                background: "var(--status-block-bg)",
                border: "1px solid var(--status-block-border)",
                borderRadius: "3px",
                display: "flex",
                alignItems: "center",
                justifyContent: "space-between",
                gap: "16px",
              }}
            >
              <div style={{ display: "flex", alignItems: "center", gap: "10px" }}>
                <span style={{ fontSize: "1.1rem" }}>■</span>
                <div>
                  <div style={{ fontWeight: 600, color: "#FFFFFF", fontSize: "0.875rem", fontFamily: "var(--font-mono)" }}>
                    GLOBAL KILL SWITCH ACTIVATED — ALL OUTBOUND TOOL EXECUTIONS FROZEN
                  </div>
                  <div style={{ fontSize: "0.75rem", color: "#FFA198", maxWidth: "75ch" }}>
                    All agent identities placed in suspended state. Any attempt to invoke tools will be terminated at the gateway.
                  </div>
                </div>
              </div>
              <button className="btn btn-ghost" onClick={toggleKillSwitch} style={{ fontSize: "0.75rem", color: "#FFFFFF" }}>
                Deactivate Kill Switch
              </button>
            </div>
          )}

          {/* TAB 1: OVERVIEW / DASHBOARD */}
          {activeTab === "overview" && (
            <>
              {/* Section: Overview Metrics */}
              <section id="metrics-grid" style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(170px, 1fr))", gap: "10px" }}>
                <StatCard
                  id="stat-active-agents"
                  title="Active Agents"
                  value={stats.active_agents}
                  subtitle="Autonomous identities active"
                  icon="🤖"
                  accentColor="var(--accent-telegraph)"
                />
                <StatCard
                  id="stat-actions-today"
                  title="Actions Today"
                  value={stats.actions_today}
                  subtitle="Evaluated at gateway"
                  icon="⚡"
                  accentColor="var(--accent-telegraph)"
                />
                <StatCard
                  id="stat-allowed"
                  title="Allowed"
                  value={stats.allowed}
                  subtitle="Passed policy constraints"
                  icon="✅"
                  accentColor="var(--status-allow-fg)"
                />
                <StatCard
                  id="stat-blocked"
                  title="Blocked"
                  value={stats.blocked}
                  subtitle="Zero tool execution"
                  icon="🛡️"
                  accentColor="var(--status-block-fg)"
                />
                <StatCard
                  id="stat-pending-approval"
                  title="Pending Approval"
                  value={stats.pending_approval}
                  subtitle="Escalated to human reviewer"
                  icon="⏳"
                  accentColor="var(--status-approval-fg)"
                />
                <StatCard
                  id="stat-suspended"
                  title="Suspended"
                  value={stats.suspended}
                  subtitle="Frozen identities & actions"
                  icon="🛑"
                  accentColor="var(--status-suspend-fg)"
                />
              </section>

              {/* Section: Live In-Line Interception Feed */}
              <LiveInterceptionFeed
                activities={activities}
                onSelectAgent={(aid) => setSelectedAgentId(aid)}
                isLive={isWsConnected}
              />

              {/* Section: Infrastructure Health & Readiness */}
              <SystemReadinessWidget />
            </>
          )}

          {/* TAB 2: AGENTS */}
          {activeTab === "agents" && (
            <section className="glass-panel" style={{ padding: "18px 20px" }}>
              <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: "14px" }}>
                <div>
                  <h2 style={{ fontSize: "0.95rem", fontWeight: 600, color: "var(--text-primary)" }}>
                    Registered Agent Identities
                  </h2>
                  <div style={{ fontSize: "0.75rem", color: "var(--text-muted)", marginTop: "2px", maxWidth: "70ch" }}>
                    Each agent possesses cryptographic credentials tied to an organization and project scope.
                  </div>
                </div>
                <div style={{ display: "flex", alignItems: "center", gap: "8px" }}>
                  <button className="btn btn-ghost" onClick={fetchAgents} style={{ fontSize: "0.75rem", padding: "5px 10px" }}>
                    Refresh
                  </button>
                  <button
                    id="btn-add-agent"
                    className="btn btn-primary"
                    onClick={() => setIsAddAgentModalOpen(true)}
                    style={{ fontSize: "0.75rem", padding: "5px 12px" }}
                  >
                    + Add Agent
                  </button>
                </div>
              </div>

              {agents.length === 0 ? (
                <div style={{ textAlign: "center", padding: "36px", color: "var(--text-muted)", border: "1px dashed var(--border-rule)", borderRadius: "3px" }}>
                  <p style={{ marginBottom: "12px", fontSize: "0.8125rem" }}>
                    No agents registered yet. Run the multi-agent simulation scripts or register via API.
                  </p>
                  <button
                    id="btn-add-agent-empty"
                    className="btn btn-primary"
                    onClick={() => setIsAddAgentModalOpen(true)}
                    style={{ fontSize: "0.75rem", padding: "6px 14px" }}
                  >
                    + Add Agent
                  </button>
                </div>
              ) : (
                <div style={{ overflowX: "auto", border: "1px solid var(--border-rule)", borderRadius: "3px" }}>
                  <table style={{ width: "100%", borderCollapse: "collapse", fontSize: "0.8125rem", textAlign: "left" }}>
                    <thead>
                      <tr style={{ color: "var(--text-muted)", borderBottom: "1px solid var(--border-rule)" }}>
                        <th style={{ padding: "8px 12px" }}>Agent</th>
                        <th style={{ padding: "8px 12px" }}>Environment</th>
                        <th style={{ padding: "8px 12px" }}>Status</th>
                        <th style={{ padding: "8px 12px" }}>Last Activity</th>
                        <th style={{ padding: "8px 12px" }}>Actions</th>
                        <th style={{ padding: "8px 12px", textAlign: "right" }}>Governance</th>
                      </tr>
                    </thead>
                    <tbody>
                      {agents.map((ag) => (
                        <tr key={ag.agent_id} style={{ borderBottom: "1px solid var(--border-subtle)" }}>
                          <td style={{ padding: "10px 12px" }}>
                            <div style={{ fontWeight: 500, color: "var(--text-primary)" }}>{ag.name}</div>
                            <span className="code-pill" style={{ fontSize: "0.6875rem" }}>{ag.agent_id}</span>
                          </td>
                          <td style={{ padding: "10px 12px" }}>
                            <span
                              style={{
                                padding: "2px 6px",
                                borderRadius: "2px",
                                fontSize: "0.6875rem",
                                background: "var(--surface-plate)",
                                border: "1px solid var(--border-rule)",
                                color: "#79C0FF",
                                textTransform: "uppercase",
                                fontFamily: "var(--font-mono)",
                              }}
                            >
                              {ag.environment}
                            </span>
                          </td>
                          <td style={{ padding: "10px 12px" }}>
                            <span className={`badge ${ag.status === "active" ? "badge-allow" : "badge-block"}`}>
                              {ag.status}
                            </span>
                          </td>
                          <td style={{ padding: "10px 12px", color: "var(--text-muted)", fontFamily: "var(--font-mono)", fontSize: "0.75rem" }}>
                            {ag.last_activity ? new Date(ag.last_activity).toLocaleTimeString() : "Never"}
                          </td>
                          <td style={{ padding: "10px 12px", fontFamily: "var(--font-mono)", color: "var(--text-primary)" }}>
                            {ag.action_count}
                          </td>
                          <td style={{ padding: "10px 12px", textAlign: "right" }}>
                            <div style={{ display: "inline-flex", gap: "6px" }}>
                              <button
                                className="btn btn-ghost"
                                onClick={() => setSelectedAgentId(ag.agent_id)}
                                style={{ padding: "4px 8px", fontSize: "0.75rem" }}
                              >
                                View Details
                              </button>
                              <button
                                className={ag.status === "active" ? "btn btn-danger" : "btn btn-primary"}
                                onClick={() => toggleAgentStatus(ag.agent_id, ag.status)}
                                style={{ padding: "4px 8px", fontSize: "0.75rem" }}
                              >
                                {ag.status === "active" ? "Suspend" : "Activate"}
                              </button>
                            </div>
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              )}
            </section>
          )}

          {/* TAB 3: SESSIONS */}
          {activeTab === "sessions" && (
            <section className="glass-panel" style={{ padding: "18px 20px" }}>
              <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: "14px" }}>
                <div>
                  <h2 style={{ fontSize: "0.95rem", fontWeight: 600, color: "var(--text-primary)" }}>
                    Active & Historical Runtime Sessions
                  </h2>
                  <div style={{ fontSize: "0.75rem", color: "var(--text-muted)", marginTop: "2px", maxWidth: "70ch" }}>
                    Sessions are established via authenticated credentials. Actions must belong to an active session.
                  </div>
                </div>
                <button className="btn btn-ghost" onClick={fetchSessions} style={{ fontSize: "0.75rem", padding: "5px 10px" }}>
                  Refresh
                </button>
              </div>

              {sessions.length === 0 ? (
                <div style={{ textAlign: "center", padding: "36px", color: "var(--text-muted)", border: "1px dashed var(--border-rule)", borderRadius: "3px", fontSize: "0.8125rem" }}>
                  No sessions recorded yet.
                </div>
              ) : (
                <div style={{ overflowX: "auto", border: "1px solid var(--border-rule)", borderRadius: "3px" }}>
                  <table style={{ width: "100%", borderCollapse: "collapse", fontSize: "0.8125rem", textAlign: "left" }}>
                    <thead>
                      <tr style={{ color: "var(--text-muted)", borderBottom: "1px solid var(--border-rule)" }}>
                        <th style={{ padding: "8px 12px" }}>Session ID</th>
                        <th style={{ padding: "8px 12px" }}>Agent Identity</th>
                        <th style={{ padding: "8px 12px" }}>Organization / Project</th>
                        <th style={{ padding: "8px 12px" }}>Status</th>
                        <th style={{ padding: "8px 12px" }}>Started At</th>
                      </tr>
                    </thead>
                    <tbody>
                      {sessions.map((sess) => (
                        <tr key={sess.session_id} style={{ borderBottom: "1px solid var(--border-subtle)" }}>
                          <td style={{ padding: "10px 12px", fontFamily: "var(--font-mono)", color: "#79C0FF", fontSize: "0.75rem" }}>
                            {sess.session_id}
                          </td>
                          <td style={{ padding: "10px 12px", color: "var(--text-primary)", fontWeight: 500 }}>
                            {sess.agent_id}
                          </td>
                          <td style={{ padding: "10px 12px", color: "var(--text-muted)", fontSize: "0.75rem" }}>
                            {sess.organization_id} / {sess.project_id}
                          </td>
                          <td style={{ padding: "10px 12px" }}>
                            <span className={`badge ${sess.status === "active" ? "badge-allow" : "badge-block"}`}>
                              {sess.status}
                            </span>
                          </td>
                          <td style={{ padding: "10px 12px", color: "var(--text-muted)", fontFamily: "var(--font-mono)", fontSize: "0.75rem" }}>
                            {new Date(sess.started_at).toLocaleString()}
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              )}
            </section>
          )}

          {/* TAB 4: RUNTIME ACTIVITY */}
          {activeTab === "activity" && (
            <section className="glass-panel" style={{ padding: "18px 20px" }}>
              <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: "14px" }}>
                <div>
                  <h2 style={{ fontSize: "0.95rem", fontWeight: 600, color: "var(--text-primary)", display: "flex", alignItems: "center", gap: "8px" }}>
                    <span>Runtime Security Activity Stream</span>
                    <span className={`status-dot ${isWsConnected ? "status-dot-active status-dot-pulse" : ""}`} />
                  </h2>
                  <div style={{ fontSize: "0.75rem", color: "var(--text-muted)", marginTop: "2px", maxWidth: "70ch" }}>
                    Pre-execution policy evaluations with cryptographically deterministic action digests.
                  </div>
                </div>
                <button className="btn btn-ghost" onClick={fetchActivities} style={{ fontSize: "0.75rem", padding: "5px 10px" }}>
                  Refresh
                </button>
              </div>

              {activities.length === 0 ? (
                <div style={{ textAlign: "center", padding: "36px", color: "var(--text-muted)", border: "1px dashed var(--border-rule)", borderRadius: "3px", fontSize: "0.8125rem" }}>
                  No mediated activity recorded yet.
                </div>
              ) : (
                <div style={{ overflowX: "auto", border: "1px solid var(--border-rule)", borderRadius: "3px" }}>
                  <table style={{ width: "100%", borderCollapse: "collapse", fontSize: "0.8125rem", textAlign: "left" }}>
                    <thead>
                      <tr style={{ color: "var(--text-muted)", borderBottom: "1px solid var(--border-rule)" }}>
                        <th style={{ padding: "8px 12px" }}>Time</th>
                        <th style={{ padding: "8px 12px" }}>Agent</th>
                        <th style={{ padding: "8px 12px" }}>Tool & Op</th>
                        <th style={{ padding: "8px 12px" }}>Resource</th>
                        <th style={{ padding: "8px 12px" }}>Decision</th>
                        <th style={{ padding: "8px 12px" }}>Status</th>
                        <th style={{ padding: "8px 12px" }}>Action Digest</th>
                      </tr>
                    </thead>
                    <tbody>
                      {activities.map((act) => (
                        <tr key={act.action_id} style={{ borderBottom: "1px solid var(--border-subtle)" }}>
                          <td style={{ padding: "8px 12px", color: "var(--text-muted)", fontFamily: "var(--font-mono)", fontSize: "0.75rem" }}>
                            {new Date(act.timestamp).toLocaleTimeString()}
                          </td>
                          <td style={{ padding: "8px 12px", color: "var(--text-primary)", fontWeight: 500 }}>
                            <button
                              onClick={() => setSelectedAgentId(act.agent_id)}
                              style={{ background: "none", border: "none", color: "var(--text-primary)", cursor: "pointer", textDecoration: "underline", fontSize: "inherit", padding: 0 }}
                            >
                              {act.agent_id}
                            </button>
                          </td>
                          <td style={{ padding: "8px 12px" }}>
                            <span className="code-pill">{act.tool}.{act.operation}</span>
                          </td>
                          <td style={{ padding: "8px 12px", color: "var(--text-secondary)" }}>
                            {act.resource}
                          </td>
                          <td style={{ padding: "8px 12px" }}>
                            <span className={`badge ${getBadgeClass(act.decision)}`}>
                              {act.decision}
                            </span>
                          </td>
                          <td
                            style={{
                              padding: "8px 12px",
                              fontFamily: "var(--font-mono)",
                              fontSize: "0.75rem",
                              fontWeight: 600,
                              color:
                                act.execution_status === "EXECUTED"
                                  ? "var(--status-allow-fg)"
                                  : act.execution_status === "BLOCKED"
                                  ? "var(--status-block-fg)"
                                  : "var(--status-approval-fg)",
                            }}
                          >
                            {act.execution_status}
                          </td>
                          <td style={{ padding: "8px 12px", fontFamily: "var(--font-mono)", fontSize: "0.725rem", color: "#79C0FF" }}>
                            {act.action_digest ? act.action_digest.slice(0, 16) + "..." : "verified"}
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              )}
            </section>
          )}

          {/* TAB 5: POLICIES */}
          {activeTab === "policies" && (
            <section className="glass-panel" style={{ padding: "18px 20px" }}>
              <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: "14px" }}>
                <div>
                  <h2 style={{ fontSize: "0.95rem", fontWeight: 600, color: "var(--text-primary)" }}>
                    Deterministic Policy Engine Rules
                  </h2>
                  <div style={{ fontSize: "0.75rem", color: "var(--text-muted)", marginTop: "2px", maxWidth: "70ch" }}>
                    Policies are evaluated before any tool execution. No non-deterministic LLMs sit on the enforcement boundary.
                  </div>
                </div>
                <span className="code-pill">
                  ENGINE: ACTIVE
                </span>
              </div>

              <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(300px, 1fr))", gap: "10px" }}>
                {policies.map((p) => (
                  <div
                    key={p.id}
                    style={{
                      background: "var(--surface-plate)",
                      border: "1px solid var(--border-rule)",
                      borderRadius: "3px",
                      padding: "14px",
                      display: "flex",
                      flexDirection: "column",
                      gap: "8px",
                    }}
                  >
                    <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between" }}>
                      <span style={{ fontWeight: 600, color: "var(--text-primary)", fontSize: "0.85rem" }}>
                        {p.name}
                      </span>
                      <span className={`badge ${getBadgeClass(p.decision)}`}>
                        {p.decision}
                      </span>
                    </div>

                    <div style={{ fontSize: "0.75rem", color: "var(--text-secondary)", lineHeight: "1.4", maxWidth: "60ch" }}>
                      {p.description}
                    </div>

                    <div style={{ background: "#090D13", padding: "6px 8px", borderRadius: "3px", border: "1px solid var(--border-rule)" }}>
                      <div style={{ fontSize: "0.65rem", color: "var(--text-muted)", textTransform: "uppercase", fontFamily: "var(--font-mono)" }}>Condition</div>
                      <code style={{ fontSize: "0.75rem", color: "#79C0FF", fontFamily: "var(--font-mono)" }}>
                        {p.condition}
                      </code>
                    </div>

                    <div style={{ display: "flex", justifyContent: "space-between", fontSize: "0.6875rem", color: "var(--text-muted)", fontFamily: "var(--font-mono)", marginTop: "2px" }}>
                      <span>Rule: {p.id}</span>
                      <span>Priority: #{p.priority}</span>
                    </div>
                  </div>
                ))}
              </div>
            </section>
          )}

          {/* TAB 6: HEALTH */}
          {activeTab === "health" && <SystemReadinessWidget />}
        </main>
      </div>

      {/* Agent Detail Modal */}
      {selectedAgentId && (
        <AgentDetailModal
          agentId={selectedAgentId}
          onClose={() => setSelectedAgentId(null)}
          apiBaseUrl={apiBase}
          onAgentStatusChanged={refreshAll}
        />
      )}

      {/* Add Agent Modal */}
      <AddAgentModal
        isOpen={isAddAgentModalOpen}
        onClose={() => setIsAddAgentModalOpen(false)}
        apiBaseUrl={apiBase}
        currentTenant={selectedTenant}
        onAgentRegistered={handleAgentRegistered}
      />
    </div>
  );
}
