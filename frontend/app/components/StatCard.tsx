"use client";

import React from "react";

interface StatCardProps {
  id: string;
  title: string;
  value: string | number;
  subtitle?: string;
  icon: React.ReactNode;
  badge?: string;
  badgeType?: "default" | "success" | "warning" | "danger" | "purple";
  onClick?: () => void;
}

export const StatCard: React.FC<StatCardProps> = ({
  id,
  title,
  value,
  subtitle,
  icon,
  badge,
  badgeType = "default",
  onClick,
}) => {
  const getBadgeStyle = () => {
    switch (badgeType) {
      case "success":
        return {
          background: "rgba(16, 185, 129, 0.12)",
          color: "#10B981",
          border: "1px solid rgba(16, 185, 129, 0.25)",
        };
      case "danger":
        return {
          background: "rgba(255, 73, 47, 0.14)",
          color: "#FF492F",
          border: "1px solid rgba(255, 73, 47, 0.3)",
        };
      case "warning":
        return {
          background: "rgba(255, 152, 0, 0.12)",
          color: "#FFA726",
          border: "1px solid rgba(255, 152, 0, 0.3)",
        };
      case "purple":
        return {
          background: "rgba(137, 85, 255, 0.14)",
          color: "#A78BFA",
          border: "1px solid rgba(137, 85, 255, 0.3)",
        };
      default:
        return {
          background: "#242328",
          color: "#A1A1A8",
          border: "1px solid #333238",
        };
    }
  };

  const badgeStyle = getBadgeStyle();

  return (
    <div
      id={id}
      onClick={onClick}
      style={{
        background: "#18171B",
        border: "1px solid #262529",
        borderRadius: "18px",
        padding: "16px 18px",
        display: "flex",
        flexDirection: "column",
        justifyContent: "space-between",
        minHeight: "100px",
        boxShadow: "0 4px 18px rgba(0, 0, 0, 0.35)",
        transition: "all 0.2s cubic-bezier(0.16, 1, 0.3, 1)",
        position: "relative",
        cursor: onClick ? "pointer" : "default",
      }}
      onMouseEnter={(e) => {
        e.currentTarget.style.borderColor = "rgba(255, 73, 47, 0.35)";
        e.currentTarget.style.transform = "translateY(-2px)";
        e.currentTarget.style.boxShadow = "0 8px 24px rgba(0, 0, 0, 0.5), 0 0 12px rgba(255, 73, 47, 0.1)";
      }}
      onMouseLeave={(e) => {
        e.currentTarget.style.borderColor = "#262529";
        e.currentTarget.style.transform = "translateY(0)";
        e.currentTarget.style.boxShadow = "0 4px 18px rgba(0, 0, 0, 0.35)";
      }}
    >
      {/* Top Row: Icon + Title */}
      <div style={{ display: "flex", alignItems: "center", gap: "9px" }}>
        <div
          style={{
            color: "#858585",
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
          }}
        >
          {icon}
        </div>
        <span
          style={{
            fontSize: "0.75rem",
            fontWeight: 500,
            color: "#858585",
            letterSpacing: "-0.01em",
          }}
        >
          {title}
        </span>
      </div>

      {/* Bottom Row: Big Bold Stat + Badge */}
      <div
        style={{
          display: "flex",
          alignItems: "baseline",
          justifyContent: "space-between",
          marginTop: "12px",
          gap: "8px",
        }}
      >
        <span
          style={{
            fontSize: "1.65rem",
            fontWeight: 700,
            color: "#F5F5F5",
            fontFamily: "var(--font-family)",
            letterSpacing: "-0.03em",
            lineHeight: 1.1,
          }}
        >
          {typeof value === "number" ? value.toLocaleString() : value}
        </span>

        {badge && (
          <span
            style={{
              padding: "2px 8px",
              borderRadius: "12px",
              fontSize: "0.6875rem",
              fontWeight: 600,
              fontFamily: "var(--font-mono)",
              lineHeight: 1.4,
              ...badgeStyle,
            }}
          >
            {badge}
          </span>
        )}
      </div>

      {subtitle && (
        <div style={{ fontSize: "0.6875rem", color: "#5E5E66", marginTop: "4px" }}>
          {subtitle}
        </div>
      )}
    </div>
  );
};
