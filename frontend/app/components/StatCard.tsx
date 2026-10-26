"use client";

import React, { useId } from "react";

interface StatCardProps {
  id: string;
  title: string;
  value: string | number;
  subtitle: string;
  icon: React.ReactNode;
  accentColor?: string;
  trend?: string;
}

const resolvePastelTheme = (color: string) => {
  if (color.includes("allow") || color.includes("059669") || color.includes("10b981")) {
    return { bg: "#ecfdf5", border: "#d1fae5", text: "#059669", spark: "#10b981" };
  }
  if (color.includes("block") || color.includes("danger") || color.includes("dc2626") || color.includes("ef4444")) {
    return { bg: "#fef2f2", border: "#fee2e2", text: "#dc2626", spark: "#ef4444" };
  }
  if (color.includes("approval") || color.includes("warning") || color.includes("d97706") || color.includes("f59e0b")) {
    return { bg: "#fffbeb", border: "#fef3c7", text: "#d97706", spark: "#f59e0b" };
  }
  if (color.includes("suspend") || color.includes("ea580c") || color.includes("f97316")) {
    return { bg: "#fff7ed", border: "#ffedd5", text: "#ea580c", spark: "#f97316" };
  }
  if (color.includes("purple") || color.includes("7c3aed")) {
    return { bg: "#f5f3ff", border: "#ede9fe", text: "#7c3aed", spark: "#8b5cf6" };
  }
  return { bg: "#eff6ff", border: "#dbeafe", text: "#2563eb", spark: "#2563eb" };
};

export const StatCard: React.FC<StatCardProps> = ({
  id,
  title,
  value,
  subtitle,
  icon,
  accentColor = "#2563eb",
  trend,
}) => {
  const theme = resolvePastelTheme(accentColor);
  const reactId = useId();
  const gradId = `spark-grad-${reactId.replace(/:/g, "")}`;
  const isPositive = !trend || trend.startsWith("+");

  return (
    <div
      id={id}
      style={{
        background: "#ffffff",
        border: "1px solid #eef2f6",
        borderRadius: "16px",
        padding: "18px 20px",
        display: "flex",
        flexDirection: "column",
        justifyContent: "space-between",
        minHeight: "128px",
        boxShadow: "0 2px 8px rgba(15, 23, 42, 0.04), 0 1px 2px rgba(15, 23, 42, 0.02)",
        transition: "all 0.2s cubic-bezier(0.16, 1, 0.3, 1)",
        position: "relative",
        overflow: "hidden",
      }}
      onMouseEnter={(e) => {
        (e.currentTarget as HTMLDivElement).style.borderColor = "rgba(37, 99, 235, 0.25)";
        (e.currentTarget as HTMLDivElement).style.transform = "translateY(-2px)";
        (e.currentTarget as HTMLDivElement).style.boxShadow = "0 8px 24px rgba(15, 23, 42, 0.08)";
      }}
      onMouseLeave={(e) => {
        (e.currentTarget as HTMLDivElement).style.borderColor = "#eef2f6";
        (e.currentTarget as HTMLDivElement).style.transform = "translateY(0)";
        (e.currentTarget as HTMLDivElement).style.boxShadow = "0 2px 8px rgba(15, 23, 42, 0.04), 0 1px 2px rgba(15, 23, 42, 0.02)";
      }}
    >
      {/* Top row: Squircle icon + Title */}
      <div style={{ display: "flex", alignItems: "center", gap: "12px" }}>
        <div
          style={{
            width: "40px",
            height: "40px",
            borderRadius: "12px",
            background: theme.bg,
            border: `1px solid ${theme.border}`,
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
            flexShrink: 0,
            color: theme.text,
            fontSize: "1.1rem",
          }}
        >
          {icon}
        </div>
        <span
          style={{
            fontSize: "0.8125rem",
            fontWeight: 500,
            color: "#64748b",
            letterSpacing: "-0.01em",
            lineHeight: 1.3,
          }}
        >
          {title}
        </span>
      </div>

      {/* Middle row: Big Value + Trend + SVG Sparkline curve */}
      <div
        style={{
          display: "flex",
          alignItems: "flex-end",
          justifyContent: "space-between",
          marginTop: "12px",
          gap: "8px",
        }}
      >
        <div>
          <div
            style={{
              fontSize: "1.875rem",
              fontWeight: 700,
              color: "#0f172a",
              letterSpacing: "-0.03em",
              lineHeight: 1,
            }}
          >
            {value}
          </div>
          <div style={{ display: "flex", alignItems: "center", gap: "6px", marginTop: "6px" }}>
            {trend && (
              <span
                style={{
                  fontSize: "0.75rem",
                  fontWeight: 600,
                  color: isPositive ? "#10b981" : "#ef4444",
                  display: "inline-flex",
                  alignItems: "center",
                  gap: "3px",
                }}
              >
                <span>{isPositive ? "▲" : "▼"}</span>
                {trend}
              </span>
            )}
            <span
              style={{
                fontSize: "0.6875rem",
                color: "#94a3b8",
                lineHeight: 1.2,
              }}
            >
              {subtitle}
            </span>
          </div>
        </div>

        {/* Render sparkline only when there is real non-zero metric activity and trend */}
        {trend && Number(value) > 0 && (
          <div style={{ flexShrink: 0, opacity: 0.9 }}>
            <svg width="78" height="32" viewBox="0 0 78 32" fill="none" style={{ overflow: "visible" }}>
              <defs>
                <linearGradient id={gradId} x1="0" y1="0" x2="0" y2="1">
                  <stop offset="0%" stopColor={theme.spark} stopOpacity="0.25" />
                  <stop offset="100%" stopColor={theme.spark} stopOpacity="0.0" />
                </linearGradient>
              </defs>
              <path
                d={
                  isPositive
                    ? "M 2 24 C 20 22, 34 28, 48 12 C 58 2, 68 8, 76 3 L 76 32 L 2 32 Z"
                    : "M 2 8 C 20 10, 34 6, 48 18 C 58 28, 68 20, 76 26 L 76 32 L 2 32 Z"
                }
                fill={`url(#${gradId})`}
              />
              <path
                d={
                  isPositive
                    ? "M 2 24 C 20 22, 34 28, 48 12 C 58 2, 68 8, 76 3"
                    : "M 2 8 C 20 10, 34 6, 48 18 C 58 28, 68 20, 76 26"
                }
                stroke={theme.spark}
                strokeWidth="2.2"
                strokeLinecap="round"
                strokeLinejoin="round"
              />
            </svg>
          </div>
        )}
      </div>
    </div>
  );
};
