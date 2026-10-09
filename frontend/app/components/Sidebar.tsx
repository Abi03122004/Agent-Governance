"use client";

import React from "react";

interface SidebarProps {
  activeTab: string;
  onSelectTab: (tab: string) => void;
  activeAgentsCount?: number;
  blockedCount?: number;
}

export const Sidebar: React.FC<SidebarProps> = ({
  activeTab,
  onSelectTab,
  activeAgentsCount = 0,
  blockedCount = 0,
}) => {
  const navItems = [
    { id: "overview", label: "Dashboard", icon: "⚡", badge: null },
    { id: "agents", label: "Agents", icon: "🤖", badge: activeAgentsCount ? `${activeAgentsCount}` : null },
    { id: "sessions", label: "Sessions", icon: "⏱️", badge: null },
    { id: "activity", label: "Runtime Activity", icon: "🛰️", badge: blockedCount > 0 ? `${blockedCount} BLOCKED` : "LIVE" },
    { id: "policies", label: "Policies", icon: "📜", badge: null },
    { id: "health", label: "System Health", icon: "💚", badge: "READY" },
  ];

  return (
    <aside
      id="sidebar-navigation"
      style={{
        width: "240px",
        background: "var(--panel-bg)",
        borderRight: "1px solid var(--border-rule)",
        display: "flex",
        flexDirection: "column",
        padding: "20px 12px",
        height: "100vh",
        position: "sticky",
        top: 0,
        flexShrink: 0,
      }}
    >
      {/* Brand & Platform Emblem */}
      <div style={{ display: "flex", alignItems: "center", gap: "10px", marginBottom: "28px", paddingLeft: "6px" }}>
        <div
          style={{
            width: "32px",
            height: "32px",
            borderRadius: "3px",
            background: "var(--surface-plate)",
            border: "1px solid var(--border-rule)",
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
            fontWeight: 700,
            color: "var(--accent-telegraph)",
            fontSize: "0.85rem",
            fontFamily: "var(--font-mono)",
          }}
        >
          AG
        </div>
        <div>
          <div style={{ fontWeight: 600, fontSize: "0.8125rem", letterSpacing: "0.02em", color: "var(--text-primary)" }}>
            AGENT GOVERNANCE
          </div>
          <div style={{ fontSize: "0.6875rem", color: "var(--text-muted)", fontFamily: "var(--font-mono)" }}>
            RUNTIME GATEWAY
          </div>
        </div>
      </div>

      {/* Navigation Links */}
      <nav style={{ display: "flex", flexDirection: "column", gap: "3px", flex: 1 }}>
        {navItems.map((item) => {
          const isActive = activeTab === item.id;
          return (
            <button
              key={item.id}
              id={`nav-${item.id}`}
              onClick={() => onSelectTab(item.id)}
              style={{
                display: "flex",
                alignItems: "center",
                justifyContent: "space-between",
                padding: "8px 12px",
                borderRadius: "3px",
                background: isActive ? "var(--surface-plate)" : "transparent",
                color: isActive ? "var(--text-primary)" : "var(--text-secondary)",
                border: "none",
                borderLeft: isActive ? "3px solid var(--accent-telegraph)" : "3px solid transparent",
                cursor: "pointer",
                fontWeight: isActive ? 600 : 400,
                fontSize: "0.8125rem",
                textAlign: "left",
                transition: "background 0.1s ease, color 0.1s ease",
              }}
            >
              <span style={{ display: "flex", alignItems: "center", gap: "9px" }}>
                <span style={{ fontSize: "0.9rem" }}>{item.icon}</span>
                <span>{item.label}</span>
              </span>
              {item.badge && (
                <span
                  style={{
                    fontSize: "0.65rem",
                    padding: "2px 5px",
                    borderRadius: "2px",
                    background:
                      item.badge === "LIVE"
                        ? "var(--status-allow-bg)"
                        : item.badge === "READY"
                        ? "var(--accent-telegraph-subtle)"
                        : "var(--status-block-bg)",
                    color:
                      item.badge === "LIVE"
                        ? "var(--status-allow-fg)"
                        : item.badge === "READY"
                        ? "#79C0FF"
                        : "var(--status-block-fg)",
                    border: `1px solid ${
                      item.badge === "LIVE"
                        ? "var(--status-allow-border)"
                        : item.badge === "READY"
                        ? "rgba(2, 132, 199, 0.3)"
                        : "var(--status-block-border)"
                    }`,
                    fontFamily: "var(--font-mono)",
                    fontWeight: 600,
                  }}
                >
                  {item.badge}
                </span>
              )}
            </button>
          );
        })}
      </nav>

      {/* Control Plane Guard Status */}
      <div
        style={{
          background: "var(--surface-plate)",
          border: "1px solid var(--border-rule)",
          borderRadius: "3px",
          padding: "10px",
          display: "flex",
          flexDirection: "column",
          gap: "5px",
          fontSize: "0.75rem",
        }}
      >
        <div style={{ display: "flex", alignItems: "center", gap: "6px", color: "var(--status-allow-fg)" }}>
          <span className="status-dot status-dot-active" />
          <span style={{ fontWeight: 600, fontSize: "0.7rem", fontFamily: "var(--font-mono)" }}>PRE-EXECUTION GATE</span>
        </div>
        <div style={{ color: "var(--text-muted)", fontSize: "0.6875rem", lineHeight: "1.4" }}>
          In-line mediation active. Blocked operations reject with zero credential exposure.
        </div>
      </div>
    </aside>
  );
};
