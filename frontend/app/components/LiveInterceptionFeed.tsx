"use client";

import React, { useState } from "react";

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

/* ── Segmented Risk Meter matching Reference ("Risk Lvl") ── */
const RiskLevelMeter: React.FC<{ decision: string }> = ({ decision }) => {
  let activeCount = 3;
  let activeColor = "#FF9800"; // orange

  if (decision === "BLOCK") {
    activeCount = 8;
    activeColor = "#FF492F"; // red
  } else if (decision === "SUSPEND") {
    activeCount = 10;
    activeColor = "#8955FF"; // purple
  } else if (decision === "REQUIRE_APPROVAL") {
    activeCount = 5;
    activeColor = "#FF7043"; // warm orange
  } else if (decision === "ALLOW") {
    activeCount = 2;
    activeColor = "#10B981"; // green
  }

  return (
    <div style={{ display: "flex", alignItems: "center", gap: "2px" }} title={`Risk Level: ${decision}`}>
      {Array.from({ length: 10 }).map((_, idx) => {
        const isActive = idx < activeCount;
        let segColor = activeColor;
        if (isActive && idx >= 7) segColor = "#FF492F"; // peak segments turn fiery red

        return (
          <span
            key={idx}
            style={{
              width: "3px",
              height: "12px",
              borderRadius: "1px",
              background: isActive ? segColor : "#242328",
              boxShadow: isActive ? `0 0 4px ${segColor}` : "none",
              transition: "background 0.2s ease",
            }}
          />
        );
      })}
    </div>
  );
};

