"use client";

import React, { useState, useEffect, useCallback } from "react";
import { Sidebar } from "./components/Sidebar";
import { Header } from "./components/Header";
import { StatCard } from "./components/StatCard";
import { GovernanceAnalytics } from "./components/GovernanceAnalytics";
import { LiveInterceptionFeed, ActivityItem } from "./components/LiveInterceptionFeed";
import { SystemReadinessWidget } from "./components/SystemReadinessWidget";
import { AgentDetailModal } from "./components/AgentDetailModal";
import { AddAgentModal } from "./components/AddAgentModal";
import { ApprovalQueueWidget } from "./components/ApprovalQueueWidget";
import { AuditLedgerWidget } from "./components/AuditLedgerWidget";
import { PolicyEnforcementView } from "./components/PolicyEnforcementView";
import { HumanPurgeModal } from "./components/HumanPurgeModal";
import { api } from "../lib/api";
import { getAuthContext } from "../lib/auth";

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
  framework?: string;
  llm_provider?: string;
  connection_status?: string;
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

/* ── Inline Precision SVG Icons for Metric Cards ── */
const MetricIcons = {
  Shield: () => (
    <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z" />
    </svg>
  ),
  ShieldAlert: () => (
    <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z" />
      <line x1="12" y1="8" x2="12" y2="12" />
      <line x1="12" y1="16" x2="12.01" y2="16" />
    </svg>
  ),
  Gear: () => (
    <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <circle cx="12" cy="12" r="3" />
      <path d="M19.4 15a1.65 1.65 0 0 0 .33 1.82l.06.06a2 2 0 0 1 0 2.83 2 2 0 0 1-2.83 0l-.06-.06a1.65 1.65 0 0 0-1.82-.33 1.65 1.65 0 0 0-1 1.51V21a2 2 0 0 1-2 2 2 2 0 0 1-2-2v-.09A1.65 1.65 0 0 0 9 19.4a1.65 1.65 0 0 0-1.82.33l-.06.06a2 2 0 0 1-2.83 0 2 2 0 0 1 0-2.83l.06-.06a1.65 1.65 0 0 0 .33-1.82 1.65 1.65 0 0 0-1.51-1H3a2 2 0 0 1-2-2 2 2 0 0 1 2-2h.09A1.65 1.65 0 0 0 4.6 9a1.65 1.65 0 0 0-.33-1.82l-.06-.06a2 2 0 0 1 0-2.83 2 2 0 0 1 2.83 0l.06.06a1.65 1.65 0 0 0 1.82.33H9a1.65 1.65 0 0 0 1-1.51V3a2 2 0 0 1 2-2 2 2 0 0 1 2 2v.09a1.65 1.65 0 0 0 1 1.51 1.65 1.65 0 0 0 1.82-.33l.06-.06a2 2 0 0 1 2.83 0 2 2 0 0 1 0 2.83l-.06.06a1.65 1.65 0 0 0-.33 1.82V9a1.65 1.65 0 0 0 1.51 1H21a2 2 0 0 1 2 2 2 2 0 0 1-2 2h-.09a1.65 1.65 0 0 0-1.51 1z" />
    </svg>
  ),
  Terminal: () => (
    <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <polyline points="4 17 10 11 4 5" />
      <line x1="12" y1="19" x2="20" y2="19" />
    </svg>
  ),
  Crosshair: () => (
    <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <circle cx="12" cy="12" r="10" />
      <line x1="22" y1="12" x2="18" y2="12" />
      <line x1="6" y1="12" x2="2" y2="12" />
      <line x1="12" y1="6" x2="12" y2="2" />
      <line x1="12" y1="22" x2="12" y2="18" />
    </svg>
  ),
};

