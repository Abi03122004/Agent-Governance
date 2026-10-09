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
  accentColor = "var(--accent-telegraph)",
  trend,
}) => {
  return (
    <div
      id={id}
      style={{
        background: "var(--panel-bg)",
        border: "1px solid var(--border-rule)",
        borderTop: `2px solid ${accentColor}`,
        borderRadius: "3px",
        padding: "14px 16px",
        display: "flex",
        flexDirection: "column",
        justifyContent: "space-between",
        gap: "8px",
        minHeight: "105px",
      }}
    >
      <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between" }}>
        <span style={{ fontSize: "0.75rem", color: "var(--text-secondary)", fontWeight: 500 }}>
          {title}
        </span>
        <span style={{ fontSize: "1rem", opacity: 0.8 }}>{icon}</span>
      </div>

      <div style={{ display: "flex", alignItems: "baseline", gap: "8px" }}>
        <span
          style={{
            fontSize: "1.5rem",
            fontWeight: 600,
            color: "var(--text-primary)",
            fontFamily: "var(--font-mono)",
            fontVariantNumeric: "tabular-nums",
            letterSpacing: "-0.03em",
            lineHeight: 1,
          }}
        >
          {value}
        </span>
        {trend && (
          <span
            style={{
              fontSize: "0.6875rem",
              color: trend.startsWith("+") ? "var(--status-allow-fg)" : "var(--status-block-fg)",
              fontFamily: "var(--font-mono)",
              fontWeight: 600,
            }}
          >
            {trend}
          </span>
        )}
      </div>

      <div style={{ fontSize: "0.6875rem", color: "var(--text-muted)", maxWidth: "60ch" }}>
        {subtitle}
      </div>
    </div>
  );
};
