"use client";

import React, { useState, useMemo } from "react";

export interface PolicyRuleData {
  id: string;
  name: string;
  decision: "ALLOW" | "BLOCK" | "REQUIRE_APPROVAL" | "SUSPEND" | string;
  condition: string;
  description: string;
  priority: number | string;
  status: string;
  category?: string;
  scope?: string;
  showEvaluationBanner?: boolean;
}

interface PolicyEnforcementViewProps {
  initialRules?: PolicyRuleData[];
}

/* ── Crisp SVG Icons matching the reference theme ── */
const Icons = {
  Shield: ({ size = 16, color = "currentColor" }: { size?: number; color?: string }) => (
    <svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke={color} strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
      <path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z" />
    </svg>
  ),
  ShieldCheck: ({ size = 16, color = "currentColor" }: { size?: number; color?: string }) => (
    <svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke={color} strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
      <path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z" />
      <path d="m9 12 2 2 4-4" />
    </svg>
  ),
  Lock: ({ size = 16, color = "currentColor" }: { size?: number; color?: string }) => (
    <svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke={color} strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
      <rect x="3" y="11" width="18" height="11" rx="2" ry="2" />
      <path d="M7 11V7a5 5 0 0 1 10 0v4" />
    </svg>
  ),
  Network: ({ size = 16, color = "currentColor" }: { size?: number; color?: string }) => (
    <svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke={color} strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
      <circle cx="18" cy="5" r="3" />
      <circle cx="6" cy="12" r="3" />
      <circle cx="18" cy="19" r="3" />
      <line x1="8.59" y1="13.51" x2="15.42" y2="17.49" />
      <line x1="15.41" y1="6.51" x2="8.59" y2="10.49" />
    </svg>
  ),
  Hierarchy: ({ size = 16, color = "currentColor" }: { size?: number; color?: string }) => (
    <svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke={color} strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
      <rect x="9" y="3" width="6" height="6" rx="1" />
      <rect x="3" y="15" width="6" height="6" rx="1" />
      <rect x="15" y="15" width="6" height="6" rx="1" />
      <path d="M12 9v3m-6 3v-3h12v3" />
    </svg>
  ),
  Pulse: ({ size = 16, color = "currentColor" }: { size?: number; color?: string }) => (
    <svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke={color} strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
      <polyline points="22 12 18 12 15 21 9 3 6 12 2 12" />
    </svg>
  ),
  Vault: ({ size = 16, color = "currentColor" }: { size?: number; color?: string }) => (
    <svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke={color} strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
      <path d="M12 2L2 7l10 5 10-5-10-5z" />
      <path d="M2 17l10 5 10-5" />
      <path d="M2 12l10 5 10-5" />
    </svg>
  ),
  ClipboardCheck: ({ size = 16, color = "currentColor" }: { size?: number; color?: string }) => (
    <svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke={color} strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
      <path d="M16 4h2a2 2 0 0 1 2 2v14a2 2 0 0 1-2 2H6a2 2 0 0 1-2-2V6a2 2 0 0 1 2-2h2" />
      <rect x="8" y="2" width="8" height="4" rx="1" ry="1" />
      <path d="m9 14 2 2 4-4" />
    </svg>
  ),
  PowerCircle: ({ size = 16, color = "currentColor" }: { size?: number; color?: string }) => (
    <svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke={color} strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
      <circle cx="12" cy="12" r="10" />
      <path d="M12 6v6" />
    </svg>
  ),
  Search: ({ size = 14, color = "currentColor" }: { size?: number; color?: string }) => (
    <svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke={color} strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
      <circle cx="11" cy="11" r="8" />
      <line x1="21" y1="21" x2="16.65" y2="16.65" />
    </svg>
  ),
  Filter: ({ size = 14, color = "currentColor" }: { size?: number; color?: string }) => (
    <svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke={color} strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
      <line x1="4" y1="21" x2="4" y2="14" />
      <line x1="4" y1="10" x2="4" y2="3" />
      <line x1="12" y1="21" x2="12" y2="12" />
      <line x1="12" y1="8" x2="12" y2="3" />
      <line x1="20" y1="21" x2="20" y2="16" />
      <line x1="20" y1="12" x2="20" y2="3" />
      <line x1="1" y1="14" x2="7" y2="14" />
      <line x1="9" y1="8" x2="15" y2="8" />
      <line x1="17" y1="16" x2="23" y2="16" />
    </svg>
  ),
  Copy: ({ size = 13, color = "currentColor" }: { size?: number; color?: string }) => (
    <svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke={color} strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
      <rect x="9" y="9" width="13" height="13" rx="2" ry="2" />
      <path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1" />
    </svg>
  ),
  Check: ({ size = 13, color = "currentColor" }: { size?: number; color?: string }) => (
    <svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke={color} strokeWidth="2.2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
      <polyline points="20 6 9 17 4 12" />
    </svg>
  ),
  Globe: ({ size = 13, color = "currentColor" }: { size?: number; color?: string }) => (
    <svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke={color} strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
      <circle cx="12" cy="12" r="10" />
      <line x1="2" y1="12" x2="22" y2="12" />
      <path d="M12 2a15.3 15.3 0 0 1 4 10 15.3 15.3 0 0 1-4 10 15.3 15.3 0 0 1-4-10 15.3 15.3 0 0 1 4-10z" />
    </svg>
  ),
  Plus: ({ size = 14, color = "currentColor" }: { size?: number; color?: string }) => (
    <svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke={color} strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
      <line x1="12" y1="5" x2="12" y2="19" />
      <line x1="5" y1="12" x2="19" y2="12" />
    </svg>
  ),
};