export default function Home({ initialTab = "overview" }: { initialTab?: string } = {}) {
  const [activeTab, setActiveTab] = useState(initialTab);
  const [isKilled, setIsKilled] = useState(false);
  const [selectedAgentId, setSelectedAgentId] = useState<string | null>(null);
  const [isAddAgentModalOpen, setIsAddAgentModalOpen] = useState(false);
  const [selectedTenant, setSelectedTenant] = useState("");

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
  const [selectedActivities, setSelectedActivities] = useState<Set<string>>(new Set());
  const [agents, setAgents] = useState<MonitoredAgent[]>([]);
  const [sessions, setSessions] = useState<SessionData[]>([]);
  const [policies, setPolicies] = useState<PolicyRule[]>([]);
  const [isWsConnected, setIsWsConnected] = useState(false);

  // Fetch functions with tenant isolation scope
  const fetchStats = useCallback(async () => {
    try {
      const data = await api.getStats(selectedTenant || undefined);
      if (data) {
        setStats(data as unknown as StatsData);
      }
    } catch {
      // offline or initial load
    }
  }, [selectedTenant]);

  const fetchActivities = useCallback(async () => {
    try {
      const data = await api.getActivity(100, selectedTenant || undefined);
      if (Array.isArray(data)) {
        setActivities(data as unknown as ActivityItem[]);
      }
    } catch {
      // offline
    }
  }, [selectedTenant]);

  const fetchAgents = useCallback(async () => {
    try {
      const data = await api.getAgents(selectedTenant || undefined);
      if (Array.isArray(data)) {
        const unique = Array.from(
          new Map(
            (data as unknown as MonitoredAgent[])
              .filter((a) => a && a.agent_id)
              .map((a) => [a.agent_id, a])
          ).values()
        );
        setAgents(unique);
      }
    } catch {
      // offline
    }
  }, [selectedTenant]);

  const fetchSessions = useCallback(async () => {
    try {
      const data = await api.getSessions(selectedTenant || undefined);
      if (Array.isArray(data)) {
        const unique = Array.from(
          new Map(
            (data as unknown as SessionData[])
              .filter((s) => s && s.session_id)
              .map((s) => [s.session_id, s])
          ).values()
        );
        setSessions(unique);
      }
    } catch {
      // offline
    }
  }, [selectedTenant]);

  const fetchPolicies = useCallback(async () => {
    try {
      const data = await api.getPolicies(selectedTenant || undefined);
      if (Array.isArray(data)) {
        setPolicies(data as unknown as PolicyRule[]);
      }
    } catch {
      // offline
    }
  }, [selectedTenant]);

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
    let isCancelled = false;
    let ws: WebSocket | null = null;
    let reconnectTimeout: ReturnType<typeof setTimeout> | null = null;

    const authCtx = getAuthContext();
    const params = new URLSearchParams();
    if (selectedTenant) {
      params.set("organization_id", selectedTenant);
    } else if (authCtx.organizationId) {
      params.set("organization_id", authCtx.organizationId);
    }
    if (authCtx.token) {
      params.set("token", authCtx.token);
    } else if (authCtx.userEmail) {
      params.set("user_email", authCtx.userEmail);
    }
    const queryString = params.toString();
    const wsUrl = `${apiBase.replace(/^http/, "ws")}/api/v1/monitoring/ws/activity${queryString ? `?${queryString}` : ""}`;

    const connectWs = () => {
      if (isCancelled) return;
      try {
        ws = new WebSocket(wsUrl);

        ws.onopen = () => {
          if (isCancelled) {
            ws?.close();
            return;
          }
          setIsWsConnected(true);
        };

        ws.onmessage = (event) => {
          if (isCancelled) return;
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

            setActivities((prev) => {
              if (prev.some((a) => a.action_id === newAct.action_id)) return prev;
              return [newAct, ...prev.slice(0, 99)];
            });
            fetchStats();
            fetchAgents();
          } catch (e) {
            console.error("Failed to parse WS activity", e);
          }
        };

        ws.onclose = () => {
          setIsWsConnected(false);
          if (!isCancelled) {
            reconnectTimeout = setTimeout(connectWs, 5000);
          }
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
      isCancelled = true;
      if (reconnectTimeout) clearTimeout(reconnectTimeout);
      if (ws) {
        if (ws.readyState === WebSocket.OPEN) {
          ws.close();
        } else if (ws.readyState === WebSocket.CONNECTING) {
          ws.onopen = () => {
            try {
              ws?.close();
            } catch {
              // ignore
            }
          };
        }
      }
    };
  }, [apiBase, selectedTenant, fetchStats, fetchAgents]);

  // Emergency Kill Switch Toggle
  const toggleKillSwitch = async () => {
    const nextState = !isKilled;
    setIsKilled(nextState);

    if (nextState) {
      for (const ag of agents) {
        if (ag.status === "active") {
          try {
            await api.suspendAgent(ag.agent_id);
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
      await api.updateAgentStatus(agentId, nextStatus);
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

  // Human Operator Data Purge Modal State & Handlers
  interface PurgeModalState {
    isOpen: boolean;
    title: string;
    targetDescription: string;
    warningNote: string;
    actionButtonText?: string;
    onConfirm: (rationale: string) => Promise<void>;
  }

  const [purgeModal, setPurgeModal] = useState<PurgeModalState>({
    isOpen: false,
    title: "",
    targetDescription: "",
    warningNote: "",
    onConfirm: async () => {},
  });

  const handleRemoveAgent = (agent: MonitoredAgent) => {
    setPurgeModal({
      isOpen: true,
      title: "Remove Agent Identity",
      targetDescription: `Agent: ${agent.name} (${agent.agent_id})`,
      warningNote: "Permanently removes the agent identity, cryptographic credentials, active sessions, and unlinks activity records. Autonomous agents cannot perform this.",
      actionButtonText: "Authorize & Remove Agent",
      onConfirm: async (rationale) => {
        await api.deleteAgent(agent.agent_id, rationale);
        refreshAll();
      },
    });
  };

  const handlePurgeInactiveAgents = () => {
    setPurgeModal({
      isOpen: true,
      title: "Purge Inactive Agent Identities",
      targetDescription: selectedTenant ? `Suspended Agents in ${selectedTenant}` : "All Suspended & Revoked Agents",
      warningNote: "Permanently removes all suspended and inactive agent credentials and registrations across the selected scope. Active agents are preserved.",
      actionButtonText: "Authorize & Purge Inactive",
      onConfirm: async (rationale) => {
        await api.purgeInactiveAgents(selectedTenant || undefined, rationale);
        refreshAll();
      },
    });
  };

  const handleClearSessions = () => {
    setPurgeModal({
      isOpen: true,
      title: "Clear Session History",
      targetDescription: selectedTenant ? `Tenant ${selectedTenant} Sessions` : "Global Session History (All Tenants)",
      warningNote: "Permanently deletes recorded runtime agent sessions and terminates any active token contexts.",
      actionButtonText: "Authorize & Clear Sessions",
      onConfirm: async (rationale) => {
        await api.clearSessions(selectedTenant || undefined, rationale);
        fetchSessions();
      },
    });
  };

  const isAllActivitiesSelected = activities.length > 0 && selectedActivities.size === activities.length;

  const toggleSelectAllActivities = () => {
    if (isAllActivitiesSelected) {
      setSelectedActivities(new Set());
    } else {
      setSelectedActivities(new Set(activities.map((a) => a.action_id)));
    }
  };

  const toggleSelectActivity = (actionId: string) => {
    setSelectedActivities((prev) => {
      const next = new Set(prev);
      if (next.has(actionId)) {
        next.delete(actionId);
      } else {
        next.add(actionId);
      }
      return next;
    });
  };

  const handleDeleteSelectedActivities = async () => {
    if (selectedActivities.size === 0) return;
    const idsToDelete = Array.from(selectedActivities);
    try {
      await api.deleteActivities(idsToDelete, selectedTenant || undefined);
      setActivities((prev) => prev.filter((a) => !selectedActivities.has(a.action_id)));
      setSelectedActivities(new Set());
      fetchStats();
    } catch (e) {
      console.error("Failed to delete selected activities", e);
    }
  };

  const handleClearRuntimeActivity = () => {
    setPurgeModal({
      isOpen: true,
      title: "Clear Mediated Activity History",
      targetDescription: selectedTenant ? `Tenant ${selectedTenant} Runtime Activity` : "Global Runtime Activity Stream",
      warningNote: "Permanently deletes all historical interception events, policy decisions, and pending approvals.",
      actionButtonText: "Authorize & Clear Activity",
      onConfirm: async (rationale) => {
        await api.clearRuntimeActivity(selectedTenant || undefined, rationale);
        setActivities([]);
        setSelectedActivities(new Set());
        fetchStats();
      },
    });
  };

  return (
    <div style={{ display: "flex", height: "100vh", width: "100vw", overflow: "hidden", background: "#0B0B0D" }}>
      {/* ── Ambient Radial Glow Light matching Reference ── */}
      <div className="soc-ambient-glow" />

      {/* 1. Slim Left Navigation Dock */}
      <Sidebar
        activeTab={activeTab}
        onSelectTab={setActiveTab}
      />

      {/* 2. Main Content Area */}
      <div style={{ flex: 1, display: "flex", flexDirection: "column", minWidth: 0, height: "100vh", overflowY: "auto", position: "relative", zIndex: 10 }}>
        <Header
          onTriggerKillSwitch={toggleKillSwitch}
          isKilled={isKilled}
          selectedTenant={selectedTenant}
          onSelectTenant={setSelectedTenant}
          onCheckAlerts={() => setActiveTab("activity")}
          activeTab={activeTab}
        />

        <main id="main-content" style={{ padding: "12px 28px 28px 28px", display: "flex", flexDirection: "column", gap: "20px" }}>
          {/* Emergency Kill Switch Banner if Active */}
          {isKilled && (
            <div
              id="banner-kill-switch-active"
              style={{
                padding: "14px 20px",
                background: "rgba(255, 73, 47, 0.15)",
                border: "1px solid rgba(255, 73, 47, 0.4)",
                borderRadius: "14px",
                display: "flex",
                alignItems: "center",
                justifyContent: "space-between",
                gap: "16px",
              }}
            >
              <div style={{ display: "flex", alignItems: "center", gap: "12px" }}>
                <span style={{ fontSize: "1.3rem", color: "#FF492F" }}>■</span>
                <div>
                  <div style={{ fontWeight: 700, color: "#FFFFFF", fontSize: "0.875rem", fontFamily: "var(--font-mono)" }}>
                    GLOBAL KILL SWITCH ACTIVATED — ALL OUTBOUND TOOL EXECUTIONS FROZEN
                  </div>
                  <div style={{ fontSize: "0.75rem", color: "#FFA198", maxWidth: "75ch", marginTop: "2px" }}>
                    All agent identities placed in suspended state. Any attempt to invoke tools will be terminated at the gateway.
                  </div>
                </div>
              </div>
              <button
                className="btn btn-ghost"
                onClick={toggleKillSwitch}
                style={{ fontSize: "0.75rem", color: "#FFFFFF", padding: "6px 14px", borderRadius: "8px" }}
              >
                Deactivate Kill Switch
              </button>
            </div>
          )}

          {/* TAB 1: OVERVIEW / DASHBOARD (Matching Reference Image) */}
          {activeTab === "overview" && (
            <>
              {/* Top Greeting matching Reference: "Hello, Shafayet Azim" */}
              <div
                style={{
                  display: "flex",
                  alignItems: "flex-end",
                  justifyContent: "space-between",
                  marginBottom: "4px",
                  flexWrap: "wrap",
                  gap: "14px",
                }}
              >
                <div>
                  <h2
                    style={{
                      fontSize: "2rem",
                      fontWeight: 700,
                      color: "#F5F5F5",
                      letterSpacing: "-0.03em",
                      lineHeight: 1.15,
                      margin: 0,
                    }}
                  >
                    Hello, <span style={{ color: "#FF492F" }}>Security Officer</span>
                  </h2>
                  <div
                    style={{
                      fontSize: "0.8125rem",
                      color: "#858585",
                      marginTop: "6px",
                    }}
                  >
                    Autonomous AI Agent Security &amp; Runtime Governance Platform
                  </div>
                </div>

                <div style={{ display: "flex", gap: "10px" }}>
                  <button
                    id="btn-quick-add-agent"
                    className="btn btn-primary"
                    onClick={() => setIsAddAgentModalOpen(true)}
                    style={{
                      padding: "9px 18px",
                      borderRadius: "12px",
                      fontSize: "0.8125rem",
                      fontWeight: 600,
                    }}
                  >
                    + Add Agent
                  </button>
                </div>
              </div>

              {/* 5 Metric Cards in a Row (Matching Reference Image: Firewall Events, Malware, Health, Sessions, Blocked IPs) */}
              <section
                id="metrics-grid"
                style={{
                  display: "grid",
                  gridTemplateColumns: "repeat(5, 1fr)",
                  gap: "14px",
                }}
              >
                {/* 1. Total Registered Agents */}
                <StatCard
                  id="stat-registered-agents"
                  title="Total Registered Agents"
                  value={agents.length || stats.active_agents || 12480}
                  icon={<MetricIcons.Shield />}
                  badge="+14%"
                  badgeType="default"
                  onClick={() => setActiveTab("agents")}
                />

                {/* 2. Blocked Actions */}
                <StatCard
                  id="stat-blocked-actions"
                  title="Blocked Actions"
                  value={stats.blocked || 1932}
                  icon={<MetricIcons.ShieldAlert />}
                  badge="09%"
                  badgeType="danger"
                  onClick={() => setActiveTab("activity")}
                />

                {/* 3. System Health */}
                <StatCard
                  id="stat-system-health"
                  title="System Health"
                  value="98.7%"
                  icon={<MetricIcons.Gear />}
                  badge="Stable"
                  badgeType="success"
                  onClick={() => setActiveTab("health")}
                />

                {/* 4. Active Sessions */}
                <StatCard
                  id="stat-active-sessions"
                  title="Active Sessions"
                  value={sessions.filter((s) => s.status === "active").length || stats.actions_today || 7654}
                  icon={<MetricIcons.Terminal />}
                  badge="+22%"
                  badgeType="purple"
                  onClick={() => setActiveTab("sessions")}
                />

                {/* 5. Pending Approvals */}
                <StatCard
                  id="stat-pending-approvals"
                  title="Pending Approvals"
                  value={stats.pending_approval || 3281}
                  icon={<MetricIcons.Crosshair />}
                  badge="+31%"
                  badgeType="warning"
                  onClick={() => setActiveTab("approvals")}
                />
              </section>

              {/* Middle Row: Analytics & Charts (Breakdown, Action Volume, Governance Enforcement Speedometer) */}
              <GovernanceAnalytics
                stats={stats}
                activitiesCount={activities.length}
              />

              {/* Bottom Row: Alert Queue (Recent Agent Activity Table) + Operations Card */}
              <LiveInterceptionFeed
                activities={activities}
                onSelectAgent={(aid) => setSelectedAgentId(aid)}
                isLive={isWsConnected}
              />

              {/* Section: Human Approvals Queue */}
              <ApprovalQueueWidget tenantId={selectedTenant || undefined} />

              {/* Section: Infrastructure Health & Readiness */}
              <SystemReadinessWidget />
            </>
          )}

          {/* TAB 2: AGENTS */}
          {activeTab === "agents" && (
            <section
              className="glass-panel"
              style={{
                padding: "20px 22px",
                background: "#18171B",
                border: "1px solid #262529",
                borderRadius: "20px",
              }}
            >
              <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: "16px" }}>
                <div>
                  <h2 style={{ fontSize: "1rem", fontWeight: 700, color: "#F5F5F5", margin: 0 }}>
                    Registered Agent Identities
                  </h2>
                  <div style={{ fontSize: "0.75rem", color: "#858585", marginTop: "3px", maxWidth: "70ch" }}>
                    Each agent possesses cryptographic credentials tied to an organization and project scope.
                  </div>
                </div>
                <div style={{ display: "flex", alignItems: "center", gap: "8px" }}>
                  <button className="btn btn-ghost" onClick={fetchAgents} style={{ fontSize: "0.75rem", padding: "5px 12px" }}>
                    Refresh
                  </button>
                  <button
                    id="btn-purge-inactive-agents"
                    className="btn btn-ghost"
                    onClick={handlePurgeInactiveAgents}
                    style={{ fontSize: "0.75rem", padding: "5px 12px", color: "#FF492F", borderColor: "rgba(255, 73, 47, 0.3)" }}
                    title="Human Operator only: Purge all suspended/revoked agent identities"
                  >
                    Purge Inactive
                  </button>
                  <button
                    id="btn-add-agent"
                    className="btn btn-primary"
                    onClick={() => setIsAddAgentModalOpen(true)}
                    style={{ fontSize: "0.75rem", padding: "5px 14px" }}
                  >
                    + Add Agent
                  </button>
                </div>
              </div>

              {agents.length === 0 ? (
                <div className="empty-state">
                  <p style={{ marginBottom: "12px", fontSize: "0.8125rem" }}>
                    No agents registered yet for this tenant scope. Click &quot;+ Add Agent&quot; above to register and connect your first external agent.
                  </p>
                  <button
                    id="btn-add-agent-empty"
                    className="btn btn-primary"
                    onClick={() => setIsAddAgentModalOpen(true)}
                    style={{ fontSize: "0.75rem", padding: "6px 16px" }}
                  >
                    + Add Agent
                  </button>
                </div>
              ) : (
                <div style={{ overflowX: "auto", border: "1px solid #262529", borderRadius: "14px" }}>
                  <table style={{ width: "100%", borderCollapse: "collapse", fontSize: "0.8125rem", textAlign: "left" }}>
                    <thead>
                      <tr style={{ background: "#141316", color: "#858585", borderBottom: "1px solid #262529" }}>
                        <th style={{ padding: "10px 14px" }}>Agent</th>
                        <th style={{ padding: "10px 14px" }}>Framework</th>
                        <th style={{ padding: "10px 14px" }}>Environment</th>
                        <th style={{ padding: "10px 14px" }}>Status</th>
                        <th style={{ padding: "10px 14px" }}>Connection</th>
                        <th style={{ padding: "10px 14px" }}>Last Activity</th>
                        <th style={{ padding: "10px 14px" }}>Actions</th>
                        <th style={{ padding: "10px 14px", textAlign: "right" }}>Governance</th>
                      </tr>
                    </thead>
                    <tbody>
                      {agents.map((ag) => (
                        <tr key={ag.agent_id} style={{ borderBottom: "1px solid rgba(255, 255, 255, 0.04)" }}>
                          <td style={{ padding: "12px 14px" }}>
                            <div style={{ fontWeight: 600, color: "#F5F5F5" }}>{ag.name}</div>
                            <span className="code-pill" style={{ fontSize: "0.6875rem", marginTop: "2px" }}>{ag.agent_id}</span>
                          </td>
                          <td style={{ padding: "12px 14px" }}>
                            <span
                              style={{
                                padding: "2px 8px",
                                borderRadius: "8px",
                                fontSize: "0.6875rem",
                                fontWeight: 700,
                                background: ag.framework?.toLowerCase() === "langgraph"
                                  ? "rgba(16, 185, 129, 0.14)"
                                  : ag.framework?.toLowerCase() === "openhands"
                                  ? "rgba(255, 112, 67, 0.14)"
                                  : "rgba(137, 85, 255, 0.14)",
                                color: ag.framework?.toLowerCase() === "langgraph"
                                  ? "#10B981"
                                  : ag.framework?.toLowerCase() === "openhands"
                                  ? "#FF7043"
                                  : "#A78BFA",
                                border: "1px solid rgba(255, 255, 255, 0.06)",
                                textTransform: "uppercase",
                                fontFamily: "var(--font-mono)",
                              }}
                            >
                              {ag.framework || "custom"}
                            </span>
                          </td>
                          <td style={{ padding: "12px 14px" }}>
                            <span
                              style={{
                                padding: "2px 6px",
                                borderRadius: "6px",
                                fontSize: "0.6875rem",
                                background: "#141316",
                                border: "1px solid #262529",
                                color: "#FF7043",
                                textTransform: "uppercase",
                                fontFamily: "var(--font-mono)",
                              }}
                            >
                              {ag.environment}
                            </span>
                          </td>
                          <td style={{ padding: "12px 14px" }}>
                            <span className={`badge ${ag.status === "active" ? "badge-allow" : "badge-block"}`}>
                              {ag.status}
                            </span>
                          </td>
                          <td style={{ padding: "12px 14px" }}>
                            <span
                              style={{
                                display: "inline-flex",
                                alignItems: "center",
                                gap: "6px",
                                fontSize: "0.75rem",
                                fontFamily: "var(--font-mono)",
                                color: ag.connection_status === "connected" ? "#10B981" : "#858585",
                              }}
                            >
                              <span
                                style={{
                                  width: "6px",
                                  height: "6px",
                                  borderRadius: "50%",
                                  background: ag.connection_status === "connected" ? "#10B981" : "#52525A",
                                }}
                              />
                              {ag.connection_status || "registered"}
                            </span>
                          </td>
                          <td style={{ padding: "12px 14px", color: "#858585", fontFamily: "var(--font-mono)", fontSize: "0.75rem" }}>
                            {ag.last_activity ? new Date(ag.last_activity).toLocaleTimeString() : "Never"}
                          </td>
                          <td style={{ padding: "12px 14px", fontFamily: "var(--font-mono)", color: "#F5F5F5", fontWeight: 600 }}>
                            {ag.action_count}
                          </td>
                          <td style={{ padding: "12px 14px", textAlign: "right" }}>
                            <div style={{ display: "inline-flex", gap: "6px" }}>
                              <button
                                className="btn btn-ghost"
                                onClick={() => setSelectedAgentId(ag.agent_id)}
                                style={{ padding: "4px 10px", fontSize: "0.75rem" }}
                              >
                                View Details
                              </button>
                              <button
                                className={ag.status === "active" ? "btn btn-danger" : "btn btn-primary"}
                                onClick={() => toggleAgentStatus(ag.agent_id, ag.status)}
                                style={{ padding: "4px 10px", fontSize: "0.75rem" }}
                              >
                                {ag.status === "active" ? "Suspend" : "Activate"}
                              </button>
                              <button
                                id={`btn-remove-agent-${ag.agent_id}`}
                                className="btn btn-ghost"
                                onClick={() => handleRemoveAgent(ag)}
                                style={{
                                  padding: "4px 8px",
                                  fontSize: "0.75rem",
                                  color: "#FF492F",
                                  border: "1px solid rgba(255, 73, 47, 0.3)",
                                }}
                                title="Human Operator only: Permanently remove agent"
                              >
                                Remove
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
            <section
              className="glass-panel"
              style={{
                padding: "20px 22px",
                background: "#18171B",
                border: "1px solid #262529",
                borderRadius: "20px",
              }}
            >
              <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: "16px" }}>
                <div>
                  <h2 style={{ fontSize: "1rem", fontWeight: 700, color: "#F5F5F5", margin: 0 }}>
                    Active &amp; Historical Runtime Sessions
                  </h2>
                  <div style={{ fontSize: "0.75rem", color: "#858585", marginTop: "3px", maxWidth: "70ch" }}>
                    Sessions are established via authenticated credentials. Actions must belong to an active session.
                  </div>
                </div>
                <div style={{ display: "flex", alignItems: "center", gap: "8px" }}>
                  <button className="btn btn-ghost" onClick={fetchSessions} style={{ fontSize: "0.75rem", padding: "5px 12px" }}>
                    Refresh
                  </button>
                  <button
                    id="btn-clear-sessions"
                    className="btn btn-danger"
                    onClick={handleClearSessions}
                    style={{ fontSize: "0.75rem", padding: "5px 12px" }}
                    title="Human Operator only: Clear session history"
                  >
                    Clear History
                  </button>
                </div>
              </div>

              {sessions.length === 0 ? (
                <div className="empty-state">
                  No sessions recorded yet.
                </div>
              ) : (
                <div style={{ overflowX: "auto", border: "1px solid #262529", borderRadius: "14px" }}>
                  <table style={{ width: "100%", borderCollapse: "collapse", fontSize: "0.8125rem", textAlign: "left" }}>
                    <thead>
                      <tr style={{ background: "#141316", color: "#858585", borderBottom: "1px solid #262529" }}>
                        <th style={{ padding: "10px 14px" }}>Session ID</th>
                        <th style={{ padding: "10px 14px" }}>Agent Identity</th>
                        <th style={{ padding: "10px 14px" }}>Organization / Project</th>
                        <th style={{ padding: "10px 14px" }}>Status</th>
                        <th style={{ padding: "10px 14px" }}>Started At</th>
                      </tr>
                    </thead>
                    <tbody>
                      {sessions.map((sess) => (
                        <tr key={sess.session_id} style={{ borderBottom: "1px solid rgba(255, 255, 255, 0.04)" }}>
                          <td style={{ padding: "12px 14px", fontFamily: "var(--font-mono)", color: "#FF7043", fontSize: "0.75rem" }}>
                            {sess.session_id}
                          </td>
                          <td style={{ padding: "12px 14px", color: "#F5F5F5", fontWeight: 600 }}>
                            {sess.agent_id}
                          </td>
                          <td style={{ padding: "12px 14px", color: "#858585", fontSize: "0.75rem" }}>
                            {sess.organization_id} / {sess.project_id}
                          </td>
                          <td style={{ padding: "12px 14px" }}>
                            <span className={`badge ${sess.status === "active" ? "badge-allow" : "badge-block"}`}>
                              {sess.status}
                            </span>
                          </td>
                          <td style={{ padding: "12px 14px", color: "#858585", fontFamily: "var(--font-mono)", fontSize: "0.75rem" }}>
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

          {/* TAB 4: RUNTIME ACTIVITY STREAM */}
          {activeTab === "activity" && (
            <section
              className="glass-panel"
              style={{
                padding: "20px 22px",
                background: "#18171B",
                border: "1px solid #262529",
                borderRadius: "20px",
              }}
            >
              <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: "16px" }}>
                <div>
                  <h2 style={{ fontSize: "1rem", fontWeight: 700, color: "#F5F5F5", margin: 0, display: "flex", alignItems: "center", gap: "10px" }}>
                    <span>Runtime Security Activity Stream</span>
                    <span className={`status-dot ${isWsConnected ? "status-dot-active status-dot-pulse" : ""}`} />
                  </h2>
                  <div style={{ fontSize: "0.75rem", color: "#858585", marginTop: "3px", maxWidth: "70ch" }}>
                    Pre-execution policy evaluations with cryptographically deterministic action digests.
                  </div>
                </div>
                <div style={{ display: "flex", alignItems: "center", gap: "8px" }}>
                  {selectedActivities.size > 0 && (
                    <button
                      id="btn-delete-selected-activities"
                      className="btn btn-danger"
                      onClick={handleDeleteSelectedActivities}
                      style={{ fontSize: "0.75rem", padding: "5px 12px" }}
                      title="Delete specifically selected activity records"
                    >
                      Delete Selected ({selectedActivities.size})
                    </button>
                  )}
                  <button className="btn btn-ghost" onClick={fetchActivities} style={{ fontSize: "0.75rem", padding: "5px 12px" }}>
                    Refresh
                  </button>
                  <button
                    id="btn-clear-runtime-activity"
                    className="btn btn-danger"
                    onClick={handleClearRuntimeActivity}
                    style={{ fontSize: "0.75rem", padding: "5px 12px" }}
                    title="Human Operator only: Clear mediated activity stream"
                  >
                    Clear History
                  </button>
                </div>
              </div>

              {activities.length === 0 ? (
                <div className="empty-state">
                  No mediated activity recorded yet.
                </div>
              ) : (
                <div style={{ overflowX: "auto", border: "1px solid #262529", borderRadius: "14px" }}>
                  <table style={{ width: "100%", borderCollapse: "collapse", fontSize: "0.8125rem", textAlign: "left" }}>
                    <thead>
                      <tr style={{ background: "#141316", color: "#858585", borderBottom: "1px solid #262529" }}>
                        <th style={{ padding: "10px 14px", width: "36px", textAlign: "center" }}>
                          <input
                            type="checkbox"
                            id="select-all-activities-checkbox"
                            checked={isAllActivitiesSelected}
                            onChange={toggleSelectAllActivities}
                            style={{ cursor: "pointer", width: "15px", height: "15px", accentColor: "#FF492F" }}
                            title={isAllActivitiesSelected ? "Deselect all" : "Select all activities"}
                            aria-label="Select all activities"
                          />
                        </th>
                        <th style={{ padding: "10px 14px" }}>Time</th>
                        <th style={{ padding: "10px 14px" }}>Agent</th>
                        <th style={{ padding: "10px 14px" }}>Tool &amp; Op</th>
                        <th style={{ padding: "10px 14px" }}>Resource</th>
                        <th style={{ padding: "10px 14px" }}>Decision</th>
                        <th style={{ padding: "10px 14px" }}>Status</th>
                        <th style={{ padding: "10px 14px" }}>Action Digest</th>
                      </tr>
                    </thead>
                    <tbody>
                      {activities.map((act) => (
                        <tr
                          key={act.action_id}
                          style={{
                            borderBottom: "1px solid rgba(255, 255, 255, 0.04)",
                            background: selectedActivities.has(act.action_id) ? "rgba(255, 73, 47, 0.08)" : undefined,
                            transition: "background 0.15s ease",
                          }}
                        >
                          <td style={{ padding: "10px 14px", width: "36px", textAlign: "center" }}>
                            <input
                              type="checkbox"
                              id={`select-activity-${act.action_id}`}
                              checked={selectedActivities.has(act.action_id)}
                              onChange={() => toggleSelectActivity(act.action_id)}
                              style={{ cursor: "pointer", width: "15px", height: "15px", accentColor: "#FF492F" }}
                              aria-label={`Select activity ${act.action_id}`}
                            />
                          </td>
                          <td style={{ padding: "10px 14px", color: "#858585", fontFamily: "var(--font-mono)", fontSize: "0.75rem" }}>
                            {new Date(act.timestamp).toLocaleTimeString()}
                          </td>
                          <td style={{ padding: "10px 14px", color: "#F5F5F5", fontWeight: 600 }}>
                            <button
                              onClick={() => setSelectedAgentId(act.agent_id)}
                              style={{ background: "none", border: "none", color: "#F5F5F5", cursor: "pointer", textDecoration: "underline", fontSize: "inherit", padding: 0 }}
                            >
                              {act.agent_id}
                            </button>
                          </td>
                          <td style={{ padding: "10px 14px" }}>
                            <span className="code-pill">{act.tool}.{act.operation}</span>
                          </td>
                          <td style={{ padding: "10px 14px", color: "#A1A1A8" }}>
                            {act.resource}
                          </td>
                          <td style={{ padding: "10px 14px" }}>
                            <span className={`badge ${getBadgeClass(act.decision)}`}>
                              {act.decision}
                            </span>
                          </td>
                          <td
                            style={{
                              padding: "10px 14px",
                              fontFamily: "var(--font-mono)",
                              fontSize: "0.75rem",
                              fontWeight: 600,
                              color:
                                act.execution_status === "EXECUTED"
                                  ? "#10B981"
                                  : act.execution_status === "BLOCKED"
                                  ? "#FF492F"
                                  : "#FFA726",
                            }}
                          >
                            {act.execution_status}
                          </td>
                          <td style={{ padding: "10px 14px", fontFamily: "var(--font-mono)", fontSize: "0.725rem", color: "#A78BFA" }}>
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
            <PolicyEnforcementView initialRules={policies} />
          )}

          {/* TAB: APPROVALS */}
          {activeTab === "approvals" && <ApprovalQueueWidget tenantId={selectedTenant || undefined} />}

          {/* TAB: AUDIT LEDGER */}
          {activeTab === "audit" && <AuditLedgerWidget tenantId={selectedTenant || undefined} />}

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

      {/* Human Operator Purge Confirmation Modal */}
      <HumanPurgeModal
        isOpen={purgeModal.isOpen}
        onClose={() => setPurgeModal((prev) => ({ ...prev, isOpen: false }))}
        title={purgeModal.title}
        targetDescription={purgeModal.targetDescription}
        warningNote={purgeModal.warningNote}
        actionButtonText={purgeModal.actionButtonText}
        onConfirm={purgeModal.onConfirm}
      />
    </div>
  );
}
