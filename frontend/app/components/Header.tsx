"use client";

import React, { useState, useEffect } from "react";
import { api } from "../../lib/api";

interface HeaderProps {
  onTriggerKillSwitch: () => void;
  isKilled: boolean;
  selectedTenant?: string;
  onSelectTenant?: (tenant: string) => void;
  isGatewayHealthy?: boolean;
}

/* ── Inline SVG icons ── */
const PowerIcon = () => (
  <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
    <path d="M18.36 6.64a9 9 0 1 1-12.73 0" />
    <line x1="12" y1="2" x2="12" y2="12" />
  </svg>
);

const ChevronIcon = () => (
  <svg width="10" height="10" viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
    <polyline points="4,6 8,10 12,6" />
  </svg>
);

export const Header: React.FC<HeaderProps> = ({
  onTriggerKillSwitch,
  isKilled,
  selectedTenant: externalSelectedTenant,
  onSelectTenant: externalOnSelectTenant,
  isGatewayHealthy = true,
}) => {
  const [internalTenant, setInternalTenant] = useState("");
  const [organizations, setOrganizations] = useState<{ id: string; name: string }[]>([]);
  const selectedTenant = externalSelectedTenant ?? internalTenant;
  const setSelectedTenant = externalOnSelectTenant ?? setInternalTenant;

  useEffect(() => {
    let active = true;
    const fetchOrgs = async () => {
      try {
        const orgs = await api.getOrganizations();
        if (active && Array.isArray(orgs)) {
          setOrganizations(orgs);
        }
      } catch {
        /* backend offline or initial load */
      }
    };
    void fetchOrgs();
    const interval = setInterval(fetchOrgs, 15000);
    return () => {
      active = false;
      clearInterval(interval);
    };
  }, []);

  return (
    <header
      id="platform-header"
      style={{
        height: "60px",
        background: "#ffffff",
        borderBottom: "1px solid #eef2f6",
        boxShadow: "0 1px 3px rgba(15, 23, 42, 0.03)",
        display: "flex",
        alignItems: "center",
        justifyContent: "space-between",
        padding: "0 24px",
        position: "sticky",
        top: 0,
        zIndex: 50,
        gap: "16px",
        flexShrink: 0,
      }}
    >
      {/* ── Left: title + version pill ── */}
      <div style={{ display: "flex", alignItems: "center", gap: "10px", flexShrink: 0 }}>
        <h1
          style={{
            fontSize: "0.875rem",
            fontWeight: 600,
            color: "#0f172a",
            letterSpacing: "-0.01em",
            whiteSpace: "nowrap",
            margin: 0,
          }}
        >
          Autonomous AI Agent Security &amp; Runtime Governance
        </h1>
        <span
          style={{
            fontSize: "0.625rem",
            fontFamily: "var(--font-mono)",
            color: "#64748b",
            background: "#f8fafc",
            border: "1px solid #e2e8f0",
            padding: "2px 7px",
            borderRadius: "6px",
            letterSpacing: "0.05em",
            textTransform: "uppercase",
            fontWeight: 600,
          }}
        >
          GATEWAY
        </span>
        <span
          className="code-pill"
          style={{
            fontSize: "0.6875rem",
            color: "#059669",
            borderColor: "rgba(16, 185, 129, 0.25)",
            background: "#ecfdf5",
            borderRadius: "6px",
            fontWeight: 600,
          }}
        >
          v0.1
        </span>
      </div>

      {/* ── Center: Search pill matching reference image ── */}
      <div
        style={{
          flex: "1 1 340px",
          maxWidth: "460px",
          minWidth: "200px",
          display: "flex",
          alignItems: "center",
          background: "#f8fafc",
          border: "1px solid #e2e8f0",
          borderRadius: "24px",
          padding: "6px 14px",
          gap: "8px",
          transition: "border-color 0.15s ease, background 0.15s ease",
        }}
      >
        <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="#94a3b8" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
          <circle cx="11" cy="11" r="8" />
          <line x1="21" y1="21" x2="16.65" y2="16.65" />
        </svg>
        <input
          type="text"
          placeholder="Search policies, apps, users..."
          style={{
            border: "none",
            outline: "none",
            background: "transparent",
            fontSize: "0.8125rem",
            color: "#0f172a",
            width: "100%",
            padding: 0,
            boxShadow: "none",
          }}
        />
        <span
          style={{
            fontSize: "0.625rem",
            fontFamily: "var(--font-mono)",
            color: "#94a3b8",
            background: "#ffffff",
            border: "1px solid #e2e8f0",
            padding: "2px 6px",
            borderRadius: "4px",
            fontWeight: 600,
            whiteSpace: "nowrap",
          }}
        >
          Ctrl K
        </span>
      </div>

      {/* ── Right: tenant selector + kill switch + notifications + profile ── */}
      <div style={{ display: "flex", alignItems: "center", gap: "12px", flexShrink: 0 }}>

        {/* Tenant selector */}
        <div
          style={{
            display: "flex",
            alignItems: "center",
            gap: "6px",
          }}
        >
          <label
            htmlFor="tenant-selector"
            style={{
              fontSize: "0.6875rem",
              color: "#64748b",
              fontFamily: "var(--font-mono)",
              letterSpacing: "0.05em",
              textTransform: "uppercase",
              whiteSpace: "nowrap",
              fontWeight: 600,
            }}
          >
            TENANT
          </label>

          <div style={{ position: "relative", display: "flex", alignItems: "center" }}>
            <select
              id="tenant-selector"
              value={selectedTenant}
              onChange={(e) => setSelectedTenant(e.target.value)}
              style={{
                appearance: "none",
                WebkitAppearance: "none",
                background: "#ffffff",
                color: "#0f172a",
                border: "1px solid #e2e8f0",
                borderRadius: "8px",
                padding: "5px 28px 5px 10px",
                fontSize: "0.75rem",
                fontFamily: "var(--font-family)",
                outline: "none",
                cursor: "pointer",
                minWidth: "150px",
                boxShadow: "0 1px 2px rgba(0, 0, 0, 0.03)",
                transition: "border-color 0.15s ease",
              }}
              onFocus={(e) => (e.currentTarget.style.borderColor = "#2563eb")}
              onBlur={(e) => (e.currentTarget.style.borderColor = "#e2e8f0")}
            >
              <option value="">All Tenants (Global)</option>
              {organizations.map((org) => (
                <option key={org.id} value={org.id}>
                  {org.id} — {org.name}
                </option>
              ))}
              {selectedTenant &&
                !organizations.some((o) => o.id === selectedTenant) && (
                  <option value={selectedTenant}>{selectedTenant}</option>
                )}
            </select>
            <span
              style={{
                position: "absolute",
                right: "8px",
                pointerEvents: "none",
                color: "#64748b",
                display: "flex",
                alignItems: "center",
              }}
            >
              <ChevronIcon />
            </span>
          </div>
        </div>

        {/* Emergency Kill Switch (Compact Icon-Only Button) */}
        <button
          id="btn-emergency-kill-switch"
          onClick={onTriggerKillSwitch}
          style={{
            display: "inline-flex",
            alignItems: "center",
            justifyContent: "center",
            width: "36px",
            height: "36px",
            borderRadius: "8px",
            border: `1px solid ${isKilled ? "#dc2626" : "rgba(239, 68, 68, 0.35)"}`,
            background: isKilled ? "#dc2626" : "#fef2f2",
            color: isKilled ? "#ffffff" : "#dc2626",
            cursor: "pointer",
            boxShadow: isKilled ? "0 0 10px rgba(220, 38, 38, 0.4)" : "0 1px 2px rgba(0, 0, 0, 0.02)",
            transition: "all 0.15s ease",
            flexShrink: 0,
          }}
          title={isKilled ? "Emergency Kill Switch Engaged (Click to Deactivate)" : "Emergency Kill Switch (Click to Freeze All Agents)"}
          aria-label={isKilled ? "Emergency Kill Switch Engaged" : "Emergency Kill Switch"}
          aria-pressed={isKilled}
        >
          <PowerIcon />
        </button>

        {/* Notification Bell */}
        <div
          style={{
            position: "relative",
            width: "36px",
            height: "36px",
            borderRadius: "50%",
            background: "#f8fafc",
            border: "1px solid #e2e8f0",
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
            cursor: "pointer",
            color: "#64748b",
          }}
          title="Notifications"
        >
          <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
            <path d="M18 8A6 6 0 0 0 6 8c0 7-3 9-3 9h18s-3-2-3-9" />
            <path d="M13.73 21a2 2 0 0 1-3.46 0" />
          </svg>
        </div>

        {/* User profile capsule */}
        <div
          style={{
            display: "flex",
            alignItems: "center",
            gap: "9px",
            padding: "3px 10px 3px 4px",
            background: "#ffffff",
            border: "1px solid #e2e8f0",
            borderRadius: "24px",
            boxShadow: "0 1px 2px rgba(0, 0, 0, 0.03)",
            cursor: "pointer",
          }}
        >
          <div
            style={{
              width: "30px",
              height: "30px",
              borderRadius: "50%",
              background: "linear-gradient(135deg, #3b82f6 0%, #1d4ed8 100%)",
              color: "#ffffff",
              display: "flex",
              alignItems: "center",
              justifyContent: "center",
              fontWeight: 700,
              fontSize: "0.75rem",
              letterSpacing: "-0.02em",
            }}
          >
            SO
          </div>
          <div style={{ display: "flex", flexDirection: "column", lineHeight: 1.1 }}>
            <span style={{ fontSize: "0.75rem", fontWeight: 600, color: "#0f172a", whiteSpace: "nowrap" }}>
              Security Officer
            </span>
            <span style={{ fontSize: "0.625rem", color: "#64748b", marginTop: "1px" }}>
              Admin
            </span>
          </div>
          <span style={{ color: "#94a3b8", display: "flex", alignItems: "center", marginLeft: "2px" }}>
            <ChevronIcon />
          </span>
        </div>
      </div>
    </header>
  );
};
