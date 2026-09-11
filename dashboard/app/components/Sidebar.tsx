"use client";

import React from "react";

interface SidebarProps {
  activeTab: string;
  onSelectTab: (tab: string) => void;
}

export const Sidebar: React.FC<SidebarProps> = ({ activeTab, onSelectTab }) => {
  const navItems = [
    { id: "overview", label: "Mission Control", icon: "⚡", badge: null },
    { id: "stream", label: "Interception Stream", icon: "🛰️", badge: "LIVE" },
    { id: "approvals", label: "Human Approvals", icon: "🛡️", badge: "3" },
    { id: "policies", label: "Policy Guardrails", icon: "📜", badge: null },
    { id: "audit", label: "Audit & Lineage", icon: "⛓️", badge: null },
    { id: "agents", label: "Agent Identities", icon: "🤖", badge: "12" },
    { id: "health", label: "System Health", icon: "💚", badge: "READY" },
  ];

  return (
    <aside
      id="sidebar-navigation"
      style={{
        width: "260px",
        background: "var(--bg-secondary)",
        borderRight: "1px solid var(--border-subtle)",
        display: "flex",
        flexDirection: "column",
        padding: "24px 16px",
        height: "100vh",
        position: "sticky",
        top: 0,
      }}
    >
      {/* Brand & Platform Emblem */}
      <div style={{ display: "flex", alignItems: "center", gap: "12px", marginBottom: "32px", paddingLeft: "8px" }}>
        <div
          style={{
            width: "36px",
            height: "36px",
            borderRadius: "10px",
            background: "linear-gradient(135deg, #00F0FF 0%, #0070F3 100%)",
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
            boxShadow: "0 0 16px rgba(0, 240, 255, 0.4)",
            fontWeight: 800,
            color: "#000",
            fontSize: "1.2rem",
          }}
        >
          AG
        </div>
        <div>
          <div style={{ fontWeight: 700, fontSize: "0.95rem", letterSpacing: "0.02em", color: "var(--text-primary)" }}>
            AGENT GOVERNANCE
          </div>
          <div style={{ fontSize: "0.7rem", color: "var(--accent-cyan)", fontFamily: "var(--font-mono)" }}>
            RUNTIME DEFENSE
          </div>
        </div>
      </div>

      {/* Navigation Links */}
      <nav style={{ display: "flex", flexDirection: "column", gap: "6px", flex: 1 }}>
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
                padding: "10px 14px",
                borderRadius: "8px",
                background: isActive ? "rgba(0, 240, 255, 0.08)" : "transparent",
                color: isActive ? "var(--accent-cyan)" : "var(--text-secondary)",
                border: isActive ? "1px solid rgba(0, 240, 255, 0.25)" : "1px solid transparent",
                cursor: "pointer",
                fontWeight: isActive ? 600 : 500,
                fontSize: "0.875rem",
                textAlign: "left",
                transition: "all 0.15s ease",
              }}
            >
              <span style={{ display: "flex", alignItems: "center", gap: "10px" }}>
                <span>{item.icon}</span>
                <span>{item.label}</span>
              </span>
              {item.badge && (
                <span
                  style={{
                    fontSize: "0.65rem",
                    padding: "2px 6px",
                    borderRadius: "4px",
                    background: item.badge === "LIVE" ? "rgba(16, 185, 129, 0.2)" : item.badge === "READY" ? "rgba(59, 130, 246, 0.2)" : "rgba(245, 158, 11, 0.2)",
                    color: item.badge === "LIVE" ? "#10B981" : item.badge === "READY" ? "#38BDF8" : "#F59E0B",
                    fontFamily: "var(--font-mono)",
                    fontWeight: 700,
                  }}
                >
                  {item.badge}
                </span>
              )}
            </button>
          );
        })}
      </nav>

      {/* Fail-Secure Indicator Footer */}
      <div
        className="glass-panel"
        style={{
          padding: "12px",
          display: "flex",
          flexDirection: "column",
          gap: "6px",
          fontSize: "0.75rem",
        }}
      >
        <div style={{ display: "flex", alignItems: "center", gap: "6px", color: "var(--status-allow-fg)" }}>
          <span className="status-dot status-dot-active status-dot-pulse" />
          <span style={{ fontWeight: 600 }}>FAIL-SECURE: ACTIVE</span>
        </div>
        <div style={{ color: "var(--text-muted)", fontSize: "0.7rem" }}>
          In-line broker enforcing strict zero-credential mediation.
        </div>
      </div>
    </aside>
  );
};
