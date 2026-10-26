"use client";

import React from "react";

export interface ActivityItem {
  action_id: string;
  timestamp: string;
  agent_id: string;
  tool: string;
  operation: string;
  resource: string;
  decision: "ALLOW" | "BLOCK" | "REQUIRE_APPROVAL" | "SUSPEND" | string;
  execution_status: string;
  reason_code?: string;
  action_digest?: string;
  correlation_id?: string;
}

interface LiveInterceptionFeedProps {
  activities: ActivityItem[];
  onSelectAgent?: (agentId: string) => void;
  isLive?: boolean;
}

const getBadgeClass = (decision: string) => {
  switch (decision) {
    case "ALLOW":            return "badge-allow";
    case "BLOCK":            return "badge-block";
    case "REQUIRE_APPROVAL": return "badge-approval";
    default:                 return "badge-suspend";
  }
};

const getExecColor = (status: string) => {
  if (status === "EXECUTED") return "var(--success-fg)";
  if (status === "BLOCKED")  return "var(--danger-fg)";
  return "var(--warning-fg)";
};

export const LiveInterceptionFeed: React.FC<LiveInterceptionFeedProps> = ({
  activities,
  onSelectAgent,
  isLive = true,
}) => {
  return (
    <section id="live-interception-section" className="glass-panel" style={{ padding: "18px 20px" }}>
      {/* ── Panel header ── */}
      <div
        style={{
          display: "flex",
          alignItems: "center",
          justifyContent: "space-between",
          marginBottom: "16px",
          gap: "12px",
          flexWrap: "wrap",
        }}
      >
        <div style={{ display: "flex", alignItems: "center", gap: "10px" }}>
          <span
            className={`status-dot ${isLive ? "status-dot-active status-dot-pulse" : ""}`}
            style={{ borderRadius: "50%" }}
          />
          <h2 className="panel-title">Pre-Execution Interception &amp; Enforcement Stream</h2>
        </div>
        <span
          style={{
            fontSize: "0.625rem",
            color: isLive ? "var(--success-fg)" : "var(--text-muted)",
            fontFamily: "var(--font-mono)",
            letterSpacing: "0.07em",
            textTransform: "uppercase",
            background: isLive ? "var(--success-bg)" : "var(--bg-elevated)",
            border: `1px solid ${isLive ? "var(--success-border)" : "var(--border-primary)"}`,
            padding: "2px 8px",
            borderRadius: "4px",
          }}
        >
          {isLive ? "REALTIME · WS" : "POLLING MODE"}
        </span>
      </div>

      {/* ── Empty state ── */}
      {activities.length === 0 ? (
        <div className="empty-state">
          No mediated actions logged yet. Realtime events will stream here as connected agents submit
          operations through the governance gateway.
        </div>
      ) : (
        <div
          style={{
            border: "1px solid #eef2f6",
            borderRadius: "12px",
            overflow: "hidden",
          }}
        >
          {/* Column header */}
          <div
            style={{
              display: "grid",
              gridTemplateColumns: "76px 160px 180px 1fr 140px 110px",
              padding: "9px 16px",
              background: "#f8fafc",
              borderBottom: "1px solid #eef2f6",
              gap: "12px",
            }}
          >
            {["TIME", "AGENT", "TOOL · OP", "RESOURCE / DIGEST", "DECISION", "STATUS"].map((h) => (
              <span
                key={h}
                style={{
                  fontSize: "0.625rem",
                  fontFamily: "var(--font-mono)",
                  fontWeight: 600,
                  color: "#64748b",
                  textTransform: "uppercase",
                  letterSpacing: "0.07em",
                }}
              >
                {h}
              </span>
            ))}
          </div>

          {/* Rows */}
          {activities.slice(0, 15).map((item) => {
            const timeStr = item.timestamp
              ? new Date(item.timestamp).toLocaleTimeString()
              : "just now";

            return (
              <div
                key={item.action_id}
                id={`feed-${item.action_id}`}
                style={{
                  display: "grid",
                  gridTemplateColumns: "76px 160px 180px 1fr 140px 110px",
                  alignItems: "center",
                  gap: "12px",
                  padding: "10px 16px",
                  borderBottom: "1px solid #f1f5f9",
                  fontSize: "0.8125rem",
                  transition: "background 0.1s ease",
                  background: "#ffffff",
                }}
                onMouseEnter={(e) =>
                  ((e.currentTarget as HTMLDivElement).style.background = "#f8fafc")
                }
                onMouseLeave={(e) =>
                  ((e.currentTarget as HTMLDivElement).style.background = "#ffffff")
                }
              >
                {/* Time */}
                <div
                  style={{
                    color: "var(--text-muted)",
                    fontFamily: "var(--font-mono)",
                    fontSize: "0.725rem",
                  }}
                >
                  {timeStr}
                </div>

                {/* Agent */}
                <div style={{ minWidth: 0 }}>
                  <button
                    onClick={() => onSelectAgent && onSelectAgent(item.agent_id)}
                    style={{
                      background: "none",
                      border: "none",
                      padding: 0,
                      color: "var(--text-primary)",
                      fontWeight: 500,
                      fontSize: "0.8125rem",
                      cursor: onSelectAgent ? "pointer" : "default",
                      textAlign: "left",
                      overflow: "hidden",
                      textOverflow: "ellipsis",
                      whiteSpace: "nowrap",
                      maxWidth: "100%",
                      display: "block",
                      textDecoration: onSelectAgent ? "underline" : "none",
                      textDecorationColor: "var(--border-secondary)",
                    }}
                  >
                    {item.agent_id}
                  </button>
                  <div
                    style={{
                      fontSize: "0.6875rem",
                      color: "var(--text-muted)",
                      fontFamily: "var(--font-mono)",
                      overflow: "hidden",
                      textOverflow: "ellipsis",
                      whiteSpace: "nowrap",
                    }}
                  >
                    {item.correlation_id || item.action_id.slice(0, 12)}
                  </div>
                </div>

                {/* Tool · Op */}
                <div>
                  <span className="code-pill">
                    {item.tool}.{item.operation}
                  </span>
                </div>

                {/* Resource / Digest */}
                <div style={{ minWidth: 0 }}>
                  <div
                    style={{
                      color: "var(--text-secondary)",
                      whiteSpace: "nowrap",
                      overflow: "hidden",
                      textOverflow: "ellipsis",
                      fontFamily: "var(--font-mono)",
                      fontSize: "0.725rem",
                    }}
                  >
                    {item.resource}
                  </div>
                  <div
                    style={{
                      color: "var(--text-muted)",
                      fontSize: "0.6875rem",
                      marginTop: "2px",
                      fontFamily: "var(--font-mono)",
                    }}
                  >
                    {item.reason_code
                      ? `Code: ${item.reason_code}`
                      : `Digest: ${item.action_digest ? item.action_digest.slice(0, 14) + "…" : "verified"}`}
                  </div>
                </div>

                {/* Decision badge */}
                <div>
                  <span className={`badge ${getBadgeClass(item.decision)}`}>
                    {item.decision}
                  </span>
                </div>

                {/* Execution status */}
                <div
                  style={{
                    fontFamily: "var(--font-mono)",
                    fontSize: "0.725rem",
                    fontWeight: 600,
                    color: getExecColor(item.execution_status),
                    textAlign: "right",
                    letterSpacing: "0.03em",
                  }}
                >
                  {item.execution_status}
                </div>
              </div>
            );
          })}
        </div>
      )}
    </section>
  );
};
