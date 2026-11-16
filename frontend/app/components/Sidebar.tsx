"use client";

import React, { useState } from "react";

interface SidebarProps {
  activeTab: string;
  onSelectTab: (tab: string) => void;
  activeAgentsCount?: number;
  blockedCount?: number;
  pendingApprovalsCount?: number;
}

/* ── Inline Precision SVG Icon Set matching Reference ── */
const Icons = {
  Logo: () => (
    <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.4" strokeLinecap="round" strokeLinejoin="round">
      <path d="M12 2L3 7v6c0 5.55 3.84 10.74 9 12 5.16-1.26 9-6.45 9-12V7l-9-5z" />
      <path d="m9 12 2 2 4-4" />
    </svg>
  ),
  Dashboard: ({ size = 18 }: { size?: number }) => (
    <svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <rect x="3" y="3" width="7" height="7" rx="2" />
      <rect x="14" y="3" width="7" height="7" rx="2" />
      <rect x="3" y="14" width="7" height="7" rx="2" />
      <rect x="14" y="14" width="7" height="7" rx="2" />
    </svg>
  ),
  Analytics: ({ size = 18 }: { size?: number }) => (
    <svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <line x1="18" y1="20" x2="18" y2="10" />
      <line x1="12" y1="20" x2="12" y2="4" />
      <line x1="6" y1="20" x2="6" y2="14" />
    </svg>
  ),
  Agents: ({ size = 18 }: { size?: number }) => (
    <svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <rect x="4" y="8" width="16" height="12" rx="3" />
      <path d="M9 13h.01M15 13h.01" strokeWidth="2.5" />
      <path d="M12 4v4M8 4h8" />
      <circle cx="2" cy="14" r="1" />
      <circle cx="22" cy="14" r="1" />
    </svg>
  ),
  Sessions: ({ size = 18 }: { size?: number }) => (
    <svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <rect x="3" y="4" width="18" height="18" rx="2" ry="2" />
      <line x1="16" y1="2" x2="16" y2="6" />
      <line x1="8" y1="2" x2="8" y2="6" />
      <line x1="3" y1="10" x2="21" y2="10" />
    </svg>
  ),
  Interception: ({ size = 18 }: { size?: number }) => (
    <svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <path d="M3 7V5a2 2 0 0 1 2-2h2" />
      <path d="M17 3h2a2 2 0 0 1 2 2v2" />
      <path d="M21 17v2a2 2 0 0 1-2 2h-2" />
      <path d="M7 21H5a2 2 0 0 1-2-2v-2" />
      <polyline points="7 12 10 15 17 9" />
    </svg>
  ),
  Approvals: ({ size = 18 }: { size?: number }) => (
    <svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <path d="M16 4h2a2 2 0 0 1 2 2v14a2 2 0 0 1-2 2H6a2 2 0 0 1-2-2V6a2 2 0 0 1 2-2h2" />
      <rect x="8" y="2" width="8" height="4" rx="1" ry="1" />
      <path d="m9 14 2 2 4-4" />
    </svg>
  ),
  Audit: ({ size = 18 }: { size?: number }) => (
    <svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z" />
      <polyline points="14 2 14 8 20 8" />
      <line x1="16" y1="13" x2="8" y2="13" />
      <line x1="16" y1="17" x2="8" y2="17" />
      <polyline points="10 9 9 9 8 9" />
    </svg>
  ),
  Policies: ({ size = 18 }: { size?: number }) => (
    <svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z" />
    </svg>
  ),
  Settings: ({ size = 18 }: { size?: number }) => (
    <svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <circle cx="12" cy="12" r="3" />
      <path d="M19.4 15a1.65 1.65 0 0 0 .33 1.82l.06.06a2 2 0 0 1 0 2.83 2 2 0 0 1-2.83 0l-.06-.06a1.65 1.65 0 0 0-1.82-.33 1.65 1.65 0 0 0-1 1.51V21a2 2 0 0 1-2 2 2 2 0 0 1-2-2v-.09A1.65 1.65 0 0 0 9 19.4a1.65 1.65 0 0 0-1.82.33l-.06.06a2 2 0 0 1-2.83 0 2 2 0 0 1 0-2.83l.06-.06a1.65 1.65 0 0 0 .33-1.82 1.65 1.65 0 0 0-1.51-1H3a2 2 0 0 1-2-2 2 2 0 0 1 2-2h.09A1.65 1.65 0 0 0 4.6 9a1.65 1.65 0 0 0-.33-1.82l-.06-.06a2 2 0 0 1 0-2.83 2 2 0 0 1 2.83 0l.06.06a1.65 1.65 0 0 0 1.82.33H9a1.65 1.65 0 0 0 1-1.51V3a2 2 0 0 1 2-2 2 2 0 0 1 2 2v.09a1.65 1.65 0 0 0 1 1.51 1.65 1.65 0 0 0 1.82-.33l.06-.06a2 2 0 0 1 2.83 0 2 2 0 0 1 0 2.83l-.06.06a1.65 1.65 0 0 0-.33 1.82V9a1.65 1.65 0 0 0 1.51 1H21a2 2 0 0 1 2 2 2 2 0 0 1-2 2h-.09a1.65 1.65 0 0 0-1.51 1z" />
    </svg>
  ),
  Logout: ({ size = 18 }: { size?: number }) => (
    <svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <path d="M9 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h4" />
      <polyline points="16 17 21 12 16 7" />
      <line x1="21" y1="12" x2="9" y2="12" />
    </svg>
  ),
  Sun: () => (
    <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <circle cx="12" cy="12" r="5" />
      <line x1="12" y1="1" x2="12" y2="3" />
      <line x1="12" y1="21" x2="12" y2="23" />
      <line x1="4.22" y1="4.22" x2="5.64" y2="5.64" />
      <line x1="18.36" y1="18.36" x2="19.78" y2="19.78" />
      <line x1="1" y1="12" x2="3" y2="12" />
      <line x1="21" y1="12" x2="23" y2="12" />
      <line x1="4.22" y1="19.78" x2="5.64" y2="18.36" />
      <line x1="18.36" y1="5.64" x2="19.78" y2="4.22" />
    </svg>
  ),
  Moon: () => (
    <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <path d="M21 12.79A9 9 0 1 1 11.21 3 7 7 0 0 0 21 12.79z" />
    </svg>
  ),
};

