"use client";

import React, { useState } from "react";

interface ApprovalItem {
  ticket_id: string;
  action_id: string;
  agent_id: string;
  tool_name: string;
  arguments_summary: string;
  canonical_hash: string;
  expires_in_minutes: number;
  status: "PENDING" | "APPROVED" | "REJECTED";
}

const INITIAL_APPROVALS: ApprovalItem[] = [
  {
    ticket_id: "ticket-appr-8921",
    action_id: "act-wire-99120",
    agent_id: "agent-finance-trader",
    tool_name: "wire_transfer",
    arguments_summary: "recipient: 'Global Vendor Inc', amount: $45,000 USD",
    canonical_hash: "9f4b8c71a3e9...2b11e0",
    expires_in_minutes: 12,
    status: "PENDING",
  },
  {
    ticket_id: "ticket-appr-8922",
    action_id: "act-sec-00412",
    agent_id: "agent-devops-ops",
    tool_name: "drop_temporary_db",
    arguments_summary: "database: 'temp_etl_shard_4', cascade: true",
    canonical_hash: "3a19df08ce45...9a88c2",
    expires_in_minutes: 7,
    status: "PENDING",
  },
  {
    ticket_id: "ticket-appr-8923",
    action_id: "act-crm-55410",
    agent_id: "agent-support-bot",
    tool_name: "export_customer_pii",
    arguments_summary: "records: 500, format: 'csv', reason: 'Audit export'",
    canonical_hash: "f107bb449a12...88319f",
    expires_in_minutes: 14,
    status: "PENDING",
  },
];

export const ApprovalQueueWidget: React.FC = () => {
  const [approvals, setApprovals] = useState<ApprovalItem[]>(INITIAL_APPROVALS);

  const handleDecision = (ticketId: string, decision: "APPROVED" | "REJECTED") => {
    setApprovals((prev) =>
      prev.map((item) =>
        item.ticket_id === ticketId ? { ...item, status: decision } : item
      )
    );
  };

  return (
    <section id="approval-queue-section" className="glass-panel" style={{ padding: "24px" }}>
      <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: "16px" }}>
        <div style={{ display: "flex", alignItems: "center", gap: "10px" }}>
          <h2 style={{ fontSize: "1.05rem", fontWeight: 700, color: "var(--text-primary)" }}>
            Cryptographic Human Approval Queue (HITL)
          </h2>
          <span className="badge badge-approval">
            {approvals.filter((a) => a.status === "PENDING").length} PENDING
          </span>
        </div>
        <span style={{ fontSize: "0.75rem", color: "var(--text-muted)", fontFamily: "var(--font-mono)" }}>
          ADR 0004: SHA-256 HASH BOUND
        </span>
      </div>

      <div style={{ overflowX: "auto" }}>
        <table style={{ width: "100%", borderCollapse: "collapse", textAlign: "left", fontSize: "0.85rem" }}>
          <thead>
            <tr style={{ borderBottom: "1px solid var(--border-subtle)", color: "var(--text-muted)" }}>
              <th style={{ padding: "10px 12px" }}>Ticket ID</th>
              <th style={{ padding: "10px 12px" }}>Agent Identity</th>
              <th style={{ padding: "10px 12px" }}>Target Tool</th>
              <th style={{ padding: "10px 12px" }}>Canonical Payload Hash</th>
              <th style={{ padding: "10px 12px" }}>TTL / Status</th>
              <th style={{ padding: "10px 12px", textAlign: "right" }}>Actions</th>
            </tr>
          </thead>
          <tbody>
            {approvals.map((item) => (
              <tr
                key={item.ticket_id}
                id={`row-${item.ticket_id}`}
                style={{
                  borderBottom: "1px solid var(--border-subtle)",
                  transition: "background 0.15s ease",
                }}
              >
                <td style={{ padding: "12px", fontFamily: "var(--font-mono)", color: "var(--text-primary)" }}>
                  {item.ticket_id}
                </td>
                <td style={{ padding: "12px", color: "var(--text-secondary)" }}>
                  <div style={{ fontWeight: 600, color: "var(--text-primary)" }}>{item.agent_id}</div>
                  <div style={{ fontSize: "0.75rem", color: "var(--text-muted)" }}>{item.action_id}</div>
                </td>
                <td style={{ padding: "12px" }}>
                  <span className="code-pill">{item.tool_name}</span>
                  <div style={{ fontSize: "0.75rem", color: "var(--text-muted)", marginTop: "4px" }}>
                    {item.arguments_summary}
                  </div>
                </td>
                <td style={{ padding: "12px", fontFamily: "var(--font-mono)", fontSize: "0.75rem", color: "var(--accent-cyan)" }}>
                  {item.canonical_hash}
                </td>
                <td style={{ padding: "12px" }}>
                  {item.status === "PENDING" ? (
                    <span style={{ color: "#F59E0B", fontWeight: 600, fontFamily: "var(--font-mono)", fontSize: "0.8rem" }}>
                      ⏳ {item.expires_in_minutes}m remaining
                    </span>
                  ) : item.status === "APPROVED" ? (
                    <span className="badge badge-allow">APPROVED</span>
                  ) : (
                    <span className="badge badge-block">REJECTED</span>
                  )}
                </td>
                <td style={{ padding: "12px", textAlign: "right" }}>
                  {item.status === "PENDING" ? (
                    <div style={{ display: "inline-flex", gap: "8px" }}>
                      <button
                        id={`btn-approve-${item.ticket_id}`}
                        className="btn btn-primary"
                        onClick={() => handleDecision(item.ticket_id, "APPROVED")}
                        style={{ padding: "6px 12px", fontSize: "0.75rem" }}
                      >
                        Sign & Allow
                      </button>
                      <button
                        id={`btn-reject-${item.ticket_id}`}
                        className="btn btn-danger"
                        onClick={() => handleDecision(item.ticket_id, "REJECTED")}
                        style={{ padding: "6px 12px", fontSize: "0.75rem" }}
                      >
                        Block
                      </button>
                    </div>
                  ) : (
                    <span style={{ fontSize: "0.75rem", color: "var(--text-muted)" }}>Decision Recorded</span>
                  )}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </section>
  );
};
