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

/* ── SVG icons ── */
const CheckIcon = () => (
  <svg width="12" height="12" viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
    <polyline points="2,8 6,12 14,4" />
  </svg>
);

const BlockIcon = () => (
  <svg width="12" height="12" viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
    <line x1="3" y1="3" x2="13" y2="13" />
    <line x1="13" y1="3" x2="3" y2="13" />
  </svg>
);

const RefreshIcon = () => (
  <svg width="12" height="12" viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
    <path d="M13.5 8a5.5 5.5 0 1 1-1.4-3.7" />
    <polyline points="14,2 13.5,6 9.5,5.5" />
  </svg>
);

const ClockIcon = () => (
  <svg width="13" height="13" viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth="1.4" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
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
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : "Failed to load approval requests";
      setErrorMessage(msg);
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
    <section id="approval-queue-section" className="glass-panel" style={{ padding: "18px 20px" }}>
      {/* ── Panel header ── */}
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
          <h2 className="panel-title">Human Approval Queue</h2>
          {pendingApprovals.length > 0 && (
            <span className="badge badge-approval">
              {pendingApprovals.length} PENDING
            </span>
          )}
          {loading && (
            <span style={{ fontSize: "0.725rem", color: "var(--text-muted)" }}>
              Updating…
            </span>
          )}
        </div>
        <div style={{ display: "flex", alignItems: "center", gap: "8px" }}>
          <span
            style={{
              fontSize: "0.625rem",
              color: "var(--text-muted)",
              fontFamily: "var(--font-mono)",
              letterSpacing: "0.06em",
              background: "var(--bg-elevated)",
              border: "1px solid var(--border-primary)",
              padding: "2px 7px",
              borderRadius: "4px",
            }}
          >
            SHA-256 BOUND
          </span>
          <button
            className="btn btn-ghost"
            onClick={fetchApprovals}
            style={{ fontSize: "0.75rem", padding: "4px 10px" }}
            aria-label="Refresh approvals"
          >
            <RefreshIcon /> Refresh
          </button>
        </div>
      </div>

      {/* ── Inline banners ── */}
      {actionMessage && (
        <div className="alert alert-success" style={{ marginBottom: "12px" }}>
          {actionMessage}
        </div>
      )}
      {errorMessage && (
        <div className="alert alert-danger" style={{ marginBottom: "12px" }}>
          {errorMessage}
        </div>
      )}

      {/* ── Empty state ── */}
      {approvals.length === 0 ? (
        <div className="empty-state">
          No pending approval requests. Human-in-the-loop approvals will appear here in real time
          when an agent action triggers a &apos;REQUIRE_APPROVAL&apos; policy rule.
        </div>
      ) : (
        <div
          style={{
            overflowX: "auto",
            border: "1px solid var(--border-primary)",
            borderRadius: "var(--radius-sm)",
          }}
        >
          <table style={{ fontSize: "0.8125rem", textAlign: "left" }}>
            <thead>
              <tr>
                <th>Ticket ID</th>
                <th>Agent Identity</th>
                <th>Target Tool</th>
                <th>Payload Hash</th>
                <th>TTL / Status</th>
                <th style={{ textAlign: "right" }}>Actions</th>
              </tr>
            </thead>
            <tbody>
              {approvals.map((item) => (
                <tr key={item.ticket_id} id={`row-${item.ticket_id}`}>
                  {/* Ticket ID */}
                  <td>
                    <span
                      style={{
                        fontFamily: "var(--font-mono)",
                        fontSize: "0.725rem",
                        color: "var(--info-fg)",
                      }}
                    >
                      {item.ticket_id}
                    </span>
                  </td>

                  {/* Agent */}
                  <td>
                    <div style={{ fontWeight: 500, color: "var(--text-primary)" }}>
                      {item.agent_id}
                    </div>
                    <div
                      style={{
                        fontSize: "0.6875rem",
                        color: "var(--text-muted)",
                        fontFamily: "var(--font-mono)",
                        marginTop: "2px",
                      }}
                    >
                      {item.action_id}
                    </div>
                  </td>

                  {/* Tool */}
                  <td>
                    <span className="code-pill">{item.tool_name}</span>
                    <div
                      style={{
                        fontSize: "0.6875rem",
                        color: "var(--text-muted)",
                        marginTop: "3px",
                        maxWidth: "22ch",
                        overflow: "hidden",
                        textOverflow: "ellipsis",
                        whiteSpace: "nowrap",
                      }}
                    >
                      {item.arguments_summary}
                    </div>
                  </td>

                  {/* Hash */}
                  <td>
                    <span
                      style={{
                        fontFamily: "var(--font-mono)",
                        fontSize: "0.725rem",
                        color: "var(--info-fg)",
                      }}
                    >
                      {item.canonical_hash}
                    </span>
                  </td>

                  {/* TTL */}
                  <td>
                    {item.status === "PENDING" ? (
                      <div
                        style={{
                          display: "flex",
                          alignItems: "center",
                          gap: "5px",
                          color: "var(--warning-fg)",
                          fontFamily: "var(--font-mono)",
                          fontSize: "0.725rem",
                          fontWeight: 600,
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
                  <td style={{ textAlign: "right" }}>
                    {item.status === "PENDING" ? (
                      <div style={{ display: "inline-flex", gap: "6px" }}>
                        <button
                          id={`btn-approve-${item.ticket_id}`}
                          className="btn btn-primary"
                          onClick={() => handleDecision(item.ticket_id, "APPROVED")}
                          style={{ padding: "4px 10px", fontSize: "0.75rem" }}
                        >
                          <CheckIcon /> Sign &amp; Allow
                        </button>
                        <button
                          id={`btn-reject-${item.ticket_id}`}
                          className="btn btn-danger"
                          onClick={() => handleDecision(item.ticket_id, "REJECTED")}
                          style={{ padding: "4px 10px", fontSize: "0.75rem" }}
                        >
                          <BlockIcon /> Block
                        </button>
                      </div>
                    ) : (
                      <span
                        style={{
                          fontSize: "0.725rem",
                          color: "var(--text-muted)",
                          fontFamily: "var(--font-mono)",
                        }}
                      >
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
