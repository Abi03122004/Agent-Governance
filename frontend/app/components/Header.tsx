"use client";

import React, { useState, useEffect } from "react";
import { api } from "../../lib/api";

interface HeaderProps {
  onTriggerKillSwitch: () => void;
  isKilled: boolean;
  selectedTenant?: string;
  onSelectTenant?: (tenant: string) => void;
  isGatewayHealthy?: boolean;
  onCheckAlerts?: () => void;
  activeTab?: string;
}

const SearchIcon = () => (
  <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
    <circle cx="11" cy="11" r="8" />
    <line x1="21" y1="21" x2="16.65" y2="16.65" />
  </svg>
);

const BellIcon = () => (
  <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
    <path d="M18 8A6 6 0 0 0 6 8c0 7-3 9-3 9h18s-3-2-3-9" />
    <path d="M13.73 21a2 2 0 0 1-3.46 0" />
  </svg>
);

const ChevronDownIcon = () => (
  <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.2" strokeLinecap="round" strokeLinejoin="round">
    <polyline points="6 9 12 15 18 9" />
  </svg>
);

const PowerIcon = () => (
  <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.2" strokeLinecap="round" strokeLinejoin="round">
    <path d="M18.36 6.64a9 9 0 1 1-12.73 0" />
    <line x1="12" y1="2" x2="12" y2="12" />
  </svg>
);

