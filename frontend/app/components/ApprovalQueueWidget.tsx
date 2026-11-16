"use client";

import React, { useEffect, useState, useCallback } from "react";
import { api } from "../../lib/api";

export interface ApprovalItem {
  ticket_id: string;
  action_id: string;
  agent_id: string;
  tool_name: string;
  arguments_summary: string;
  canonical_hash: string;
  expires_in_minutes: number;
  status: "PENDING" | "APPROVED" | "REJECTED";
}

interface ApprovalQueueWidgetProps {
  tenantId?: string;
}

const CheckIcon = () => (
  <svg width="12" height="12" viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth="2.2" strokeLinecap="round" strokeLinejoin="round">
    <polyline points="2,8 6,12 14,4" />
  </svg>
);

const BlockIcon = () => (
  <svg width="12" height="12" viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth="2.2" strokeLinecap="round" strokeLinejoin="round">
    <line x1="3" y1="3" x2="13" y2="13" />
    <line x1="13" y1="3" x2="3" y2="13" />
  </svg>
);

const RefreshIcon = () => (
  <svg width="12" height="12" viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
    <path d="M13.5 8a5.5 5.5 0 1 1-1.4-3.7" />
    <polyline points="14,2 13.5,6 9.5,5.5" />
  </svg>
);

const ClockIcon = () => (
  <svg width="13" height="13" viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round">
    <circle cx="8" cy="8" r="6" />
    <polyline points="8,4.5 8,8 10,10" />
  </svg>
);