const navItems = [
  { id: "overview",  label: "Dashboard",        Icon: Icons.Dashboard },
  { id: "activity",  label: "Activity Stream",  Icon: Icons.Analytics },
  { id: "sessions",  label: "Runtime Sessions", Icon: Icons.Sessions },
  { id: "interception", label: "Interception Feed", Icon: Icons.Interception },
  { id: "agents",    label: "Agent Fleet",      Icon: Icons.Agents },
  { id: "approvals", label: "Approval Queue",   Icon: Icons.Approvals },
  { id: "audit",     label: "Audit Ledger",     Icon: Icons.Audit },
  { id: "policies",  label: "Security Policies", Icon: Icons.Policies },
] as const;

export const Sidebar: React.FC<SidebarProps> = ({
  activeTab,
  onSelectTab,
}) => {
  const [hoveredTab, setHoveredTab] = useState<string | null>(null);

  return (
    <aside
      id="sidebar-navigation"
      style={{
        width: "78px",
        background: "#0E0E10",
        borderRight: "1px solid #1E1D22",
        display: "flex",
        flexDirection: "column",
        alignItems: "center",
        justifyContent: "space-between",
        padding: "18px 0 16px 0",
        height: "100vh",
        position: "sticky",
        top: 0,
        flexShrink: 0,
        zIndex: 40,
      }}
    >
      {/* ── Top Brand Squircle Icon (Vibrant Orange-Red matching reference) ── */}
      <div style={{ display: "flex", flexDirection: "column", alignItems: "center" }}>
        <button
          onClick={() => onSelectTab("overview")}
          style={{
            width: "44px",
            height: "44px",
            borderRadius: "14px",
            background: "linear-gradient(135deg, #FF492F 0%, #FF7043 100%)",
            border: "1px solid rgba(255, 255, 255, 0.2)",
            boxShadow: "0 0 20px rgba(255, 73, 47, 0.45)",
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
            color: "#FFFFFF",
            cursor: "pointer",
            transition: "transform 0.18s ease, box-shadow 0.18s ease",
          }}
          onMouseEnter={(e) => {
            e.currentTarget.style.transform = "scale(1.05)";
            e.currentTarget.style.boxShadow = "0 0 26px rgba(255, 73, 47, 0.65)";
          }}
          onMouseLeave={(e) => {
            e.currentTarget.style.transform = "scale(1)";
            e.currentTarget.style.boxShadow = "0 0 20px rgba(255, 73, 47, 0.45)";
          }}
          title="Autonomous AI Agent Security Gateway"
          aria-label="Dashboard Home"
        >
          <span style={{ fontWeight: 800, fontSize: "1.1rem", fontFamily: "var(--font-family)", letterSpacing: "-0.04em" }}>
            C
          </span>
        </button>
      </div>

      {/* ── Middle Nav Dock (Dark Charcoal Capsule with Active Pill Indicator) ── */}
      <nav
        aria-label="Main navigation"
        style={{
          background: "#141316",
          border: "1px solid #222126",
          borderRadius: "22px",
          padding: "8px 6px",
          display: "flex",
          flexDirection: "column",
          gap: "8px",
          alignItems: "center",
          boxShadow: "0 4px 20px rgba(0, 0, 0, 0.45)",
        }}
      >
        {navItems.map(({ id, label, Icon }) => {
          const isActive = activeTab === id || (id === "interception" && activeTab === "activity");

          return (
            <div key={id} style={{ position: "relative" }}>
              <button
                id={`nav-${id}`}
                onClick={() => onSelectTab(id === "interception" ? "activity" : id)}
                onMouseEnter={() => setHoveredTab(id)}
                onMouseLeave={() => setHoveredTab(null)}
                aria-current={isActive ? "page" : undefined}
                style={{
                  position: "relative",
                  width: "42px",
                  height: "42px",
                  borderRadius: "14px",
                  background: isActive ? "#222126" : "transparent",
                  color: isActive ? "#FFFFFF" : "#858585",
                  border: isActive ? "1px solid rgba(255, 255, 255, 0.12)" : "1px solid transparent",
                  boxShadow: isActive ? "0 4px 14px rgba(0, 0, 0, 0.5), inset 0 1px 1px rgba(255, 255, 255, 0.08)" : "none",
                  cursor: "pointer",
                  display: "flex",
                  alignItems: "center",
                  justifyContent: "center",
                  transition: "all 0.18s ease",
                }}
              >
                <Icon size={19} />

                {/* Active Indicator Accent Dot */}
                {isActive && (
                  <span
                    style={{
                      position: "absolute",
                      bottom: "5px",
                      width: "4px",
                      height: "4px",
                      borderRadius: "50%",
                      background: "#FF492F",
                      boxShadow: "0 0 6px #FF492F",
                    }}
                  />
                )}
              </button>

              {/* Tooltip on Hover */}
              {hoveredTab === id && (
                <div
                  style={{
                    position: "absolute",
                    left: "54px",
                    top: "50%",
                    transform: "translateY(-50%)",
                    background: "#1C1B1F",
                    border: "1px solid #333238",
                    color: "#F5F5F5",
                    fontSize: "0.75rem",
                    fontWeight: 600,
                    padding: "5px 11px",
                    borderRadius: "8px",
                    whiteSpace: "nowrap",
                    boxShadow: "0 6px 18px rgba(0, 0, 0, 0.6)",
                    zIndex: 100,
                    pointerEvents: "none",
                  }}
                >
                  {label}
                </div>
              )}
            </div>
          );
        })}
      </nav>

      {/* ── Bottom Controls: Settings, Purge/Logout & Dark/Light Switch ── */}
      <div
        style={{
          display: "flex",
          flexDirection: "column",
          gap: "10px",
          alignItems: "center",
        }}
      >
        {/* Settings Button */}
        <div style={{ position: "relative" }}>
          <button
            onClick={() => onSelectTab("health")}
            onMouseEnter={() => setHoveredTab("settings")}
            onMouseLeave={() => setHoveredTab(null)}
            style={{
              width: "38px",
              height: "38px",
              borderRadius: "12px",
              background: activeTab === "health" ? "#222126" : "transparent",
              color: activeTab === "health" ? "#FFFFFF" : "#858585",
              border: activeTab === "health" ? "1px solid rgba(255, 255, 255, 0.1)" : "1px solid transparent",
              cursor: "pointer",
              display: "flex",
              alignItems: "center",
              justifyContent: "center",
              transition: "all 0.15s ease",
            }}
            title="System Settings & Readiness"
          >
            <Icons.Settings size={18} />
          </button>
          {hoveredTab === "settings" && (
            <div
              style={{
                position: "absolute",
                left: "50px",
                top: "50%",
                transform: "translateY(-50%)",
                background: "#1C1B1F",
                border: "1px solid #333238",
                color: "#F5F5F5",
                fontSize: "0.75rem",
                fontWeight: 600,
                padding: "5px 11px",
                borderRadius: "8px",
                whiteSpace: "nowrap",
                zIndex: 100,
                pointerEvents: "none",
              }}
            >
              Settings &amp; Readiness
            </div>
          )}
        </div>

        {/* Audit / Switch Button */}
        <div style={{ position: "relative" }}>
          <button
            onClick={() => onSelectTab("audit")}
            onMouseEnter={() => setHoveredTab("audit_quick")}
            onMouseLeave={() => setHoveredTab(null)}
            style={{
              width: "38px",
              height: "38px",
              borderRadius: "12px",
              background: "transparent",
              color: "#858585",
              border: "1px solid transparent",
              cursor: "pointer",
              display: "flex",
              alignItems: "center",
              justifyContent: "center",
              transition: "all 0.15s ease",
            }}
            title="Cryptographic Audit Trail"
          >
            <Icons.Logout size={18} />
          </button>
          {hoveredTab === "audit_quick" && (
            <div
              style={{
                position: "absolute",
                left: "50px",
                top: "50%",
                transform: "translateY(-50%)",
                background: "#1C1B1F",
                border: "1px solid #333238",
                color: "#F5F5F5",
                fontSize: "0.75rem",
                fontWeight: 600,
                padding: "5px 11px",
                borderRadius: "8px",
                whiteSpace: "nowrap",
                zIndex: 100,
                pointerEvents: "none",
              }}
            >
              Audit Trail
            </div>
          )}
        </div>

        {/* Dark / Light Toggle Pill matching reference image */}
        <div
          style={{
            background: "#141316",
            border: "1px solid #222126",
            borderRadius: "16px",
            padding: "4px 3px",
            display: "flex",
            flexDirection: "column",
            gap: "4px",
            alignItems: "center",
          }}
        >
          <div
            style={{
              width: "28px",
              height: "28px",
              borderRadius: "10px",
              display: "flex",
              alignItems: "center",
              justifyContent: "center",
              color: "#858585",
              cursor: "pointer",
            }}
            title="Light Mode (Cybersecurity SOC Dark Default)"
          >
            <Icons.Sun />
          </div>
          <div
            style={{
              width: "28px",
              height: "28px",
              borderRadius: "10px",
              background: "#222126",
              border: "1px solid rgba(255, 255, 255, 0.1)",
              display: "flex",
              alignItems: "center",
              justifyContent: "center",
              color: "#FFFFFF",
              boxShadow: "0 2px 6px rgba(0, 0, 0, 0.4)",
            }}
            title="Dark SOC Mode (Active)"
          >
            <Icons.Moon />
          </div>
        </div>
      </div>
    </aside>
  );
};
