"use client";

import React from "react";

interface SidebarProps {
  activeTab: string;
  onSelectTab: (tab: string) => void;
  activeAgentsCount?: number;
  blockedCount?: number;
  pendingApprovalsCount?: number;
}

/* ── Inline SVG icon set matching reference design ── */
const Icons: Record<string, React.FC<{ size?: number }>> = {
  Dashboard: ({ size = 16 }) => (
    <svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
      <rect x="3" y="3" width="7" height="7" rx="1.5" />
      <rect x="14" y="3" width="7" height="7" rx="1.5" />
      <rect x="3" y="14" width="7" height="7" rx="1.5" />
      <rect x="14" y="14" width="7" height="7" rx="1.5" />
    </svg>
  ),
  Agents: ({ size = 16 }) => (
    <svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
      <rect x="4" y="8" width="16" height="12" rx="3" />
      <path d="M9 13h.01M15 13h.01" strokeWidth="2.5" />
      <path d="M12 4v4M8 4h8" />
      <circle cx="2" cy="14" r="1" />
      <circle cx="22" cy="14" r="1" />
    </svg>
  ),
  Sessions: ({ size = 16 }) => (
    <svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
      <path d="M4.93 19.07A10 10 0 0 1 4.93 4.93" />
      <path d="M19.07 4.93a10 10 0 0 1 0 14.14" />
      <path d="M8.46 15.54a5 5 0 0 1 0-7.07" />
      <path d="M15.54 8.47a5 5 0 0 1 0 7.07" />
      <circle cx="12" cy="12" r="2" fill="currentColor" />
    </svg>
  ),
  Approvals: ({ size = 16 }) => (
    <svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
      <path d="M16 4h2a2 2 0 0 1 2 2v14a2 2 0 0 1-2 2H6a2 2 0 0 1-2-2V6a2 2 0 0 1 2-2h2" />
      <rect x="8" y="2" width="8" height="4" rx="1" ry="1" />
      <path d="m9 14 2 2 4-4" />
    </svg>
  ),
  RuntimeActivity: ({ size = 16 }) => (
    <svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
      <polyline points="22 12 18 12 15 21 9 3 6 12 2 12" />
    </svg>
  ),
  AuditLog: ({ size = 16 }) => (
    <svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
      <circle cx="12" cy="12" r="10" />
      <polyline points="12 6 12 12 16 14" />
    </svg>
  ),
  Policies: ({ size = 16 }) => (
    <svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
      <path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z" />
      <path d="m9 12 2 2 4-4" />
    </svg>
  ),
  SystemHealth: ({ size = 16 }) => (
    <svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
      <path d="M19 14c1.49-1.46 3-3.21 3-5.5A5.5 5.5 0 0 0 16.5 3c-1.76 0-3 .5-4.5 2-1.5-1.5-2.74-2-4.5-2A5.5 5.5 0 0 0 2 8.5c0 2.3 1.5 4.05 3 5.5l7 7Z" />
    </svg>
  ),
  Shield: ({ size = 16 }) => (
    <svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
      <path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z" />
    </svg>
  ),
  Lock: ({ size = 16 }) => (
    <svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
      <rect x="3" y="11" width="18" height="11" rx="2" ry="2" />
      <path d="M7 11V7a5 5 0 0 1 10 0v4" />
    </svg>
  ),
};

const navItems = [
  { id: "overview",  label: "Dashboard",        Icon: Icons.Dashboard       },
  { id: "agents",    label: "Agents",            Icon: Icons.Agents          },
  { id: "sessions",  label: "Sessions",          Icon: Icons.Sessions        },
  { id: "approvals", label: "Approvals",         Icon: Icons.Approvals       },
  { id: "activity",  label: "Runtime Activity",  Icon: Icons.RuntimeActivity },
  { id: "audit",     label: "Audit Log",         Icon: Icons.AuditLog        },
  { id: "policies",  label: "Policies",          Icon: Icons.Policies        },
  { id: "health",    label: "System Health",     Icon: Icons.SystemHealth    },
] as const;

