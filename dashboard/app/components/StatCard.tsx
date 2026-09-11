"use client";

import React from "react";

interface StatCardProps {
  id: string;
  title: string;
  value: string | number;
  subtitle: string;
  icon: string;
  accentColor?: string;
  trend?: string;
}

export const StatCard: React.FC<StatCardProps> = ({
  id,
  title,
  value,
  subtitle,
  icon,
  accentColor = "var(--accent-cyan)",
  trend,
}) => {
  return (
    <div
      id={id}
      className="glass-panel"
      style={{
        padding: "20px",
        display: "flex",
        flexDirection: "column",
        justifyContent: "space-between",
        gap: "12px",
        position: "relative",
        overflow: "hidden",
      }}
    >
      {/* Background glow accent */}
      <div
        style={{
          position: "absolute",
          top: "-20px",
          right: "-20px",
          width: "80px",
          height: "80px",
          borderRadius: "50%",
          background: accentColor,
          opacity: 0.08,
          filter: "blur(20px)",
          pointerEvents: "none",
        }}
      />

      <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between" }}>
        <span style={{ fontSize: "0.85rem", color: "var(--text-secondary)", fontWeight: 500 }}>
          {title}
        </span>
        <span style={{ fontSize: "1.2rem" }}>{icon}</span>
      </div>

      <div style={{ display: "flex", alignItems: "baseline", gap: "10px" }}>
        <span
          style={{
            fontSize: "1.8rem",
            fontWeight: 800,
            color: "var(--text-primary)",
            fontFamily: "var(--font-mono)",
            letterSpacing: "-0.02em",
          }}
        >
          {value}
        </span>
        {trend && (
          <span
            style={{
              fontSize: "0.75rem",
              color: trend.startsWith("+") ? "#10B981" : "#F43F5E",
              fontFamily: "var(--font-mono)",
              fontWeight: 600,
            }}
          >
            {trend}
          </span>
        )}
      </div>

      <div style={{ fontSize: "0.75rem", color: "var(--text-muted)" }}>
        {subtitle}
      </div>
    </div>
  );
};