export const ApprovalQueueWidget: React.FC<ApprovalQueueWidgetProps> = ({ tenantId }) => {
  const [approvals, setApprovals] = useState<ApprovalItem[]>([]);
  const [loading, setLoading] = useState(false);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const [actionMessage, setActionMessage] = useState<string | null>(null);

  const fetchApprovals = useCallback(async () => {
    setLoading(true);
    setErrorMessage(null);
    try {
      const res = await api.getApprovals("PENDING", tenantId || undefined);
      if (Array.isArray(res)) {
        const map = new Map<string, ApprovalItem>();
        res.forEach((r: Record<string, unknown>) => {
          const ticketId = String(r.ticket_id || "");
          if (!ticketId) return;
          const expTime = r.expires_at
            ? new Date(String(r.expires_at)).getTime()
            : Date.now() + 600000;
          const minsRemaining = Math.max(0, Math.round((expTime - Date.now()) / 60000));
          const canonHash = typeof r.canonical_action_hash === "string" ? r.canonical_action_hash : "";
          map.set(ticketId, {
            ticket_id: ticketId,
            action_id: String(r.action_id || ""),
            agent_id: String(r.agent_id || "agent"),
            tool_name: String(r.tool_name || r.tool || "mutation_tool"),
            arguments_summary: String(r.arguments_summary || JSON.stringify(r.arguments || {})),
            canonical_hash: canonHash ? `${canonHash.slice(0, 14)}…` : "sha256:verified",
            expires_in_minutes: minsRemaining,
            status: (r.status as "PENDING" | "APPROVED" | "REJECTED") || "PENDING",
          });
        });
        setApprovals(Array.from(map.values()));
      } else {
        setApprovals([]);
      }
    } catch {
      // offline or initial load - keep quiet
    } finally {
      setLoading(false);
    }
  }, [tenantId]);

  useEffect(() => {
    void fetchApprovals();
    const interval = setInterval(() => void fetchApprovals(), 10000);
    return () => clearInterval(interval);
  }, [fetchApprovals]);

  const handleDecision = async (ticketId: string, decision: "APPROVED" | "REJECTED") => {
    setErrorMessage(null);
    try {
      if (decision === "APPROVED") {
        await api.approveAction(ticketId, "Approved via Dashboard Reviewer");
      } else {
        await api.rejectAction(ticketId, "Blocked via Dashboard Reviewer");
      }
      setApprovals((prev) =>
        prev.map((item) =>
          item.ticket_id === ticketId ? { ...item, status: decision } : item,
        ),
      );
      setActionMessage(`Ticket ${ticketId} marked as ${decision}.`);
      setTimeout(() => setActionMessage(null), 4000);
      void fetchApprovals();
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : `Failed to ${decision.toLowerCase()} ticket`;
      setErrorMessage(`Action failed: ${msg}`);
    }
  };

  const pendingApprovals = approvals.filter((a) => a.status === "PENDING");

  return (
    <section
      id="approval-queue-section"
      className="glass-panel"
      style={{
        padding: "20px 22px",
        background: "#18171B",
        border: "1px solid #262529",
        borderRadius: "20px",
      }}
    >
      {/* ── Panel Header ── */}
      <div
        style={{
          display: "flex",
          alignItems: "center",
          justifyContent: "space-between",
          marginBottom: "16px",
          gap: "12px",
          flexWrap: "wrap",
        }}
      >
        <div style={{ display: "flex", alignItems: "center", gap: "10px" }}>
          <h2 style={{ fontSize: "0.9375rem", fontWeight: 600, color: "#F5F5F5", margin: 0 }}>
            Human Approval Queue
          </h2>
          {pendingApprovals.length > 0 && (
            <span
              style={{
                fontSize: "0.6875rem",
                fontWeight: 700,
                color: "#FF7043",
                background: "rgba(255, 112, 67, 0.12)",
                border: "1px solid rgba(255, 112, 67, 0.3)",
                padding: "2px 8px",
                borderRadius: "12px",
                fontFamily: "var(--font-mono)",
              }}
            >
              {pendingApprovals.length} PENDING
            </span>
          )}
          {loading && (
            <span style={{ fontSize: "0.725rem", color: "#858585" }}>
              Syncing…
            </span>
          )}
        </div>

        <div style={{ display: "flex", alignItems: "center", gap: "8px" }}>
          <span
            style={{
              fontSize: "0.625rem",
              color: "#858585",
              fontFamily: "var(--font-mono)",
              letterSpacing: "0.06em",
              background: "#141316",
              border: "1px solid #262529",
              padding: "2px 8px",
              borderRadius: "6px",
            }}
          >
            SHA-256 BOUND
          </span>
          <button
            className="btn btn-ghost"
            onClick={fetchApprovals}
            style={{ fontSize: "0.75rem", padding: "4px 10px", borderRadius: "8px" }}
            aria-label="Refresh approvals"
          >
            <RefreshIcon /> Refresh
          </button>
        </div>
      </div>

      {/* ── Inline Messages ── */}
      {actionMessage && (
        <div
          style={{
            padding: "8px 12px",
            background: "rgba(16, 185, 129, 0.12)",
            border: "1px solid rgba(16, 185, 129, 0.3)",
            color: "#10B981",
            borderRadius: "8px",
            fontSize: "0.75rem",
            marginBottom: "12px",
          }}
        >
          {actionMessage}
        </div>
      )}
      {errorMessage && (
        <div
          style={{
            padding: "8px 12px",
            background: "rgba(255, 73, 47, 0.14)",
            border: "1px solid rgba(255, 73, 47, 0.35)",
            color: "#FF492F",
            borderRadius: "8px",
            fontSize: "0.75rem",
            marginBottom: "12px",
          }}
        >
          {errorMessage}
        </div>
      )}

      {/* ── Empty State ── */}
      {approvals.length === 0 ? (
        <div className="empty-state">
          No pending approval requests. Human-in-the-loop approvals will appear here in real time
          when an autonomous agent action triggers a &apos;REQUIRE_APPROVAL&apos; policy constraint.
        </div>
      ) : (
        <div
          style={{
            overflowX: "auto",
            border: "1px solid #262529",
            borderRadius: "14px",
          }}
        >
          <table style={{ fontSize: "0.8125rem", textAlign: "left", width: "100%" }}>
            <thead>
              <tr style={{ background: "#141316", color: "#858585", borderBottom: "1px solid #262529" }}>
                <th style={{ padding: "10px 14px" }}>Ticket ID</th>
                <th style={{ padding: "10px 14px" }}>Agent Identity</th>
                <th style={{ padding: "10px 14px" }}>Target Tool</th>
                <th style={{ padding: "10px 14px" }}>Payload Hash</th>
                <th style={{ padding: "10px 14px" }}>TTL / Status</th>
                <th style={{ padding: "10px 14px", textAlign: "right" }}>Actions</th>
              </tr>
            </thead>
            <tbody>
              {approvals.map((item) => (
                <tr
                  key={item.ticket_id}
                  id={`row-${item.ticket_id}`}
                  style={{ borderBottom: "1px solid rgba(255, 255, 255, 0.04)" }}
                >
                  {/* Ticket ID */}
                  <td style={{ padding: "12px 14px" }}>
                    <span style={{ fontFamily: "var(--font-mono)", fontSize: "0.75rem", color: "#FF7043", fontWeight: 600 }}>
                      {item.ticket_id}
                    </span>
                  </td>

                  {/* Agent */}
                  <td style={{ padding: "12px 14px" }}>
                    <div style={{ fontWeight: 600, color: "#F5F5F5" }}>{item.agent_id}</div>
                    <div style={{ fontSize: "0.6875rem", color: "#858585", fontFamily: "var(--font-mono)", marginTop: "2px" }}>
                      {item.action_id}
                    </div>
                  </td>

                  {/* Tool */}
                  <td style={{ padding: "12px 14px" }}>
                    <span className="code-pill">{item.tool_name}</span>
                    <div
                      style={{
                        fontSize: "0.6875rem",
                        color: "#858585",
                        marginTop: "3px",
                        maxWidth: "24ch",
                        overflow: "hidden",
                        textOverflow: "ellipsis",
                        whiteSpace: "nowrap",
                      }}
                    >
                      {item.arguments_summary}
                    </div>
                  </td>

                  {/* Hash */}
                  <td style={{ padding: "12px 14px" }}>
                    <span style={{ fontFamily: "var(--font-mono)", fontSize: "0.725rem", color: "#A78BFA" }}>
                      {item.canonical_hash}
                    </span>
                  </td>

                  {/* TTL */}
                  <td style={{ padding: "12px 14px" }}>
                    {item.status === "PENDING" ? (
                      <div
                        style={{
                          display: "inline-flex",
                          alignItems: "center",
                          gap: "5px",
                          color: "#FFA726",
                          fontFamily: "var(--font-mono)",
                          fontSize: "0.75rem",
                          fontWeight: 600,
                          background: "rgba(255, 152, 0, 0.1)",
                          padding: "2px 8px",
                          borderRadius: "10px",
                        }}
                      >
                        <ClockIcon />
                        {item.expires_in_minutes}m
                      </div>
                    ) : item.status === "APPROVED" ? (
                      <span className="badge badge-allow">APPROVED</span>
                    ) : (
                      <span className="badge badge-block">REJECTED</span>
                    )}
                  </td>

                  {/* Actions */}
                  <td style={{ padding: "12px 14px", textAlign: "right" }}>
                    {item.status === "PENDING" ? (
                      <div style={{ display: "inline-flex", gap: "8px" }}>
                        <button
                          id={`btn-approve-${item.ticket_id}`}
                          className="btn btn-primary"
                          onClick={() => handleDecision(item.ticket_id, "APPROVED")}
                          style={{ padding: "5px 12px", fontSize: "0.75rem", borderRadius: "8px" }}
                        >
                          <CheckIcon /> Sign &amp; Allow
                        </button>
                        <button
                          id={`btn-reject-${item.ticket_id}`}
                          className="btn btn-danger"
                          onClick={() => handleDecision(item.ticket_id, "REJECTED")}
                          style={{ padding: "5px 12px", fontSize: "0.75rem", borderRadius: "8px" }}
                        >
                          <BlockIcon /> Block
                        </button>
                      </div>
                    ) : (
                      <span style={{ fontSize: "0.725rem", color: "#858585", fontFamily: "var(--font-mono)" }}>
                        Resolved
                      </span>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </section>
  );
};