/* ── The 6 Exact Canonical Deterministic Policies from the Theme ── */
const DEFAULT_RULES: PolicyRuleData[] = [
  {
    id: "pol_agent_suspension",
    name: "Agent Suspension Enforcement",
    decision: "SUSPEND",
    condition: "identity.status == 'suspended'",
    description: "Immediately halts any action from an agent flagged as suspended or revoked by an administrator or risk policy.",
    priority: "1",
    status: "active",
    category: "Identity",
    scope: "Before execution",
  },
  {
    id: "pol_destructive_block",
    name: "Destructive Operations Block",
    decision: "BLOCK",
    condition: "operation in ['delete', 'drop', 'destroy']",
    description: "Completely forbids unapproved destructive side-effects on platform or tenant databases.",
    priority: "2",
    status: "active",
    category: "Operations",
    scope: "All tenants",
    showEvaluationBanner: true,
  },
  {
    id: "pol_external_egress",
    name: "External Network Egress Guard",
    decision: "BLOCK",
    condition: "tool in ['external', 'http'] and operation in ['send', 'post', 'write']",
    description: "Restricts external outbound calls to prevent data exfiltration.",
    priority: "3",
    status: "active",
    category: "Network",
    scope: "Outbound",
  },
  {
    id: "pol_secrets_protection",
    name: "Restricted Resources & Secrets Sandbox",
    decision: "BLOCK",
    condition: "resource starts with ('secrets', 'credentials', 'forbidden')",
    description: "Blocks agent access to restricted resource scopes and system credentials.",
    priority: "4",
    status: "active",
    category: "Resources",
    scope: "Sensitive scopes",
  },
  {
    id: "pol_mutation_approval",
    name: "Production Mutation Approval Required",
    decision: "REQUIRE_APPROVAL",
    condition: "operation in ['write', 'update'] and tool != 'safe_echo'",
    description: "Requires human approver cryptographic sign-off before committing state changes.",
    priority: "5",
    status: "active",
    category: "Production",
    scope: "Human approval",
  },
  {
    id: "pol_allow_permitted",
    name: "Deterministic Allowed Operations",
    decision: "ALLOW",
    condition: "authorized + permitted in contract",
    description: "Permits safe read operations and validated tool execution with a single-use authorization token.",
    priority: "999",
    status: "active",
    category: "Contract",
    scope: "Authorized actions",
  },
];

