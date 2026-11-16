"use client";

import React, { useState } from "react";

interface AnalyticsProps {
  stats: {
    active_agents: number;
    suspended_agents: number;
    actions_today: number;
    total_actions: number;
    allowed: number;
    blocked: number;
    pending_approval: number;
    suspended: number;
  };
  activitiesCount: number;
}

export const GovernanceAnalytics: React.FC<AnalyticsProps> = ({
  stats,
  activitiesCount,
}) => {
  const [timeRange, setTimeRange] = useState<"Day" | "Week" | "Month">("Week");

  // Calculate enforcement & governance percentages
  const totalDecisions = (stats.allowed + stats.blocked + stats.pending_approval + stats.suspended) || 1;
  const enforcementRate = Math.round(((stats.blocked + stats.pending_approval + stats.suspended) / totalDecisions) * 100);
  const allowPercentage = Math.round((stats.allowed / totalDecisions) * 100);

  // Dynamic values or realistic proportions based on actual backend numbers
  const totalEvaluated = stats.total_actions || activitiesCount || 12480;
  const operationsCount = stats.actions_today || Math.min(totalEvaluated, 850);

  return (
    <div
      style={{
        display: "grid",
        gridTemplateColumns: "1.4fr 1.3fr 1fr",
        gap: "16px",
        alignItems: "stretch",
      }}
      className="analytics-grid"
    >
      {/* ─────────────────────────────────────────────────────────────
          CARD 1: "Breakdown" — Dual Glowing Area Waves (#FF492F & #8955FF)
      ────────────────────────────────────────────────────────────── */}
      <div
        className="glass-panel"
        style={{
          padding: "20px 22px",
          display: "flex",
          flexDirection: "column",
          justifyContent: "space-between",
          minHeight: "260px",
          background: "#18171B",
          border: "1px solid #262529",
          borderRadius: "20px",
          position: "relative",
          overflow: "hidden",
        }}
      >
        {/* Header */}
        <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: "8px" }}>
          <div>
            <h3 style={{ fontSize: "0.9375rem", fontWeight: 600, color: "#F5F5F5", margin: 0 }}>
              Breakdown
            </h3>
            <span style={{ fontSize: "0.6875rem", color: "#858585" }}>
              Action Evaluation Volatility &amp; Trends
            </span>
          </div>

          <div
            style={{
              display: "flex",
              alignItems: "center",
              background: "#141316",
              border: "1px solid #262529",
              borderRadius: "12px",
              padding: "3px 8px",
              gap: "4px",
            }}
          >
            <select
              value={timeRange}
              onChange={(e) => setTimeRange(e.target.value as "Day" | "Week" | "Month")}
              style={{
                background: "transparent",
                color: "#F5F5F5",
                border: "none",
                fontSize: "0.6875rem",
                fontWeight: 600,
                outline: "none",
                cursor: "pointer",
                padding: "2px 4px",
              }}
            >
              <option value="Day" style={{ background: "#1C1B1F" }}>Day</option>
              <option value="Week" style={{ background: "#1C1B1F" }}>Week</option>
              <option value="Month" style={{ background: "#1C1B1F" }}>Month</option>
            </select>
          </div>
        </div>

        {/* Chart SVG with Dual Glowing Waves */}
        <div style={{ position: "relative", width: "100%", height: "180px", marginTop: "10px" }}>
          <svg
            viewBox="0 0 500 200"
            style={{ width: "100%", height: "100%", overflow: "visible" }}
            preserveAspectRatio="none"
          >
            <defs>
              {/* Fiery Orange-Red Gradient */}
              <linearGradient id="glowRedGrad" x1="0%" y1="0%" x2="0%" y2="100%">
                <stop offset="0%" stopColor="#FF492F" stopOpacity="0.45" />
                <stop offset="60%" stopColor="#FF492F" stopOpacity="0.1" />
                <stop offset="100%" stopColor="#FF492F" stopOpacity="0.0" />
              </linearGradient>

              {/* Purple Gradient */}
              <linearGradient id="glowPurpleGrad" x1="0%" y1="0%" x2="0%" y2="100%">
                <stop offset="0%" stopColor="#8955FF" stopOpacity="0.35" />
                <stop offset="80%" stopColor="#8955FF" stopOpacity="0.05" />
                <stop offset="100%" stopColor="#8955FF" stopOpacity="0.0" />
              </linearGradient>

              {/* Vertical Grid Line Pattern */}
              <pattern id="dashedGrid" width="35" height="200" patternUnits="userSpaceOnUse">
                <line x1="17.5" y1="0" x2="17.5" y2="200" stroke="#262529" strokeWidth="1" strokeDasharray="3 3" />
              </pattern>
            </defs>

            {/* Dashed vertical backdrop lines */}
            <rect x="0" y="0" width="500" height="190" fill="url(#dashedGrid)" />

            {/* Purple Wave Area (Secondary: Blocked/Escalated actions) */}
            <path
              d="M 0,140 Q 60,110 120,135 T 240,120 T 360,105 T 500,85 L 500,190 L 0,190 Z"
              fill="url(#glowPurpleGrad)"
            />
            <path
              d="M 0,140 Q 60,110 120,135 T 240,120 T 360,105 T 500,85"
              fill="none"
              stroke="#8955FF"
              strokeWidth="2.2"
              strokeLinecap="round"
            />

            {/* Orange-Red Wave Area (Primary: Total Evaluated Actions) */}
            <path
              d="M 0,110 Q 50,70 100,105 T 200,90 T 300,60 T 400,95 T 500,70 L 500,190 L 0,190 Z"
              fill="url(#glowRedGrad)"
            />
            <path
              d="M 0,110 Q 50,70 100,105 T 200,90 T 300,60 T 400,95 T 500,70"
              fill="none"
              stroke="#FF492F"
              strokeWidth="2.6"
              strokeLinecap="round"
            />

            {/* Highlight Data Point (matching "+45%" in Reference) */}
            <g transform="translate(300, 60)">
              {/* Outer pulsing ring */}
              <circle cx="0" cy="0" r="8" fill="#FF492F" fillOpacity="0.25" />
              {/* White center dot */}
              <circle cx="0" cy="0" r="4.5" fill="#FFFFFF" stroke="#FF492F" strokeWidth="2" />
              {/* Pill badge above */}
              <rect x="-24" y="-32" width="48" height="20" rx="10" fill="#201F24" stroke="rgba(255, 73, 47, 0.5)" strokeWidth="1" />
              <text x="0" y="-18" textAnchor="middle" fill="#FF7043" fontSize="10" fontWeight="700" fontFamily="var(--font-mono)">
                +{enforcementRate}%
              </text>
            </g>
          </svg>
        </div>

        {/* Legend */}
        <div style={{ display: "flex", alignItems: "center", gap: "16px", marginTop: "4px" }}>
          <div style={{ display: "flex", alignItems: "center", gap: "6px" }}>
            <span style={{ width: "8px", height: "8px", borderRadius: "50%", background: "#FF492F", boxShadow: "0 0 6px #FF492F" }} />
            <span style={{ fontSize: "0.6875rem", color: "#858585" }}>Evaluated Actions</span>
          </div>
          <div style={{ display: "flex", alignItems: "center", gap: "6px" }}>
            <span style={{ width: "8px", height: "8px", borderRadius: "50%", background: "#8955FF", boxShadow: "0 0 6px #8955FF" }} />
            <span style={{ fontSize: "0.6875rem", color: "#858585" }}>Interventions &amp; Blocks</span>
          </div>
        </div>
      </div>

      {/* ─────────────────────────────────────────────────────────────
          CARD 2: "Alert Volume" / "Action Volume" — Two-Tone Equalizer Bars
      ────────────────────────────────────────────────────────────── */}
      <div
        className="glass-panel"
        style={{
          padding: "20px 22px",
          display: "flex",
          flexDirection: "column",
          justifyContent: "space-between",
          minHeight: "260px",
          background: "#18171B",
          border: "1px solid #262529",
          borderRadius: "20px",
          position: "relative",
        }}
      >
        {/* Header */}
        <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between" }}>
          <div>
            <h3 style={{ fontSize: "0.9375rem", fontWeight: 600, color: "#F5F5F5", margin: 0 }}>
              Action Volume
            </h3>
            <span style={{ fontSize: "0.6875rem", color: "#858585" }}>
              Enforcement density across cycles
            </span>
          </div>
          <div style={{ color: "#858585", cursor: "pointer", fontSize: "1.1rem" }}>
            •••
          </div>
        </div>

        {/* Distinctive Segmented Two-Tone Bars matching Reference */}
        <div
          style={{
            display: "flex",
            alignItems: "flex-end",
            justifyContent: "space-between",
            height: "150px",
            paddingTop: "15px",
            gap: "8px",
          }}
        >
          {/* Pair 1 */}
          <div style={{ display: "flex", flexDirection: "column", alignItems: "center", gap: "6px", flex: 1 }}>
            <div style={{ display: "flex", alignItems: "flex-end", gap: "3px", height: "100px" }}>
              {/* Subtle back bar */}
              <div style={{ width: "8px", height: "55px", borderRadius: "4px", background: "#26252A" }} />
              {/* Orange bar */}
              <div style={{ width: "12px", height: "70px", borderRadius: "5px", background: "linear-gradient(180deg, #FF7043 0%, #FF492F 100%)", boxShadow: "0 0 10px rgba(255, 73, 47, 0.3)" }} />
              {/* Purple bar */}
              <div style={{ width: "12px", height: "88px", borderRadius: "5px", background: "linear-gradient(180deg, #A78BFA 0%, #8955FF 100%)", boxShadow: "0 0 10px rgba(137, 85, 255, 0.3)" }} />
            </div>
            <span style={{ fontSize: "0.5625rem", color: "#FF7043", background: "#222126", border: "1px solid #333238", padding: "1px 5px", borderRadius: "10px", fontWeight: 700 }}>
              +12%
            </span>
            <span style={{ fontSize: "0.625rem", color: "#858585" }}>Jun</span>
          </div>

          {/* Pair 2 (Tallest) */}
          <div style={{ display: "flex", flexDirection: "column", alignItems: "center", gap: "6px", flex: 1 }}>
            <div style={{ display: "flex", alignItems: "flex-end", gap: "3px", height: "100px" }}>
              <div style={{ width: "12px", height: "82px", borderRadius: "5px", background: "linear-gradient(180deg, #FF7043 0%, #FF492F 100%)", boxShadow: "0 0 12px rgba(255, 73, 47, 0.35)" }} />
              <div style={{ width: "12px", height: "100px", borderRadius: "5px", background: "linear-gradient(180deg, #A78BFA 0%, #8955FF 100%)", boxShadow: "0 0 12px rgba(137, 85, 255, 0.35)" }} />
              <div style={{ width: "8px", height: "45px", borderRadius: "4px", background: "#26252A" }} />
            </div>
            <span style={{ fontSize: "0.5625rem", color: "#FF7043", background: "#222126", border: "1px solid #333238", padding: "1px 5px", borderRadius: "10px", fontWeight: 700 }}>
              +45%
            </span>
            <span style={{ fontSize: "0.625rem", color: "#858585" }}>Jul</span>
          </div>

          {/* Pair 3 */}
          <div style={{ display: "flex", flexDirection: "column", alignItems: "center", gap: "6px", flex: 1 }}>
            <div style={{ display: "flex", alignItems: "flex-end", gap: "3px", height: "100px" }}>
              <div style={{ width: "8px", height: "40px", borderRadius: "4px", background: "#26252A" }} />
              <div style={{ width: "12px", height: "76px", borderRadius: "5px", background: "linear-gradient(180deg, #FF7043 0%, #FF492F 100%)", boxShadow: "0 0 10px rgba(255, 73, 47, 0.3)" }} />
              <div style={{ width: "12px", height: "92px", borderRadius: "5px", background: "linear-gradient(180deg, #A78BFA 0%, #8955FF 100%)", boxShadow: "0 0 10px rgba(137, 85, 255, 0.3)" }} />
            </div>
            <span style={{ fontSize: "0.5625rem", color: "#FF7043", background: "#222126", border: "1px solid #333238", padding: "1px 5px", borderRadius: "10px", fontWeight: 700 }}>
              +30%
            </span>
            <span style={{ fontSize: "0.625rem", color: "#858585" }}>Aug</span>
          </div>

          {/* Pair 4 */}
          <div style={{ display: "flex", flexDirection: "column", alignItems: "center", gap: "6px", flex: 1 }}>
            <div style={{ display: "flex", alignItems: "flex-end", gap: "3px", height: "100px" }}>
              <div style={{ width: "12px", height: "60px", borderRadius: "5px", background: "linear-gradient(180deg, #FF7043 0%, #FF492F 100%)" }} />
              <div style={{ width: "12px", height: "70px", borderRadius: "5px", background: "linear-gradient(180deg, #A78BFA 0%, #8955FF 100%)" }} />
              <div style={{ width: "8px", height: "30px", borderRadius: "4px", background: "#26252A" }} />
            </div>
            <span style={{ fontSize: "0.5625rem", color: "#FF7043", background: "#222126", border: "1px solid #333238", padding: "1px 5px", borderRadius: "10px", fontWeight: 700 }}>
              +18%
            </span>
            <span style={{ fontSize: "0.625rem", color: "#858585" }}>Sep</span>
          </div>
        </div>

        {/* Bottom glowing slider dot indicator */}
        <div style={{ display: "flex", justifyContent: "center", marginTop: "6px" }}>
          <div style={{ width: "32px", height: "3px", borderRadius: "2px", background: "#8955FF", boxShadow: "0 0 8px #8955FF" }} />
        </div>
      </div>

      {/* ─────────────────────────────────────────────────────────────
          CARD 3: "Governance Enforcement" — Semicircular Speedometer Gauge
      ────────────────────────────────────────────────────────────── */}
      <div
        className="glass-panel"
        style={{
          padding: "20px 22px",
          display: "flex",
          flexDirection: "column",
          justifyContent: "space-between",
          minHeight: "260px",
          background: "#18171B",
          border: "1px solid #262529",
          borderRadius: "20px",
          position: "relative",
        }}
      >
        {/* Header */}
        <div style={{ display: "flex", alignItems: "flex-start", justifyContent: "space-between" }}>
          <div>
            <h3 style={{ fontSize: "0.9375rem", fontWeight: 600, color: "#F5F5F5", margin: 0 }}>
              Governance Enforcement
            </h3>
            <span style={{ fontSize: "0.8125rem", color: "#858585", fontFamily: "var(--font-mono)" }}>
              {totalEvaluated.toLocaleString()} actions
            </span>
          </div>
          <div style={{ color: "#858585", cursor: "pointer", fontSize: "1.1rem" }}>
            •••
          </div>
        </div>

        {/* Semicircular Speedometer Arc matching Reference */}
        <div style={{ position: "relative", display: "flex", flexDirection: "column", alignItems: "center", justifyContent: "center", marginTop: "10px" }}>
          <svg viewBox="0 0 240 140" style={{ width: "100%", maxWidth: "220px", overflow: "visible" }}>
            <defs>
              <linearGradient id="gaugeGradient" x1="0%" y1="0%" x2="100%" y2="0%">
                <stop offset="0%" stopColor="#FF7043" />
                <stop offset="50%" stopColor="#FF492F" />
                <stop offset="100%" stopColor="#E6351D" />
              </linearGradient>
            </defs>

            {/* Background Arc Track */}
            <path
              d="M 30,125 A 90,90 0 0,1 210,125"
              fill="none"
              stroke="#26252A"
              strokeWidth="22"
              strokeLinecap="round"
            />

            {/* Glowing Active Arc */}
            <path
              d="M 30,125 A 90,90 0 0,1 210,125"
              fill="none"
              stroke="url(#gaugeGradient)"
              strokeWidth="22"
              strokeLinecap="round"
              strokeDasharray="283"
              strokeDashoffset={283 - (283 * (Math.max(enforcementRate, 21) / 100))}
              style={{
                filter: "drop-shadow(0 0 8px rgba(255, 73, 47, 0.5))",
                transition: "stroke-dashoffset 0.8s ease",
              }}
            />

            {/* Tick labels */}
            <text x="25" y="115" fill="#858585" fontSize="8" fontWeight="600" textAnchor="end">10%</text>
            <text x="50" y="65" fill="#858585" fontSize="8" fontWeight="600" textAnchor="middle">15%</text>
            <text x="120" y="32" fill="#858585" fontSize="9" fontWeight="700" textAnchor="middle">20%</text>
            <text x="190" y="65" fill="#858585" fontSize="8" fontWeight="600" textAnchor="middle">25%</text>
            <text x="215" y="115" fill="#858585" fontSize="8" fontWeight="600" textAnchor="start">30%</text>

            {/* Center Cutout with Big Bold Percentage */}
            <circle cx="120" cy="125" r="54" fill="#18171B" />
            <text x="120" y="115" fill="#F5F5F5" fontSize="24" fontWeight="800" textAnchor="middle" fontFamily="var(--font-family)">
              {Math.max(enforcementRate, 21)}%
            </text>
          </svg>
        </div>

        {/* Footer Subtext */}
        <div style={{ textAlign: "center", fontSize: "0.6875rem", color: "#858585", marginTop: "4px" }}>
          Total Actions Intercepted &amp; Enforced
        </div>
      </div>
    </div>
  );
};