export const LiveInterceptionFeed: React.FC<LiveInterceptionFeedProps> = ({
  activities,
  onSelectAgent,
  isLive = true,
}) => {
  const [filterPeriod, setFilterPeriod] = useState<string>("Week");

  const getStatusBadge = (decision: string) => {
    switch (decision) {
      case "ALLOW":
        return {
          label: "Allow",
          border: "rgba(16, 185, 129, 0.4)",
          color: "#10B981",
          bg: "rgba(16, 185, 129, 0.08)",
        };
      case "BLOCK":
        return {
          label: "Critical",
          border: "rgba(255, 73, 47, 0.45)",
          color: "#FF492F",
          bg: "rgba(255, 73, 47, 0.1)",
        };
      case "REQUIRE_APPROVAL":
        return {
          label: "Medium",
          border: "rgba(255, 152, 0, 0.4)",
          color: "#FFA726",
          bg: "rgba(255, 152, 0, 0.08)",
        };
      case "SUSPEND":
        return {
          label: "Suspended",
          border: "rgba(137, 85, 255, 0.45)",
          color: "#A78BFA",
          bg: "rgba(137, 85, 255, 0.1)",
        };
      default:
        return {
          label: decision,
          border: "#333238",
          color: "#A1A1A8",
          bg: "#1C1B1F",
        };
    }
  };

  const formatShortId = (actId: string) => {
    const cleaned = actId.replace(/^act_|^evt_/, "");
    return `#INC-${cleaned.slice(0, 4).toUpperCase()}`;
  };

  return (
    <div
      style={{
        display: "grid",
        gridTemplateColumns: "2fr 1fr",
        gap: "16px",
        alignItems: "stretch",
      }}
      className="alert-queue-grid"
    >
      {/* ─────────────────────────────────────────────────────────────
          LEFT: "Alert Queue" (Recent Agent Activity Table matching Reference)
      ────────────────────────────────────────────────────────────── */}
      <div
        className="glass-panel"
        style={{
          padding: "20px 22px",
          background: "#18171B",
          border: "1px solid #262529",
          borderRadius: "20px",
          minHeight: "260px",
          display: "flex",
          flexDirection: "column",
        }}
      >
        {/* Header */}
        <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: "14px" }}>
          <div>
            <div style={{ display: "flex", alignItems: "center", gap: "8px" }}>
              <h3 style={{ fontSize: "0.9375rem", fontWeight: 600, color: "#F5F5F5", margin: 0 }}>
                Alert Queue
              </h3>
              <span
                className={`status-dot ${isLive ? "status-dot-active status-dot-pulse" : ""}`}
                title={isLive ? "WebSocket Live Stream" : "Polling Mode"}
              />
            </div>
            <span style={{ fontSize: "0.6875rem", color: "#858585" }}>
              Total Alerts (Today) · {activities.length} Interceptions
            </span>
          </div>

          <div
            style={{
              display: "flex",
              alignItems: "center",
              background: "#141316",
              border: "1px solid #262529",
              borderRadius: "12px",
              padding: "2px 8px",
            }}
          >
            <select
              value={filterPeriod}
              onChange={(e) => setFilterPeriod(e.target.value)}
              style={{
                background: "transparent",
                color: "#F5F5F5",
                border: "none",
                fontSize: "0.6875rem",
                fontWeight: 600,
                outline: "none",
                cursor: "pointer",
              }}
            >
              <option value="Today" style={{ background: "#1C1B1F" }}>Today</option>
              <option value="Week" style={{ background: "#1C1B1F" }}>Week</option>
              <option value="Month" style={{ background: "#1C1B1F" }}>Month</option>
            </select>
          </div>
        </div>

        {/* Table Content */}
        {activities.length === 0 ? (
          <div className="empty-state" style={{ margin: "auto 0" }}>
            No intercepted activity recorded yet. Autonomous agents will stream live events here.
          </div>
        ) : (
          <div style={{ overflowX: "auto", flex: 1 }}>
            <table style={{ width: "100%", borderCollapse: "collapse", textAlign: "left" }}>
              <thead>
                <tr style={{ color: "#73737C", borderBottom: "1px solid #262529" }}>
                  <th style={{ padding: "8px 10px", fontSize: "0.6875rem", fontWeight: 600, background: "transparent" }}>Time</th>
                  <th style={{ padding: "8px 10px", fontSize: "0.6875rem", fontWeight: 600, background: "transparent" }}>Alert ID</th>
                  <th style={{ padding: "8px 10px", fontSize: "0.6875rem", fontWeight: 600, background: "transparent" }}>Severity / Component</th>
                  <th style={{ padding: "8px 10px", fontSize: "0.6875rem", fontWeight: 600, background: "transparent" }}>Risk Lvl</th>
                  <th style={{ padding: "8px 10px", fontSize: "0.6875rem", fontWeight: 600, background: "transparent", textAlign: "right" }}>Status</th>
                </tr>
              </thead>
              <tbody>
                {activities.slice(0, 6).map((act) => {
                  const badge = getStatusBadge(act.decision);
                  const timeFormatted = new Date(act.timestamp).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', hour12: false }) + " UTC";

                  return (
                    <tr
                      key={act.action_id}
                      style={{
                        borderBottom: "1px solid rgba(255, 255, 255, 0.04)",
                        transition: "background 0.15s ease",
                      }}
                    >
                      <td style={{ padding: "9px 10px", color: "#858585", fontFamily: "var(--font-mono)", fontSize: "0.75rem", whiteSpace: "nowrap" }}>
                        {timeFormatted}
                      </td>

                      <td style={{ padding: "9px 10px", color: "#A1A1A8", fontFamily: "var(--font-mono)", fontSize: "0.75rem", fontWeight: 500 }}>
                        {formatShortId(act.action_id)}
                      </td>

                      <td style={{ padding: "9px 10px" }}>
                        <div style={{ display: "flex", alignItems: "center", gap: "6px" }}>
                          <span style={{ color: "#F5F5F5", fontSize: "0.8125rem", fontWeight: 500 }}>
                            {act.tool}—{act.operation}
                          </span>
                          <span style={{ fontSize: "0.6875rem", color: "#5E5E66" }}>
                            ({act.agent_id})
                          </span>
                        </div>
                      </td>

                      <td style={{ padding: "9px 10px" }}>
                        <RiskLevelMeter decision={act.decision} />
                      </td>

                      <td style={{ padding: "9px 10px", textAlign: "right" }}>
                        <span
                          style={{
                            display: "inline-flex",
                            alignItems: "center",
                            gap: "4px",
                            padding: "2px 8px",
                            borderRadius: "14px",
                            fontSize: "0.6875rem",
                            fontWeight: 600,
                            fontFamily: "var(--font-mono)",
                            border: `1px solid ${badge.border}`,
                            color: badge.color,
                            background: badge.bg,
                          }}
                        >
                          <span style={{ width: "4px", height: "4px", borderRadius: "50%", background: badge.color }} />
                          {badge.label}
                        </span>
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        )}
      </div>

      {/* ─────────────────────────────────────────────────────────────
          RIGHT: "Operations" (Live Telemetry & Spectrum Flow matching Reference)
      ────────────────────────────────────────────────────────────── */}
      <div
        className="glass-panel"
        style={{
          padding: "20px 22px",
          background: "#18171B",
          border: "1px solid #262529",
          borderRadius: "20px",
          display: "flex",
          flexDirection: "column",
          justifyContent: "space-between",
          minHeight: "260px",
          position: "relative",
          overflow: "hidden",
        }}
      >
        {/* Header */}
        <div>
          <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between" }}>
            <h3 style={{ fontSize: "0.9375rem", fontWeight: 600, color: "#F5F5F5", margin: 0 }}>
              Operations
            </h3>
            <div style={{ color: "#858585", cursor: "pointer", fontSize: "1.1rem" }}>
              •••
            </div>
          </div>
          <div style={{ display: "flex", alignItems: "baseline", gap: "8px", marginTop: "4px" }}>
            <span style={{ fontSize: "1.6rem", fontWeight: 700, color: "#F5F5F5", fontFamily: "var(--font-mono)" }}>
              {activities.length ? activities.length * 12 : 850}
            </span>
            <span
              style={{
                fontSize: "0.625rem",
                color: "#FF7043",
                background: "#222126",
                border: "1px solid #333238",
                padding: "1px 6px",
                borderRadius: "10px",
                fontWeight: 700,
              }}
            >
              • 36%
            </span>
          </div>
        </div>

        {/* Equalizer Spectrum Bars & Flowing Line Chart matching Reference */}
        <div style={{ position: "relative", width: "100%", height: "130px", marginTop: "10px" }}>
          <svg viewBox="0 0 300 120" style={{ width: "100%", height: "100%", overflow: "visible" }} preserveAspectRatio="none">
            <defs>
              <linearGradient id="opLineGrad" x1="0%" y1="0%" x2="100%" y2="0%">
                <stop offset="0%" stopColor="#8955FF" />
                <stop offset="50%" stopColor="#FF492F" />
                <stop offset="100%" stopColor="#FF7043" />
              </linearGradient>

              <linearGradient id="spectrumBarGrad" x1="0%" y1="0%" x2="0%" y2="100%">
                <stop offset="0%" stopColor="#FF492F" stopOpacity="0.8" />
                <stop offset="100%" stopColor="#FF492F" stopOpacity="0.05" />
              </linearGradient>
            </defs>

            {/* Glowing Vertical Equalizer Spectrum Bars in Background */}
            {Array.from({ length: 28 }).map((_, i) => {
              const x = i * 11;
              const h = Math.sin(i * 0.35) * 35 + 40;
              return (
                <rect
                  key={i}
                  x={x}
                  y={110 - h}
                  width="2.5"
                  height={h}
                  fill="url(#spectrumBarGrad)"
                  rx="1"
                />
              );
            })}

            {/* Glowing Foreground Curve */}
            <path
              d="M 0,90 Q 50,85 90,75 T 180,50 T 240,65 T 300,40"
              fill="none"
              stroke="url(#opLineGrad)"
              strokeWidth="2.5"
              strokeLinecap="round"
              style={{ filter: "drop-shadow(0 0 6px rgba(255, 73, 47, 0.45))" }}
            />

            {/* Active pointer dot */}
            <circle cx="180" cy="50" r="3.5" fill="#FFFFFF" stroke="#FF492F" strokeWidth="2" />
          </svg>
        </div>

        {/* Footer */}
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", fontSize: "0.6875rem", color: "#858585" }}>
          <span>Throughput: Realtime</span>
          <span style={{ color: "#10B981", fontWeight: 600 }}>Optimal</span>
        </div>
      </div>
    </div>
  );
};
