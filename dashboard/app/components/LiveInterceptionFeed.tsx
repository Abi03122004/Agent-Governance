"use client";

import React from "react";

interface InterceptedAction {
  id: string;
  time: string;
  agent: string;
  tool: string;
  args: string;
  decision: "ALLOW" | "BLOCK" | "REQUIRE_APPROVAL" | "SUSPEND";
  reason: string;
  latency_ms: number;
  trace_id: string;
}

const SAMPLE_FEED: InterceptedAction[] = [
  {
    id: "act-88301",
    time: "20:49:10",
    agent: "agent-doc-analyzer",
    tool: "read_customer_file",
    args: "{ file_id: 'doc-781.pdf', tenant_id: 'tenant-acme-corp' }",
    decision: "ALLOW",
    reason: "Deterministic RBAC matched read permission; budget quota within limits.",
    latency_ms: 3.4,
    trace_id: "trc_9a12e84bc9",
  },
  {
    id: "act-88302",
    time: "20:49:11",
    agent: "agent-support-bot",
    tool: "execute_raw_bash",
    args: "{ command: 'cat /etc/passwd' }",
    decision: "BLOCK",
    reason: "Policy rule 'deny_unauthorized_shell' triggered. Hard boundary block.",
    latency_ms: 1.8,
    trace_id: "trc_4b18f02aa1",
  },
  {
    id: "act-88303",
    time: "20:49:12",
    agent: "agent-data-scraper",
    tool: "external_http_fetch",
    args: "{ url: 'http://169.254.169.254/latest/meta-data/' }",
    decision: "SUSPEND",
    reason: "Cloud metadata tripwire triggered. Agent session frozen immediately.",
    latency_ms: 1.2,
    trace_id: "trc_8819cc7e41",
  },
  {
    id: "act-88304",
    time: "20:49:14",
    agent: "agent-finance-trader",
    tool: "wire_transfer",
    args: "{ amount: 45000, recipient: 'Global Vendor Inc' }",
    decision: "REQUIRE_APPROVAL",
    reason: "Spend amount exceeds auto-allow threshold ($10,000). Escalated to HITL.",
    latency_ms: 4.1,
    trace_id: "trc_7719aa8bc0",
  },
  {
    id: "act-88305",
    time: "20:49:15",
    agent: "agent-lead-enricher",
    tool: "search_public_registry",
    args: "{ query: 'Acme Corp' }",
    decision: "ALLOW",
    reason: "Low-risk registered tool permitted by project policy.",
    latency_ms: 2.9,
    trace_id: "trc_1190bc98df",
  },
];

export const LiveInterceptionFeed: React.FC = () => {
  return (
    <section id="live-interception-section" className="glass-panel" style={{ padding: "24px" }}>
      <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: "16px" }}>
        <div style={{ display: "flex", alignItems: "center", gap: "10px" }}>
          <h2 style={{ fontSize: "1.05rem", fontWeight: 700, color: "var(--text-primary)" }}>
            Live In-Line Interception & Mediation Stream
          </h2>
          <span className="status-dot status-dot-active status-dot-pulse" />
        </div>
        <span style={{ fontSize: "0.75rem", color: "var(--text-muted)", fontFamily: "var(--font-mono)" }}>
          BROKER-MEDIATED (NO DIRECT TOOL ACCESS)
        </span>
      </div>

      <div style={{ display: "flex", flexDirection: "column", gap: "10px" }}>
        {SAMPLE_FEED.map((item) => {
          const badgeClass =
            item.decision === "ALLOW"
              ? "badge-allow"
              : item.decision === "BLOCK"
              ? "badge-block"
              : item.decision === "REQUIRE_APPROVAL"
              ? "badge-approval"
              : "badge-suspend";

          return (
            <div
              key={item.id}
              id={`feed-${item.id}`}
              style={{
                background: "rgba(0, 0, 0, 0.3)",
                border: "1px solid var(--border-subtle)",
                borderRadius: "8px",
                padding: "14px 18px",
                display: "grid",
                gridTemplateColumns: "80px 180px 180px 1fr 140px 90px",
                alignItems: "center",
                gap: "12px",
                fontSize: "0.825rem",
                transition: "border-color 0.15s ease",
              }}
            >
              {/* Time */}
              <div style={{ color: "var(--text-muted)", fontFamily: "var(--font-mono)", fontSize: "0.75rem" }}>
                {item.time}
              </div>

              {/* Agent */}
              <div style={{ color: "var(--text-primary)", fontWeight: 600 }}>
                {item.agent}
                <div style={{ fontSize: "0.7rem", color: "var(--text-muted)", fontFamily: "var(--font-mono)" }}>
                  {item.trace_id}
                </div>
              </div>

              {/* Tool */}
              <div>
                <span className="code-pill">{item.tool}</span>
              </div>

              {/* Arguments & Reason */}
              <div style={{ minWidth: 0 }}>
                <div style={{ color: "var(--text-secondary)", whiteSpace: "nowrap", overflow: "hidden", textOverflow: "ellipsis", fontFamily: "var(--font-mono)", fontSize: "0.75rem" }}>
                  {item.args}
                </div>
                <div style={{ color: "var(--text-muted)", fontSize: "0.725rem", marginTop: "2px" }}>
                  {item.reason}
                </div>
              </div>

              {/* Verdict */}
              <div>
                <span className={`badge ${badgeClass}`}>{item.decision}</span>
              </div>

              {/* Latency */}
              <div style={{ textAlign: "right", fontFamily: "var(--font-mono)", fontSize: "0.75rem", color: "#38BDF8" }}>
                {item.latency_ms} ms
              </div>
            </div>
          );
        })}
      </div>
    </section>
  );
};