export const PolicyEnforcementView: React.FC<PolicyEnforcementViewProps> = ({ initialRules }) => {
  const [rules, setRules] = useState<PolicyRuleData[]>(() => {
    if (Array.isArray(initialRules)) {
      return initialRules;
    }
    return [];
  });

  React.useEffect(() => {
    if (Array.isArray(initialRules)) {
      setRules(initialRules);
    }
  }, [initialRules]);

  const [searchQuery, setSearchQuery] = useState("");
  const [filterDecision, setFilterDecision] = useState<string>("ALL");
  const [copiedRuleId, setCopiedRuleId] = useState<string | null>(null);
  const [isNewPolicyModalOpen, setIsNewPolicyModalOpen] = useState(false);
  const [newRuleForm, setNewRuleForm] = useState({
    name: "",
    decision: "BLOCK",
    condition: "",
    description: "",
    priority: "10",
    category: "Custom",
    scope: "Tenant scope",
  });

  const handleCopyCondition = async (ruleId: string, condition: string) => {
    try {
      await navigator.clipboard.writeText(condition);
      setCopiedRuleId(ruleId);
      setTimeout(() => setCopiedRuleId(null), 1800);
    } catch (e) {
      console.error("Failed to copy condition", e);
    }
  };

  const filteredRules = useMemo(() => {
    return rules.filter((r) => {
      const matchesSearch =
        searchQuery === "" ||
        r.name.toLowerCase().includes(searchQuery.toLowerCase()) ||
        r.id.toLowerCase().includes(searchQuery.toLowerCase()) ||
        r.condition.toLowerCase().includes(searchQuery.toLowerCase()) ||
        r.description.toLowerCase().includes(searchQuery.toLowerCase());

      const matchesDecision =
        filterDecision === "ALL" || r.decision.toUpperCase() === filterDecision.toUpperCase();

      return matchesSearch && matchesDecision;
    });
  }, [rules, searchQuery, filterDecision]);

  const getDecisionBadge = (decision: string) => {
    switch (decision.toUpperCase()) {
      case "ALLOW":
        return {
          color: "#34d399",
          dotColor: "#10b981",
          border: "rgba(16, 185, 129, 0.35)",
          bg: "rgba(16, 185, 129, 0.10)",
          label: "ALLOW",
        };
      case "BLOCK":
        return {
          color: "#f87171",
          dotColor: "#ef4444",
          border: "rgba(239, 68, 68, 0.35)",
          bg: "rgba(239, 68, 68, 0.10)",
          label: "BLOCK",
        };
      case "REQUIRE_APPROVAL":
        return {
          color: "#fbbf24",
          dotColor: "#f59e0b",
          border: "rgba(245, 158, 11, 0.35)",
          bg: "rgba(245, 158, 11, 0.10)",
          label: "REQUIRE_APPROVAL",
        };
      case "SUSPEND":
      default:
        return {
          color: "#fb923c",
          dotColor: "#f97316",
          border: "rgba(249, 115, 22, 0.35)",
          bg: "rgba(249, 115, 22, 0.10)",
          label: "SUSPEND",
        };
    }
  };

  const getRuleIcon = (id: string, index: number) => {
    switch (id) {
      case "pol_agent_suspension":
        return <Icons.Shield size={16} color="#34d399" />;
      case "pol_destructive_block":
        return <Icons.Lock size={16} color="#34d399" />;
      case "pol_external_egress":
        return <Icons.Network size={16} color="#34d399" />;
      case "pol_secrets_protection":
        return <Icons.Vault size={16} color="#34d399" />;
      case "pol_mutation_approval":
        return <Icons.ClipboardCheck size={16} color="#34d399" />;
      case "pol_allow_permitted":
        return <Icons.PowerCircle size={16} color="#34d399" />;
      default:
        return index % 2 === 0 ? (
          <Icons.Shield size={16} color="#34d399" />
        ) : (
          <Icons.Lock size={16} color="#34d399" />
        );
    }
  };

  const handleCreateNewRule = (e: React.FormEvent) => {
    e.preventDefault();
    if (!newRuleForm.name || !newRuleForm.condition) return;

    const newRule: PolicyRuleData = {
      id: `pol_${newRuleForm.name.toLowerCase().replace(/\s+/g, "_").slice(0, 20)}`,
      name: newRuleForm.name,
      decision: newRuleForm.decision,
      condition: newRuleForm.condition,
      description: newRuleForm.description || "Custom runtime deterministic enforcement rule.",
      priority: newRuleForm.priority || "10",
      status: "active",
      category: newRuleForm.category || "Custom",
      scope: newRuleForm.scope || "Tenant scope",
    };

    setRules((prev) => [...prev, newRule]);
    setIsNewPolicyModalOpen(false);
    setNewRuleForm({
      name: "",
      decision: "BLOCK",
      condition: "",
      description: "",
      priority: "10",
      category: "Custom",
      scope: "Tenant scope",
    });
  };

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: "16px", width: "100%" }}>
      {/* ── 1. Top Breadcrumb ── */}
      <div
        style={{
          display: "flex",
          alignItems: "center",
          gap: "8px",
          fontSize: "0.6875rem",
          fontFamily: "var(--font-mono)",
          color: "var(--text-muted)",
          letterSpacing: "0.08em",
          textTransform: "uppercase",
        }}
      >
        <span>CONTROL PLANE</span>
        <span style={{ color: "var(--border-secondary)", fontWeight: 700 }}>&gt;</span>
        <span style={{ color: "var(--text-secondary)" }}>POLICIES</span>
      </div>

      {/* ── 2. Page Title Header Row ── */}
      <div
        style={{
          display: "flex",
          alignItems: "flex-start",
          justifyContent: "space-between",
          flexWrap: "wrap",
          gap: "12px",
        }}
      >
        <div>
          <div style={{ display: "flex", alignItems: "center", gap: "12px", flexWrap: "wrap" }}>
            <h1
              style={{
                fontSize: "1.75rem",
                fontWeight: 700,
                color: "var(--text-primary)",
                letterSpacing: "-0.025em",
                lineHeight: 1.2,
                margin: 0,
              }}
            >
              Policy enforcement
            </h1>

            {/* Pill: DETERMINISTIC ENGINE */}
            <div
              style={{
                display: "inline-flex",
                alignItems: "center",
                gap: "6px",
                padding: "3px 10px",
                borderRadius: "20px",
                background: "rgba(16, 185, 129, 0.08)",
                border: "1px solid rgba(16, 185, 129, 0.3)",
                color: "#34d399",
                fontFamily: "var(--font-mono)",
                fontSize: "0.6875rem",
                fontWeight: 600,
                letterSpacing: "0.05em",
              }}
            >
              <Icons.Network size={12} color="#34d399" />
              <span>DETERMINISTIC ENGINE</span>
            </div>
          </div>

          <p
            style={{
              fontSize: "0.8125rem",
              color: "var(--text-secondary)",
              lineHeight: 1.5,
              marginTop: "6px",
              maxWidth: "76ch",
            }}
          >
            Ordered runtime rules evaluate every agent action before a tool call crosses the enforcement boundary.
          </p>
        </div>

        {/* Right Status Badges */}
        <div style={{ display: "flex", alignItems: "center", gap: "10px", flexShrink: 0 }}>
          {/* ENGINE: ACTIVE */}
          <div
            style={{
              display: "inline-flex",
              alignItems: "center",
              gap: "6px",
              padding: "4px 12px",
              borderRadius: "20px",
              background: "rgba(16, 185, 129, 0.10)",
              border: "1px solid rgba(16, 185, 129, 0.35)",
              color: "#34d399",
              fontFamily: "var(--font-mono)",
              fontSize: "0.6875rem",
              fontWeight: 600,
              letterSpacing: "0.05em",
            }}
          >
            <span
              style={{
                width: "6px",
                height: "6px",
                borderRadius: "50%",
                background: "#10b981",
                boxShadow: "0 0 6px rgba(16, 185, 129, 0.8)",
                display: "inline-block",
              }}
            />
            <span>ENGINE: ACTIVE</span>
          </div>

          {/* Global policy set */}
          <div
            style={{
              display: "inline-flex",
              alignItems: "center",
              gap: "6px",
              padding: "4px 12px",
              borderRadius: "20px",
              background: "var(--bg-elevated)",
              border: "1px solid var(--border-primary)",
              color: "var(--text-secondary)",
              fontFamily: "var(--font-family)",
              fontSize: "0.75rem",
              fontWeight: 500,
            }}
          >
            <Icons.Globe size={13} color="var(--text-muted)" />
            <span>Global policy set</span>
          </div>
        </div>
      </div>

      {/* ── 3. The 4 Stat Cards Row ── */}
      <div
        id="policy-metrics-row"
        style={{
          display: "grid",
          gridTemplateColumns: "repeat(auto-fit, minmax(210px, 1fr))",
          gap: "12px",
        }}
      >
        {/* Card 1: ACTIVE RULES */}
        <div
          style={{
            background: "var(--bg-card)",
            border: "1px solid var(--border-primary)",
            borderRadius: "var(--radius-md)",
            padding: "16px 18px",
            display: "flex",
            flexDirection: "column",
            justifyContent: "space-between",
            minHeight: "96px",
            transition: "border-color 0.15s ease, background 0.15s ease",
          }}
          onMouseEnter={(e) => {
            (e.currentTarget as HTMLDivElement).style.borderColor = "var(--border-secondary)";
            (e.currentTarget as HTMLDivElement).style.background = "var(--bg-elevated)";
          }}
          onMouseLeave={(e) => {
            (e.currentTarget as HTMLDivElement).style.borderColor = "var(--border-primary)";
            (e.currentTarget as HTMLDivElement).style.background = "var(--bg-card)";
          }}
        >
          <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between" }}>
            <span
              style={{
                fontSize: "0.6875rem",
                fontWeight: 600,
                color: "var(--text-muted)",
                letterSpacing: "0.08em",
                textTransform: "uppercase",
                fontFamily: "var(--font-mono)",
              }}
            >
              ACTIVE RULES
            </span>
            <Icons.ShieldCheck size={16} color="var(--accent-mint)" />
          </div>
          <div style={{ marginTop: "10px" }}>
            <div style={{ fontSize: "1.75rem", fontWeight: 700, color: "var(--text-primary)", lineHeight: 1 }}>
              {String(rules.length).padStart(2, "0")}
            </div>
            <div style={{ fontSize: "0.75rem", color: "var(--text-muted)", marginTop: "4px" }}>
              in evaluation order
            </div>
          </div>
        </div>

        {/* Card 2: ENFORCEMENT */}
        <div
          style={{
            background: "var(--bg-card)",
            border: "1px solid var(--border-primary)",
            borderRadius: "var(--radius-md)",
            padding: "16px 18px",
            display: "flex",
            flexDirection: "column",
            justifyContent: "space-between",
            minHeight: "96px",
            transition: "border-color 0.15s ease, background 0.15s ease",
          }}
          onMouseEnter={(e) => {
            (e.currentTarget as HTMLDivElement).style.borderColor = "var(--border-secondary)";
            (e.currentTarget as HTMLDivElement).style.background = "var(--bg-elevated)";
          }}
          onMouseLeave={(e) => {
            (e.currentTarget as HTMLDivElement).style.borderColor = "var(--border-primary)";
            (e.currentTarget as HTMLDivElement).style.background = "var(--bg-card)";
          }}
        >
          <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between" }}>
            <span
              style={{
                fontSize: "0.6875rem",
                fontWeight: 600,
                color: "var(--text-muted)",
                letterSpacing: "0.08em",
                textTransform: "uppercase",
                fontFamily: "var(--font-mono)",
              }}
            >
              ENFORCEMENT
            </span>
            <Icons.Lock size={16} color="var(--accent-mint)" />
          </div>
          <div style={{ marginTop: "10px" }}>
            <div style={{ fontSize: "1.25rem", fontWeight: 700, color: "var(--text-primary)", lineHeight: 1.2 }}>
              Pre-execution
            </div>
            <div style={{ fontSize: "0.75rem", color: "var(--text-muted)", marginTop: "4px" }}>
              gate
            </div>
          </div>
        </div>

        {/* Card 3: EVALUATION MODE */}
        <div
          style={{
            background: "var(--bg-card)",
            border: "1px solid var(--border-primary)",
            borderRadius: "var(--radius-md)",
            padding: "16px 18px",
            display: "flex",
            flexDirection: "column",
            justifyContent: "space-between",
            minHeight: "96px",
            transition: "border-color 0.15s ease, background 0.15s ease",
          }}
          onMouseEnter={(e) => {
            (e.currentTarget as HTMLDivElement).style.borderColor = "var(--border-secondary)";
            (e.currentTarget as HTMLDivElement).style.background = "var(--bg-elevated)";
          }}
          onMouseLeave={(e) => {
            (e.currentTarget as HTMLDivElement).style.borderColor = "var(--border-primary)";
            (e.currentTarget as HTMLDivElement).style.background = "var(--bg-card)";
          }}
        >
          <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between" }}>
            <span
              style={{
                fontSize: "0.6875rem",
                fontWeight: 600,
                color: "var(--text-muted)",
                letterSpacing: "0.08em",
                textTransform: "uppercase",
                fontFamily: "var(--font-mono)",
              }}
            >
              EVALUATION MODE
            </span>
            <Icons.Hierarchy size={16} color="var(--accent-mint)" />
          </div>
          <div style={{ marginTop: "10px" }}>
            <div style={{ fontSize: "1.25rem", fontWeight: 700, color: "var(--text-primary)", lineHeight: 1.2 }}>
              Deterministic
            </div>
            <div style={{ fontSize: "0.75rem", color: "var(--text-muted)", marginTop: "4px" }}>
              no model judgment
            </div>
          </div>
        </div>

        {/* Card 4: RUNTIME STATUS */}
        <div
          style={{
            background: "var(--bg-card)",
            border: "1px solid var(--border-primary)",
            borderRadius: "var(--radius-md)",
            padding: "16px 18px",
            display: "flex",
            flexDirection: "column",
            justifyContent: "space-between",
            minHeight: "96px",
            transition: "border-color 0.15s ease, background 0.15s ease",
          }}
          onMouseEnter={(e) => {
            (e.currentTarget as HTMLDivElement).style.borderColor = "var(--border-secondary)";
            (e.currentTarget as HTMLDivElement).style.background = "var(--bg-elevated)";
          }}
          onMouseLeave={(e) => {
            (e.currentTarget as HTMLDivElement).style.borderColor = "var(--border-primary)";
            (e.currentTarget as HTMLDivElement).style.background = "var(--bg-card)";
          }}
        >
          <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between" }}>
            <span
              style={{
                fontSize: "0.6875rem",
                fontWeight: 600,
                color: "var(--text-muted)",
                letterSpacing: "0.08em",
                textTransform: "uppercase",
                fontFamily: "var(--font-mono)",
              }}
            >
              RUNTIME STATUS
            </span>
            <Icons.Pulse size={16} color="var(--accent-mint)" />
          </div>
          <div style={{ marginTop: "10px" }}>
            <div style={{ fontSize: "1.25rem", fontWeight: 700, color: "var(--text-primary)", lineHeight: 1.2 }}>
              Operational
            </div>
            <div style={{ fontSize: "0.75rem", color: "var(--text-muted)", marginTop: "4px" }}>
              gateway v0.1
            </div>
          </div>
        </div>
      </div>

      {/* ── 4. Main Policy Engine Container Panel ── */}
      <section
        id="policy-engine-panel"
        style={{
          background: "var(--bg-panel)",
          border: "1px solid var(--border-primary)",
          borderRadius: "var(--radius-lg)",
          padding: "20px 22px",
          display: "flex",
          flexDirection: "column",
          gap: "16px",
        }}
      >
        {/* Header Toolbar */}
        <div
          style={{
            display: "flex",
            alignItems: "flex-start",
            justifyContent: "space-between",
            flexWrap: "wrap",
            gap: "14px",
          }}
        >
          <div>
            <div style={{ display: "flex", alignItems: "center", gap: "8px" }}>
              <h2
                style={{
                  fontSize: "1rem",
                  fontWeight: 600,
                  color: "var(--text-primary)",
                  margin: 0,
                }}
              >
                Deterministic policy engine rules
              </h2>
              <span
                style={{
                  fontSize: "0.625rem",
                  fontFamily: "var(--font-mono)",
                  fontWeight: 600,
                  color: "var(--text-muted)",
                  background: "var(--bg-code)",
                  border: "1px solid var(--border-primary)",
                  padding: "1px 6px",
                  borderRadius: "4px",
                  letterSpacing: "0.06em",
                  textTransform: "uppercase",
                }}
              >
                ORDERED
              </span>
            </div>
            <div
              style={{
                fontSize: "0.75rem",
                color: "var(--text-muted)",
                marginTop: "3px",
              }}
            >
              First matching outcome applies. No non-deterministic model sits on the enforcement boundary.
            </div>
          </div>

          {/* Right Controls: Search, Filter, New Policy */}
          <div style={{ display: "flex", alignItems: "center", gap: "8px", flexWrap: "wrap" }}>
            {/* Search Input */}
            <div style={{ position: "relative", display: "flex", alignItems: "center" }}>
              <span
                style={{
                  position: "absolute",
                  left: "10px",
                  pointerEvents: "none",
                  color: "var(--text-muted)",
                  display: "flex",
                  alignItems: "center",
                }}
              >
                <Icons.Search size={14} />
              </span>
              <input
                type="text"
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                placeholder="Find a policy..."
                style={{
                  background: "var(--bg-code)",
                  border: "1px solid var(--border-primary)",
                  borderRadius: "var(--radius-sm)",
                  padding: "5px 12px 5px 30px",
                  fontSize: "0.8125rem",
                  color: "var(--text-primary)",
                  outline: "none",
                  width: "180px",
                  transition: "border-color 0.15s ease, width 0.15s ease",
                }}
                onFocus={(e) => {
                  e.currentTarget.style.borderColor = "var(--accent-mint)";
                  e.currentTarget.style.width = "210px";
                }}
                onBlur={(e) => {
                  e.currentTarget.style.borderColor = "var(--border-primary)";
                  e.currentTarget.style.width = "180px";
                }}
              />
            </div>

            {/* Filter Dropdown */}
            <div style={{ position: "relative", display: "flex", alignItems: "center" }}>
              <select
                value={filterDecision}
                onChange={(e) => setFilterDecision(e.target.value)}
                style={{
                  background: "var(--bg-elevated)",
                  border: "1px solid var(--border-primary)",
                  borderRadius: "var(--radius-sm)",
                  padding: "5px 24px 5px 24px",
                  fontSize: "0.75rem",
                  color: "var(--text-secondary)",
                  outline: "none",
                  cursor: "pointer",
                  appearance: "none",
                  WebkitAppearance: "none",
                }}
              >
                <option value="ALL">Filter: All</option>
                <option value="BLOCK">Filter: BLOCK</option>
                <option value="SUSPEND">Filter: SUSPEND</option>
                <option value="REQUIRE_APPROVAL">Filter: APPROVAL</option>
                <option value="ALLOW">Filter: ALLOW</option>
              </select>
              <span
                style={{
                  position: "absolute",
                  left: "7px",
                  pointerEvents: "none",
                  color: "var(--text-muted)",
                  display: "flex",
                }}
              >
                <Icons.Filter size={12} />
              </span>
              <span
                style={{
                  position: "absolute",
                  right: "7px",
                  pointerEvents: "none",
                  color: "var(--text-muted)",
                  fontSize: "0.6rem",
                }}
              >
                ▼
              </span>
            </div>

            {/* + New policy Button */}
            <button
              onClick={() => setIsNewPolicyModalOpen(true)}
              style={{
                display: "inline-flex",
                alignItems: "center",
                gap: "6px",
                background: "var(--accent-primary)",
                color: "#081115",
                fontWeight: 600,
                fontSize: "0.78125rem",
                padding: "6px 14px",
                borderRadius: "var(--radius-sm)",
                border: "none",
                cursor: "pointer",
                transition: "background 0.15s ease, transform 0.1s ease",
              }}
              onMouseEnter={(e) => {
                e.currentTarget.style.background = "#34d399";
              }}
              onMouseLeave={(e) => {
                e.currentTarget.style.background = "var(--accent-primary)";
              }}
            >
              <Icons.Plus size={14} color="#081115" />
              <span>New policy</span>
            </button>
          </div>
        </div>

        {/* Sub-bar: rule count & evaluation order note */}
        <div
          style={{
            display: "flex",
            alignItems: "center",
            justifyContent: "space-between",
            fontSize: "0.6875rem",
            color: "var(--text-muted)",
            borderBottom: "1px solid var(--border-primary)",
            paddingBottom: "10px",
            marginTop: "-4px",
          }}
        >
          <div style={{ display: "flex", alignItems: "center", gap: "10px" }}>
            <span style={{ fontFamily: "var(--font-mono)", fontWeight: 600, color: "var(--text-secondary)" }}>
              {String(filteredRules.length).padStart(2, "0")} rules in policy set
            </span>
            <span>·</span>
            <span style={{ display: "inline-flex", alignItems: "center", gap: "5px", color: "#34d399" }}>
              <span
                style={{
                  width: "5px",
                  height: "5px",
                  borderRadius: "50%",
                  background: "#10b981",
                  display: "inline-block",
                }}
              />
              All rules active
            </span>
          </div>

          <div
            style={{
              fontFamily: "var(--font-mono)",
              fontSize: "0.625rem",
              letterSpacing: "0.06em",
              textTransform: "uppercase",
              color: "var(--text-muted)",
            }}
          >
            EVALUATION ORDER · HIGHEST PRIORITY FIRST
          </div>
        </div>

        {/* ── 5. The Rule Cards Grid (3 Columns) ── */}
        <div
          id="policy-cards-grid"
          style={{
            display: "grid",
            gridTemplateColumns: "repeat(auto-fill, minmax(320px, 1fr))",
            gap: "12px",
          }}
        >
          {filteredRules.map((r, index) => {
            const badge = getDecisionBadge(r.decision);
            const isCopied = copiedRuleId === r.id;

            return (
              <div
                key={r.id}
                id={`policy-card-${r.id}`}
                style={{
                  background: "var(--bg-card)",
                  border: "1px solid var(--border-primary)",
                  borderRadius: "var(--radius-md)",
                  padding: "16px 18px",
                  display: "flex",
                  flexDirection: "column",
                  gap: "12px",
                  position: "relative",
                  transition: "border-color 0.15s ease, background 0.15s ease",
                }}
                onMouseEnter={(e) => {
                  (e.currentTarget as HTMLDivElement).style.borderColor = "var(--border-secondary)";
                  (e.currentTarget as HTMLDivElement).style.background = "var(--bg-elevated)";
                }}
                onMouseLeave={(e) => {
                  (e.currentTarget as HTMLDivElement).style.borderColor = "var(--border-primary)";
                  (e.currentTarget as HTMLDivElement).style.background = "var(--bg-card)";
                }}
              >
                {/* Header: Icon + Title + Decision Badge */}
                <div style={{ display: "flex", alignItems: "flex-start", justifyContent: "space-between", gap: "8px" }}>
                  <div style={{ display: "flex", alignItems: "center", gap: "9px", minWidth: 0 }}>
                    <div
                      style={{
                        width: "30px",
                        height: "30px",
                        borderRadius: "var(--radius-sm)",
                        background: "rgba(16, 185, 129, 0.08)",
                        border: "1px solid rgba(16, 185, 129, 0.20)",
                        display: "flex",
                        alignItems: "center",
                        justifyContent: "center",
                        flexShrink: 0,
                      }}
                    >
                      {getRuleIcon(r.id, index)}
                    </div>
                    <h3
                      style={{
                        fontSize: "0.8125rem",
                        fontWeight: 600,
                        color: "var(--text-primary)",
                        lineHeight: 1.3,
                        margin: 0,
                        whiteSpace: "nowrap",
                        overflow: "hidden",
                        textOverflow: "ellipsis",
                      }}
                      title={r.name}
                    >
                      {r.name}
                    </h3>
                  </div>

                  {/* Decision Badge */}
                  <span
                    style={{
                      display: "inline-flex",
                      alignItems: "center",
                      gap: "5px",
                      padding: "2px 8px",
                      borderRadius: "4px",
                      fontSize: "0.625rem",
                      fontWeight: 700,
                      fontFamily: "var(--font-mono)",
                      letterSpacing: "0.05em",
                      background: badge.bg,
                      color: badge.color,
                      border: `1px solid ${badge.border}`,
                      flexShrink: 0,
                      whiteSpace: "nowrap",
                    }}
                  >
                    <span
                      style={{
                        width: "5px",
                        height: "5px",
                        borderRadius: "50%",
                        background: badge.dotColor,
                        display: "inline-block",
                      }}
                    />
                    {badge.label}
                  </span>
                </div>

                {/* Description */}
                <p
                  style={{
                    fontSize: "0.75rem",
                    color: "var(--text-secondary)",
                    lineHeight: 1.45,
                    margin: 0,
                    minHeight: "36px",
                  }}
                >
                  {r.description}
                </p>

                {/* Condition Code Block */}
                <div
                  style={{
                    background: "var(--bg-code)",
                    border: "1px solid #14222a",
                    borderRadius: "6px",
                    padding: "8px 12px",
                    display: "flex",
                    flexDirection: "column",
                    gap: "4px",
                    overflowX: "auto",
                  }}
                >
                  <div
                    style={{
                      fontSize: "0.5625rem",
                      fontFamily: "var(--font-mono)",
                      letterSpacing: "0.07em",
                      textTransform: "uppercase",
                      color: "var(--text-muted)",
                    }}
                  >
                    CONDITION
                  </div>
                  <code
                    style={{
                      fontFamily: "var(--font-mono)",
                      fontSize: "0.7rem",
                      color: "#93c5fd",
                      whiteSpace: "nowrap",
                      overflowX: "auto",
                    }}
                  >
                    {r.condition}
                  </code>
                </div>

                {/* Rule ID & Priority line */}
                <div
                  style={{
                    display: "flex",
                    alignItems: "center",
                    justifyContent: "space-between",
                    fontSize: "0.6875rem",
                    color: "var(--text-muted)",
                    fontFamily: "var(--font-mono)",
                  }}
                >
                  <span>Rule: {r.id}</span>
                  <span>Priority #{r.priority}</span>
                </div>

                {/* Optional Evaluation Order Banner (as in Card 2 of Reference) */}
                {r.showEvaluationBanner && (
                  <div
                    style={{
                      background: "rgba(16, 185, 129, 0.05)",
                      border: "1px dashed rgba(16, 185, 129, 0.25)",
                      borderRadius: "5px",
                      padding: "6px 10px",
                      fontSize: "0.6875rem",
                      display: "flex",
                      alignItems: "center",
                      justifyContent: "space-between",
                      gap: "6px",
                    }}
                  >
                    <div>
                      <div
                        style={{
                          fontSize: "0.5625rem",
                          fontFamily: "var(--font-mono)",
                          letterSpacing: "0.06em",
                          textTransform: "uppercase",
                          color: "var(--accent-mint)",
                          fontWeight: 600,
                        }}
                      >
                        EVALUATION ORDER
                      </div>
                      <div style={{ color: "var(--text-secondary)", fontSize: "0.6875rem" }}>
                        Evaluated before any tool call reaches the runtime.
                      </div>
                    </div>
                    <span
                      style={{
                        fontFamily: "var(--font-mono)",
                        fontWeight: 700,
                        fontSize: "0.6875rem",
                        color: "var(--accent-mint)",
                        whiteSpace: "nowrap",
                      }}
                    >
                      PRIORITY #{r.priority}
                    </span>
                  </div>
                )}

                {/* Bottom Footer Line */}
                <div
                  style={{
                    display: "flex",
                    alignItems: "center",
                    justifyContent: "space-between",
                    borderTop: "1px solid rgba(24, 41, 50, 0.7)",
                    paddingTop: "10px",
                    marginTop: "auto",
                    fontSize: "0.6875rem",
                  }}
                >
                  {/* Left: Enforced · Category · Scope */}
                  <div style={{ display: "flex", alignItems: "center", gap: "6px", color: "var(--text-secondary)" }}>
                    <span
                      style={{
                        width: "5px",
                        height: "5px",
                        borderRadius: "50%",
                        background: badge.dotColor,
                        display: "inline-block",
                      }}
                    />
                    <span>
                      Enforced · {r.category || "Identity"} · {r.scope || "Runtime"}
                    </span>
                  </div>

                  {/* Right: Copy condition button */}
                  <button
                    onClick={() => handleCopyCondition(r.id, r.condition)}
                    style={{
                      display: "inline-flex",
                      alignItems: "center",
                      gap: "4px",
                      background: "transparent",
                      border: "none",
                      color: isCopied ? "#34d399" : "var(--text-muted)",
                      fontSize: "0.6875rem",
                      cursor: "pointer",
                      padding: "2px 4px",
                      borderRadius: "4px",
                      transition: "color 0.15s ease",
                    }}
                    onMouseEnter={(e) => {
                      if (!isCopied) e.currentTarget.style.color = "var(--text-primary)";
                    }}
                    onMouseLeave={(e) => {
                      if (!isCopied) e.currentTarget.style.color = "var(--text-muted)";
                    }}
                    title="Copy condition to clipboard"
                  >
                    {isCopied ? <Icons.Check size={12} color="#34d399" /> : <Icons.Copy size={12} />}
                    <span>{isCopied ? "Copied!" : "Copy condition"}</span>
                  </button>
                </div>
              </div>
            );
          })}
        </div>

        {/* Empty state when filtering yields no results or no policies exist */}
        {filteredRules.length === 0 && (
          <div
            style={{
              textAlign: "center",
              padding: "40px 20px",
              color: "var(--text-muted)",
              fontSize: "0.8125rem",
              border: "1px dashed var(--border-primary)",
              borderRadius: "var(--radius-md)",
            }}
          >
            {rules.length === 0 ? (
              <>
                <p style={{ marginBottom: "12px" }}>
                  No deterministic policies configured for this scope yet.
                </p>
                <button
                  onClick={() => setIsNewPolicyModalOpen(true)}
                  className="btn btn-primary"
                  style={{ fontSize: "0.75rem", padding: "6px 14px" }}
                >
                  + New Policy Rule
                </button>
              </>
            ) : (
              <>
                <p>No deterministic policies match your search or filter criteria.</p>
                <div style={{ marginTop: "8px" }}>
                  <button
                    onClick={() => {
                      setSearchQuery("");
                      setFilterDecision("ALL");
                    }}
                    className="btn btn-ghost"
                    style={{ fontSize: "0.75rem", padding: "4px 10px" }}
                  >
                    Reset filters
                  </button>
                </div>
              </>
            )}
          </div>
        )}
      </section>

      {/* ── 6. New Policy Modal ── */}
      {isNewPolicyModalOpen && (
        <div
          role="dialog"
          aria-modal="true"
          style={{
            position: "fixed",
            inset: 0,
            background: "rgba(5, 10, 14, 0.82)",
            backdropFilter: "blur(4px)",
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
            zIndex: 100,
            padding: "20px",
          }}
          onClick={() => setIsNewPolicyModalOpen(false)}
        >
          <div
            style={{
              background: "var(--bg-panel)",
              border: "1px solid var(--border-primary)",
              borderRadius: "var(--radius-lg)",
              width: "100%",
              maxWidth: "520px",
              padding: "24px",
              display: "flex",
              flexDirection: "column",
              gap: "18px",
              boxShadow: "0 20px 40px rgba(0,0,0,0.5)",
            }}
            onClick={(e) => e.stopPropagation()}
          >
            <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between" }}>
              <div style={{ display: "flex", alignItems: "center", gap: "8px" }}>
                <Icons.ShieldCheck size={18} color="var(--accent-mint)" />
                <h3 style={{ fontSize: "1rem", fontWeight: 600, color: "var(--text-primary)", margin: 0 }}>
                  Create Deterministic Policy Rule
                </h3>
              </div>
              <button
                onClick={() => setIsNewPolicyModalOpen(false)}
                style={{
                  background: "transparent",
                  border: "none",
                  color: "var(--text-muted)",
                  fontSize: "1.2rem",
                  cursor: "pointer",
                  padding: "4px",
                }}
              >
                ✕
              </button>
            </div>

            <form onSubmit={handleCreateNewRule} style={{ display: "flex", flexDirection: "column", gap: "14px" }}>
              <div>
                <label style={{ display: "block", fontSize: "0.75rem", color: "var(--text-secondary)", marginBottom: "4px" }}>
                  Rule Name
                </label>
                <input
                  type="text"
                  required
                  placeholder="e.g. Sensitive Database Query Filter"
                  value={newRuleForm.name}
                  onChange={(e) => setNewRuleForm({ ...newRuleForm, name: e.target.value })}
                  style={{ width: "100%", padding: "7px 10px" }}
                />
              </div>

              <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "12px" }}>
                <div>
                  <label style={{ display: "block", fontSize: "0.75rem", color: "var(--text-secondary)", marginBottom: "4px" }}>
                    Enforcement Decision
                  </label>
                  <select
                    value={newRuleForm.decision}
                    onChange={(e) => setNewRuleForm({ ...newRuleForm, decision: e.target.value })}
                    style={{ width: "100%", padding: "7px 10px" }}
                  >
                    <option value="BLOCK">BLOCK</option>
                    <option value="REQUIRE_APPROVAL">REQUIRE_APPROVAL</option>
                    <option value="SUSPEND">SUSPEND</option>
                    <option value="ALLOW">ALLOW</option>
                  </select>
                </div>

                <div>
                  <label style={{ display: "block", fontSize: "0.75rem", color: "var(--text-secondary)", marginBottom: "4px" }}>
                    Priority (Lower executes first)
                  </label>
                  <input
                    type="number"
                    min="1"
                    max="999"
                    value={newRuleForm.priority}
                    onChange={(e) => setNewRuleForm({ ...newRuleForm, priority: e.target.value })}
                    style={{ width: "100%", padding: "7px 10px" }}
                  />
                </div>
              </div>

              <div>
                <label style={{ display: "block", fontSize: "0.75rem", color: "var(--text-secondary)", marginBottom: "4px" }}>
                  Deterministic Condition Expression
                </label>
                <input
                  type="text"
                  required
                  placeholder="e.g. tool in ['sql', 'query'] and 'salary' in resource"
                  value={newRuleForm.condition}
                  onChange={(e) => setNewRuleForm({ ...newRuleForm, condition: e.target.value })}
                  style={{ width: "100%", padding: "7px 10px", fontFamily: "var(--font-mono)" }}
                />
              </div>

              <div>
                <label style={{ display: "block", fontSize: "0.75rem", color: "var(--text-secondary)", marginBottom: "4px" }}>
                  Description & Rationale
                </label>
                <textarea
                  rows={2}
                  placeholder="Explain why this policy boundary is enforced..."
                  value={newRuleForm.description}
                  onChange={(e) => setNewRuleForm({ ...newRuleForm, description: e.target.value })}
                  style={{ width: "100%", padding: "7px 10px" }}
                />
              </div>

              <div style={{ display: "flex", justifyContent: "flex-end", gap: "10px", marginTop: "6px" }}>
                <button
                  type="button"
                  className="btn btn-ghost"
                  onClick={() => setIsNewPolicyModalOpen(false)}
                >
                  Cancel
                </button>
                <button type="submit" className="btn btn-primary">
                  Save & Enforce Policy
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
};