export const Header: React.FC<HeaderProps> = ({
  onTriggerKillSwitch,
  isKilled,
  selectedTenant: externalSelectedTenant,
  onSelectTenant: externalOnSelectTenant,
  onCheckAlerts,
  activeTab = "overview",
}) => {
  const [internalTenant, setInternalTenant] = useState("");
  const [organizations, setOrganizations] = useState<{ id: string; name: string }[]>([]);
  const [searchQuery, setSearchQuery] = useState("");
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
        /* offline or initial load */
      }
    };
    void fetchOrgs();
    const interval = setInterval(fetchOrgs, 20000);
    return () => {
      active = false;
      clearInterval(interval);
    };
  }, []);

  const getBreadcrumbTitle = (tab: string) => {
    switch (tab) {
      case "agents": return "Agent Fleet & Identities";
      case "sessions": return "Runtime Sessions";
      case "approvals": return "Human Approval Queue";
      case "activity": return "Interception & Activity Feed";
      case "audit": return "Cryptographic Audit Ledger";
      case "policies": return "Security Policies";
      case "health": return "System Readiness & Health";
      default: return "Dashboard";
    }
  };

  return (
    <header
      id="platform-header"
      style={{
        display: "flex",
        alignItems: "center",
        justifyContent: "space-between",
        padding: "16px 28px 8px 28px",
        background: "transparent",
        position: "sticky",
        top: 0,
        zIndex: 30,
        gap: "16px",
        flexShrink: 0,
      }}
    >
      {/* ── Left Breadcrumb Tag ── */}
      <div style={{ display: "flex", alignItems: "center", gap: "10px" }}>
        <span
          style={{
            fontSize: "0.8125rem",
            fontWeight: 500,
            color: "#858585",
            letterSpacing: "0.02em",
          }}
        >
          {getBreadcrumbTitle(activeTab)}
        </span>
        <span style={{ color: "#36353C", fontSize: "0.75rem" }}>/</span>
        <span
          style={{
            fontSize: "0.6875rem",
            color: "#10B981",
            background: "rgba(16, 185, 129, 0.12)",
            border: "1px solid rgba(16, 185, 129, 0.25)",
            padding: "2px 7px",
            borderRadius: "6px",
            fontFamily: "var(--font-mono)",
            fontWeight: 600,
            textTransform: "uppercase",
            letterSpacing: "0.05em",
          }}
        >
          Live Gateway
        </span>
      </div>

      {/* ── Right Utility Cluster matching Reference ── */}
      <div style={{ display: "flex", alignItems: "center", gap: "10px" }}>
        {/* Tenant Selector Dropdown Capsule */}
        <div
          style={{
            display: "flex",
            alignItems: "center",
            background: "#151418",
            border: "1px solid #262529",
            borderRadius: "20px",
            padding: "4px 10px 4px 12px",
            gap: "6px",
          }}
        >
          <span style={{ fontSize: "0.6875rem", color: "#858585", textTransform: "uppercase", fontFamily: "var(--font-mono)", fontWeight: 600 }}>
            Scope:
          </span>
          <select
            id="tenant-selector"
            value={selectedTenant}
            onChange={(e) => setSelectedTenant(e.target.value)}
            style={{
              background: "transparent",
              color: "#F5F5F5",
              border: "none",
              outline: "none",
              fontSize: "0.75rem",
              fontWeight: 500,
              cursor: "pointer",
              paddingRight: "6px",
            }}
          >
            <option value="" style={{ background: "#1C1B1F", color: "#F5F5F5" }}>All Tenants (Global)</option>
            {organizations.map((org) => (
              <option key={org.id} value={org.id} style={{ background: "#1C1B1F", color: "#F5F5F5" }}>
                {org.name} ({org.id})
              </option>
            ))}
            {selectedTenant && !organizations.some((o) => o.id === selectedTenant) && (
              <option value={selectedTenant} style={{ background: "#1C1B1F", color: "#F5F5F5" }}>{selectedTenant}</option>
            )}
          </select>
        </div>

        {/* Search Capsule Input matching Reference */}
        <div
          style={{
            display: "flex",
            alignItems: "center",
            background: "#151418",
            border: "1px solid #262529",
            borderRadius: "20px",
            padding: "6px 14px",
            gap: "8px",
            width: "220px",
            transition: "border-color 0.15s ease, width 0.2s ease",
          }}
          onFocus={() => {}}
        >
          <span style={{ color: "#858585", display: "flex", alignItems: "center" }}>
            <SearchIcon />
          </span>
          <input
            type="text"
            placeholder="Search alerts, agents..."
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            style={{
              background: "transparent",
              border: "none",
              outline: "none",
              color: "#F5F5F5",
              fontSize: "0.75rem",
              width: "100%",
              padding: 0,
              boxShadow: "none",
            }}
          />
        </div>

        {/* Notification Bell with unread dot */}
        <div
          style={{
            position: "relative",
            width: "36px",
            height: "36px",
            borderRadius: "50%",
            background: "#151418",
            border: "1px solid #262529",
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
            color: "#858585",
            cursor: "pointer",
            transition: "all 0.15s ease",
          }}
          onMouseEnter={(e) => {
            e.currentTarget.style.color = "#F5F5F5";
            e.currentTarget.style.borderColor = "#36353C";
          }}
          onMouseLeave={(e) => {
            e.currentTarget.style.color = "#858585";
            e.currentTarget.style.borderColor = "#262529";
          }}
          title="Security Notifications"
        >
          <BellIcon />
          <span
            style={{
              position: "absolute",
              top: "8px",
              right: "9px",
              width: "6px",
              height: "6px",
              borderRadius: "50%",
              background: "#FF492F",
              boxShadow: "0 0 6px #FF492F",
            }}
          />
        </div>

        {/* User Profile Capsule matching Reference: Avatar, Name, Handle, Chevron */}
        <div
          style={{
            display: "flex",
            alignItems: "center",
            gap: "8px",
            background: "#151418",
            border: "1px solid #262529",
            borderRadius: "24px",
            padding: "3px 10px 3px 4px",
            cursor: "pointer",
            transition: "border-color 0.15s ease",
          }}
          onMouseEnter={(e) => {
            e.currentTarget.style.borderColor = "#36353C";
          }}
          onMouseLeave={(e) => {
            e.currentTarget.style.borderColor = "#262529";
          }}
        >
          {/* Avatar circle */}
          <div
            style={{
              width: "28px",
              height: "28px",
              borderRadius: "50%",
              background: "linear-gradient(135deg, #FF492F 0%, #8955FF 100%)",
              color: "#FFFFFF",
              fontSize: "0.6875rem",
              fontWeight: 700,
              display: "flex",
              alignItems: "center",
              justifyContent: "center",
            }}
          >
            BN
          </div>
          <div style={{ display: "flex", flexDirection: "column", lineHeight: 1.15 }}>
            <span style={{ fontSize: "0.75rem", fontWeight: 600, color: "#F5F5F5" }}>
              Security Admin
            </span>
            <span style={{ fontSize: "0.625rem", color: "#858585" }}>
              @soc.defense
            </span>
          </div>
          <span style={{ color: "#858585", display: "flex", alignItems: "center", marginLeft: "2px" }}>
            <ChevronDownIcon />
          </span>
        </div>

        {/* Emergency Kill Switch */}
        <button
          id="btn-emergency-kill-switch"
          onClick={onTriggerKillSwitch}
          style={{
            display: "inline-flex",
            alignItems: "center",
            justifyContent: "center",
            width: "36px",
            height: "36px",
            borderRadius: "12px",
            border: `1px solid ${isKilled ? "#FF492F" : "rgba(255, 73, 47, 0.3)"}`,
            background: isKilled ? "#FF492F" : "rgba(255, 73, 47, 0.12)",
            color: isKilled ? "#FFFFFF" : "#FF5D45",
            cursor: "pointer",
            boxShadow: isKilled ? "0 0 14px rgba(255, 73, 47, 0.5)" : "none",
            transition: "all 0.15s ease",
          }}
          title={isKilled ? "KILL SWITCH ACTIVE: Click to Resume Agents" : "EMERGENCY FREEZE: Suspend All Agents"}
          aria-label="Emergency Kill Switch"
        >
          <PowerIcon />
        </button>

        {/* "Check Alerts" button matching Reference! */}
        <button
          id="btn-check-alerts"
          className="btn-check-alerts"
          onClick={onCheckAlerts}
          title="Inspect Security Alerts & Interceptions"
        >
          Check Alerts
        </button>
      </div>
    </header>
  );
};
