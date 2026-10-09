"use client";

import React, { useState } from "react";

interface HeaderProps {
  onTriggerKillSwitch: () => void;
  isKilled: boolean;
  selectedTenant?: string;
  onSelectTenant?: (tenant: string) => void;
}

export const Header: React.FC<HeaderProps> = ({
  onTriggerKillSwitch,
  isKilled,
  selectedTenant: externalSelectedTenant,
  onSelectTenant: externalOnSelectTenant,
}) => {
  const [internalTenant, setInternalTenant] = useState("org_enterprise");
  const selectedTenant = externalSelectedTenant ?? internalTenant;
  const setSelectedTenant = externalOnSelectTenant ?? setInternalTenant;

  return (
    <header
      id="platform-header"
      style={{
        height: "56px",
        background: "var(--panel-bg)",
        borderBottom: "1px solid var(--border-rule)",
        display: "flex",
        alignItems: "center",
        justifyContent: "space-between",
        padding: "0 24px",
        position: "sticky",
        top: 0,
        zIndex: 50,
      }}
    >
      {/* Title & Tenant Scope */}
      <div style={{ display: "flex", alignItems: "center", gap: "20px" }}>
        <h1 style={{ fontSize: "0.95rem", fontWeight: 600, color: "var(--text-primary)", display: "flex", alignItems: "center", gap: "10px", letterSpacing: "-0.01em" }}>
          <span>Autonomous AI Agent Security & Runtime Governance</span>
          <span className="code-pill">
            PHASE 1
          </span>
        </h1>

        <div style={{ display: "flex", alignItems: "center", gap: "8px" }}>
          <label htmlFor="tenant-selector" style={{ fontSize: "0.75rem", color: "var(--text-muted)", fontFamily: "var(--font-mono)" }}>TENANT:</label>
          <select
            id="tenant-selector"
            value={selectedTenant}
            onChange={(e) => setSelectedTenant(e.target.value)}
            style={{
              background: "#090D13",
              color: "var(--text-primary)",
              border: "1px solid var(--border-rule)",
              borderRadius: "3px",
              padding: "4px 8px",
              fontSize: "0.75rem",
              fontFamily: "var(--font-mono)",
              outline: "none",
              cursor: "pointer",
            }}
          >
            <option value="org_enterprise">org_enterprise (Enterprise Fleet)</option>
            <option value="tenant-acme-corp">tenant-acme-corp (Prod)</option>
            <option value="tenant-fintech-global">tenant-fintech-global (Staging)</option>
            <option value="tenant-health-ai">tenant-health-ai (Dev)</option>
            {selectedTenant && !["org_enterprise", "tenant-acme-corp", "tenant-fintech-global", "tenant-health-ai"].includes(selectedTenant) && (
              <option value={selectedTenant}>{selectedTenant}</option>
            )}
          </select>
        </div>
      </div>

      {/* Right Controls: Health & Kill Switch */}
      <div style={{ display: "flex", alignItems: "center", gap: "12px" }}>
        {/* Readiness Badge */}
        <div
          id="system-readiness-indicator"
          style={{
            display: "flex",
            alignItems: "center",
            gap: "6px",
            background: "var(--status-allow-bg)",
            border: "1px solid var(--status-allow-border)",
            padding: "4px 10px",
            borderRadius: "3px",
            fontSize: "0.75rem",
            color: "var(--status-allow-fg)",
            fontFamily: "var(--font-mono)",
            fontWeight: 600,
          }}
        >
          <span className="status-dot status-dot-active" />
          <span>GATEWAY: OPERATIONAL</span>
        </div>

        {/* Emergency Kill Switch */}
        <button
          id="btn-emergency-kill-switch"
          onClick={onTriggerKillSwitch}
          className="btn btn-danger"
          style={{
            background: isKilled ? "var(--status-block-border)" : "var(--status-block-bg)",
            color: isKilled ? "#FFFFFF" : "var(--status-block-fg)",
            borderColor: "var(--status-block-border)",
            fontWeight: 600,
            fontSize: "0.75rem",
            padding: "5px 12px",
            borderRadius: "3px",
          }}
        >
          <span aria-hidden="true">■</span>
          <span>{isKilled ? "KILL SWITCH ENGAGED (ALL SUSPENDED)" : "EMERGENCY KILL SWITCH"}</span>
        </button>
      </div>
    </header>
  );
};
