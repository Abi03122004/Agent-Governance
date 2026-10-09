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

export const LiveInterceptionFeed: React.FC<LiveInterceptionFeedProps> = ({
  activities,
  onSelectAgent,
  isLive = true,
}) => {
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
    <section id="live-interception-section" className="glass-panel" style={{ padding: "18px 20px" }}>
      <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: "14px" }}>
        <div style={{ display: "flex", alignItems: "center", gap: "8px" }}>
          <span className={`status-dot ${isLive ? "status-dot-active status-dot-pulse" : ""}`} />
          <h2 style={{ fontSize: "0.95rem", fontWeight: 600, color: "var(--text-primary)" }}>
            Pre-Execution Interception & Enforcement Stream
          </h2>
        </div>
        <span style={{ fontSize: "0.6875rem", color: "var(--text-muted)", fontFamily: "var(--font-mono)", letterSpacing: "0.04em" }}>
          {isLive ? "REALTIME TELEMETRY (WS)" : "CONTROL PLANE SYNC"}
        </span>
      </div>

      {activities.length === 0 ? (
        <div style={{ textAlign: "center", padding: "36px", color: "var(--text-muted)", fontSize: "0.8125rem", border: "1px dashed var(--border-rule)", borderRadius: "3px" }}>
          No mediated actions logged yet. Run simulated agent workflows to trigger runtime interception.
        </div>
      ) : (
        <div style={{ display: "flex", flexDirection: "column", gap: "6px" }}>
          {activities.slice(0, 15).map((item) => {
            const timeStr = item.timestamp
              ? new Date(item.timestamp).toLocaleTimeString()
              : "just now";

            return (
              <div
                key={item.action_id}
                id={`feed-${item.action_id}`}
                style={{
                  background: "var(--surface-plate)",
                  border: "1px solid var(--border-subtle)",
                  borderRadius: "2px",
                  padding: "10px 14px",
                  display: "grid",
                  gridTemplateColumns: "70px 150px 170px 1fr 130px 100px",
                  alignItems: "center",
                  gap: "12px",
                  fontSize: "0.8125rem",
                  transition: "border-color 0.1s ease",
                }}
              >
                {/* Time */}
                <div style={{ color: "var(--text-muted)", fontFamily: "var(--font-mono)", fontSize: "0.75rem" }}>
                  {timeStr}
                </div>

                {/* Agent */}
                <div
                  style={{ color: "var(--text-primary)", fontWeight: 500, cursor: onSelectAgent ? "pointer" : "default" }}
                  onClick={() => onSelectAgent && onSelectAgent(item.agent_id)}
                >
                  <span style={{ textDecoration: onSelectAgent ? "underline" : "none", color: "var(--text-primary)" }}>
                    {item.agent_id}
                  </span>
                  <div style={{ fontSize: "0.6875rem", color: "var(--text-muted)", fontFamily: "var(--font-mono)" }}>
                    {item.correlation_id || item.action_id.slice(0, 12)}
                  </div>
                </div>

                {/* Tool & Operation */}
                <div>
                  <span className="code-pill">{item.tool}.{item.operation}</span>
                </div>

                {/* Resource & Reason */}
                <div style={{ minWidth: 0 }}>
                  <div
                    style={{
                      color: "var(--text-secondary)",
                      whiteSpace: "nowrap",
                      overflow: "hidden",
                      textOverflow: "ellipsis",
                      fontFamily: "var(--font-mono)",
                      fontSize: "0.75rem",
                    }}
                  >
                    Target: {item.resource}
                  </div>
                  <div style={{ color: "var(--text-muted)", fontSize: "0.6875rem", marginTop: "2px" }}>
                    {item.reason_code ? `Code: ${item.reason_code}` : `Digest: ${item.action_digest ? item.action_digest.slice(0, 16) + "..." : "verified"}`}
                  </div>
                </div>

                {/* Verdict Badge */}
                <div>
                  <span className={`badge ${getBadgeClass(item.decision)}`}>{item.decision}</span>
                </div>

                {/* Execution Status */}
                <div
                  style={{
                    textAlign: "right",
                    fontFamily: "var(--font-mono)",
                    fontSize: "0.75rem",
                    color:
                      item.execution_status === "EXECUTED"
                        ? "var(--status-allow-fg)"
                        : item.execution_status === "BLOCKED"
                        ? "var(--status-block-fg)"
                        : "var(--status-approval-fg)",
                    fontWeight: 600,
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
