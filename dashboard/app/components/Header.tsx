"use client";

import React, { useState } from "react";

interface HeaderProps {
  onTriggerKillSwitch: () => void;
  isKilled: boolean;
}

export const Header: React.FC<HeaderProps> = ({ onTriggerKillSwitch, isKilled }) => {
  const [selectedTenant, setSelectedTenant] = useState("tenant-acme-corp");

  return (
    <header
      id="platform-header"
      style={{
        height: "68px",
        background: "rgba(13, 18, 27, 0.8)",
        backdropFilter: "blur(12px)",
        borderBottom: "1px solid var(--border-subtle)",
        display: "flex",
        alignItems: "center",
        justifyContent: "space-between",
        padding: "0 32px",
        position: "sticky",
        top: 0,
        zIndex: 50,
      }}
    >
      {/* Title & Tenant Scope */}
      <div style={{ display: "flex", alignItems: "center", gap: "20px" }}>
        <h1 style={{ fontSize: "1.1rem", fontWeight: 700, color: "var(--text-primary)", display: "flex", alignItems: "center", gap: "10px" }}>
          <span>Autonomous AI Agent Security & Runtime Governance</span>
          <span
            className="code-pill"
            style={{ color: "var(--accent-cyan)", borderColor: "rgba(0, 240, 255, 0.3)" }}
          >
            PHASE 1
          </span>
        </h1>

        <div style={{ display: "flex", alignItems: "center", gap: "8px" }}>
          <span style={{ fontSize: "0.8rem", color: "var(--text-muted)" }}>Tenant:</span>
          <select
            id="tenant-selector"
            value={selectedTenant}
            onChange={(e) => setSelectedTenant(e.target.value)}
            style={{
              background: "rgba(0, 0, 0, 0.4)",
              color: "var(--text-primary)",
              border: "1px solid var(--border-subtle)",
              borderRadius: "6px",
              padding: "4px 8px",
              fontSize: "0.8rem",
              fontFamily: "var(--font-mono)",
              outline: "none",
              cursor: "pointer",
            }}
          >
            <option value="tenant-acme-corp">tenant-acme-corp (Prod)</option>
            <option value="tenant-fintech-global">tenant-fintech-global (Staging)</option>
            <option value="tenant-health-ai">tenant-health-ai (Dev)</option>
          </select>
        </div>
      </div>

      {/* Right Controls: Health & Kill Switch */}
      <div style={{ display: "flex", alignItems: "center", gap: "16px" }}>
        {/* Readiness Badge */}
        <div
          id="system-readiness-indicator"
          style={{
            display: "flex",
            alignItems: "center",
            gap: "8px",
            background: "rgba(16, 185, 129, 0.1)",
            border: "1px solid rgba(16, 185, 129, 0.25)",
            padding: "6px 12px",
            borderRadius: "8px",
            fontSize: "0.8rem",
            color: "#10B981",
            fontFamily: "var(--font-mono)",
          }}
        >
          <span className="status-dot status-dot-active" />
          <span>SERVICES: READY</span>
        </div>

        {/* Emergency Kill Switch */}
        <button
          id="btn-emergency-kill-switch"
          onClick={onTriggerKillSwitch}
          className="btn btn-danger"
          style={{
            background: isKilled ? "#F43F5E" : "rgba(244, 63, 94, 0.15)",
            color: isKilled ? "#FFF" : "#F43F5E",
            fontWeight: 700,
            fontSize: "0.8rem",
          }}
        >
          <span>🛑</span>
          <span>{isKilled ? "KILL SWITCH ENGAGED (ALL SUSPENDED)" : "EMERGENCY KILL SWITCH"}</span>
        </button>
      </div>
    </header>
  );
};