export const Sidebar: React.FC<SidebarProps> = ({
  activeTab,
  onSelectTab,
  activeAgentsCount = 0,
  blockedCount = 0,
  pendingApprovalsCount = 0,
}) => {

  return (
    <aside
      id="sidebar-navigation"
      style={{
        width: "230px",
        background: "#0b1329",
        borderRight: "1px solid rgba(255, 255, 255, 0.08)",
        display: "flex",
        flexDirection: "column",
        height: "100vh",
        position: "sticky",
        top: 0,
        flexShrink: 0,
        overflowY: "auto",
      }}
    >
      {/* ── Brand ── */}
      <div
        style={{
          padding: "20px 18px 18px",
          borderBottom: "1px solid rgba(255, 255, 255, 0.08)",
          display: "flex",
          alignItems: "center",
          gap: "12px",
        }}
      >
        {/* Monogram badge with glowing dot */}
        <div
          style={{
            position: "relative",
            width: "34px",
            height: "34px",
            borderRadius: "10px",
            background: "linear-gradient(135deg, #3b82f6 0%, #1d4ed8 100%)",
            border: "1px solid rgba(255, 255, 255, 0.2)",
            boxShadow: "0 0 16px rgba(59, 130, 246, 0.4)",
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
            flexShrink: 0,
            color: "#ffffff",
          }}
        >
          <Icons.Shield size={18} />
          <span
            style={{
              position: "absolute",
              bottom: "7px",
              right: "7px",
              width: "4px",
              height: "4px",
              borderRadius: "50%",
              background: "#60a5fa",
              boxShadow: "0 0 6px #60a5fa",
            }}
          />
        </div>
        <div>
          <div
            style={{
              fontWeight: 700,
              fontSize: "0.8125rem",
              letterSpacing: "0.04em",
              color: "#ffffff",
              lineHeight: 1.2,
            }}
          >
            AGENT<br />GOVERNANCE
          </div>
          <div
            style={{
              fontSize: "0.5625rem",
              color: "#64748b",
              fontFamily: "var(--font-mono)",
              letterSpacing: "0.08em",
              textTransform: "uppercase",
              marginTop: "2px",
            }}
          >
            RUNTIME GATEWAY
          </div>
        </div>
      </div>

      {/* ── Workspace label ── */}
      <div
        style={{
          padding: "16px 16px 8px",
          fontSize: "0.625rem",
          fontWeight: 600,
          letterSpacing: "0.1em",
          textTransform: "uppercase",
          color: "#64748b",
          fontFamily: "var(--font-mono)",
        }}
      >
        WORKSPACE
      </div>

      {/* ── Nav items ── */}
      <nav
        aria-label="Main navigation"
        style={{ flex: 1, display: "flex", flexDirection: "column", gap: "4px", padding: "0 10px" }}
      >
        {navItems.map(({ id, label, Icon }) => {
          const isActive = activeTab === id;

          return (
            <button
              key={id}
              id={`nav-${id}`}
              onClick={() => onSelectTab(id)}
              aria-current={isActive ? "page" : undefined}
              style={{
                display: "flex",
                alignItems: "center",
                padding: "9px 12px",
                borderRadius: "10px",
                background: isActive ? "#2563eb" : "transparent",
                color: isActive ? "#ffffff" : "#94a3b8",
                border: isActive
                  ? "1px solid #3b82f6"
                  : "1px solid transparent",
                boxShadow: isActive ? "0 4px 14px rgba(37, 99, 235, 0.35)" : "none",
                cursor: "pointer",
                fontWeight: isActive ? 600 : 500,
                fontSize: "0.8125rem",
                textAlign: "left",
                width: "100%",
                transition: "all 0.15s ease",
                gap: "8px",
              }}
              onMouseEnter={(e) => {
                if (!isActive) {
                  (e.currentTarget as HTMLButtonElement).style.background = "rgba(255, 255, 255, 0.06)";
                  (e.currentTarget as HTMLButtonElement).style.color = "#ffffff";
                }
              }}
              onMouseLeave={(e) => {
                if (!isActive) {
                  (e.currentTarget as HTMLButtonElement).style.background = "transparent";
                  (e.currentTarget as HTMLButtonElement).style.color = "#94a3b8";
                }
              }}
            >
              <span style={{ display: "flex", alignItems: "center", gap: "10px", flex: 1, minWidth: 0 }}>
                <span style={{ flexShrink: 0, opacity: isActive ? 1 : 0.8, color: isActive ? "#ffffff" : "currentColor" }}>
                  <Icon size={16} />
                </span>
                <span
                  style={{
                    overflow: "hidden",
                    textOverflow: "ellipsis",
                    whiteSpace: "nowrap",
                  }}
                >
                  {label}
                </span>
              </span>
            </button>
          );
        })}
      </nav>

      {/* ── Bottom status card ── */}
      <div
        style={{
          margin: "12px 10px 18px",
          background: "linear-gradient(180deg, #17243b 0%, #0f182c 100%)",
          border: "1px solid rgba(59, 130, 246, 0.25)",
          borderRadius: "14px",
          padding: "16px 14px",
          display: "flex",
          flexDirection: "column",
          gap: "8px",
          boxShadow: "0 8px 24px rgba(0, 0, 0, 0.2)",
        }}
      >
        <div
          style={{
            display: "flex",
            alignItems: "center",
            gap: "8px",
            color: "#38bdf8",
          }}
        >
          <div
            style={{
              width: "28px",
              height: "28px",
              borderRadius: "8px",
              background: "rgba(56, 189, 248, 0.15)",
              border: "1px solid rgba(56, 189, 248, 0.3)",
              display: "flex",
              alignItems: "center",
              justifyContent: "center",
              color: "#38bdf8",
            }}
          >
            <Icons.Lock size={14} />
          </div>
          <span
            style={{
              fontWeight: 700,
              fontSize: "0.75rem",
              fontFamily: "var(--font-mono)",
              letterSpacing: "0.04em",
              textTransform: "uppercase",
              color: "#ffffff",
            }}
          >
            PRE-EXECUTION GATE
          </span>
        </div>
        <div
          style={{
            color: "#94a3b8",
            fontSize: "0.6875rem",
            lineHeight: "1.45",
          }}
        >
          Every tool call is checked against deterministic policy before execution.
        </div>
      </div>
    </aside>
  );
};
