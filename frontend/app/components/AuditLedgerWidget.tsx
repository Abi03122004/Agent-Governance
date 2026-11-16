"use client";

import React, { useEffect, useState, useCallback } from "react";
import { api } from "../../lib/api";
import { HumanPurgeModal } from "./HumanPurgeModal";

export interface AuditEventItem {
  id: string;
  event_id?: string;
  organization_id: string;
  project_id: string;
  agent_id: string | null;
  event_type: string;
  tool_name: string | null;
  policy_decision: string | null;
  execution_state: string | null;
  severity: string;
  event_hash: string;
  prev_event_hash: string;
  previous_event_hash?: string;
  timestamp: string;
  details?: Record<string, unknown>;
}

const ShieldCheckIcon = () => (
  <svg width="13" height="13" viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
    <path d="M8 1.5L13.5 4v4.5c0 3-2.5 5-5.5 5.5C5 13.5 2.5 11.5 2.5 8.5V4L8 1.5Z" />
    <polyline points="5.5,8 7,9.5 10.5,6" />
  </svg>
);

const RefreshIcon = () => (
  <svg width="12" height="12" viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
    <path d="M13.5 8a5.5 5.5 0 1 1-1.4-3.7" />
    <polyline points="14,2 13.5,6 9.5,5.5" />
  </svg>
);

interface AuditLedgerWidgetProps {
  tenantId?: string;
}

export const AuditLedgerWidget: React.FC<AuditLedgerWidgetProps> = ({ tenantId }) => {
  const [events, setEvents] = useState<AuditEventItem[]>([]);
  const [loading, setLoading] = useState(false);
  const [verifying, setVerifying] = useState(false);
  const [isClearModalOpen, setIsClearModalOpen] = useState(false);
  const [purgeMessage, setPurgeMessage] = useState<string | null>(null);
  const [verificationResult, setVerificationResult] = useState<{
    verified: boolean;
    event_count: number;
    message: string;
  } | null>(null);

  const processAuditEvents = (raw: unknown[]): AuditEventItem[] => {
    const map = new Map<string, AuditEventItem>();
    (raw as Record<string, unknown>[]).forEach((item) => {
      const eventId = String(item.event_id || item.id || "");
      const eventHash = String(item.event_hash || "");
      const key = eventId || eventHash || JSON.stringify(item);
      map.set(key, {
        id: eventId,
        event_id: eventId,
        organization_id: String(item.organization_id || ""),
        project_id: String(item.project_id || ""),
        agent_id: item.agent_id ? String(item.agent_id) : null,
        event_type: String(item.event_type || ""),
        tool_name: item.tool_name ? String(item.tool_name) : null,
        policy_decision: item.policy_decision ? String(item.policy_decision) : null,
        execution_state: item.execution_state ? String(item.execution_state) : null,
        severity: String(item.severity || "INFO"),
        event_hash: eventHash,
        prev_event_hash: String(item.prev_event_hash || item.previous_event_hash || ""),
        previous_event_hash: String(item.previous_event_hash || item.prev_event_hash || ""),
        timestamp: String(item.timestamp || new Date().toISOString()),
        details: (item.details as Record<string, unknown>) || {},
      });
    });
    return Array.from(map.values());
  };

  const handleRefresh = useCallback(async () => {
    setLoading(true);
    try {
      const res = await api.getAuditEvents(100, tenantId);
      if (Array.isArray(res)) setEvents(processAuditEvents(res));
    } catch (e) {
      console.warn("Failed to load audit events (retrying gracefully)", e);
    } finally {
      setLoading(false);
    }
  }, [tenantId]);

  const handleClearAuditLogs = async (rationale: string) => {
    try {
      const res = await api.clearAuditLogs(tenantId, rationale);
      setPurgeMessage(res.message);
      setVerificationResult(null);
      await handleRefresh();
    } catch (err: unknown) {
      console.error("Failed to clear audit logs", err);
    }
  };

  useEffect(() => {
    void handleRefresh();
  }, [handleRefresh]);

  const verifyChain = async () => {
    try {
      setVerifying(true);
      const res = await api.verifyAuditChain();
      setVerificationResult(res);
    } catch (e: unknown) {
      const err = e as Error;
      setVerificationResult({
        verified: false,
        event_count: 0,
        message: err?.message || "Verification check failed.",
      });
    } finally {
      setVerifying(false);
    }
  };

  return (
    <section
      id="audit-ledger-section"
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
          flexWrap: "wrap",
          gap: "12px",
        }}
      >
        <div>
          <div style={{ display: "flex", alignItems: "center", gap: "10px" }}>
            <h2 style={{ fontSize: "0.9375rem", fontWeight: 600, color: "#F5F5F5", margin: 0 }}>
              Immutable Cryptographic Audit Ledger
            </h2>
            <span
              style={{
                fontSize: "0.625rem",
                color: "#10B981",
                background: "rgba(16, 185, 129, 0.12)",
                border: "1px solid rgba(16, 185, 129, 0.3)",
                padding: "2px 8px",
                borderRadius: "10px",
                fontFamily: "var(--font-mono)",
                fontWeight: 700,
              }}
            >
              SHA-256 CHAINED
            </span>
          </div>
          <p style={{ fontSize: "0.75rem", color: "#858585", marginTop: "4px" }}>
            Every lifecycle event, policy evaluation, and tool execution is hashed and cryptographically
            linked to the previous block.
          </p>
        </div>

        <div style={{ display: "flex", alignItems: "center", gap: "8px" }}>
          <button
            id="btn-verify-chain"
            className="btn btn-primary"
            onClick={verifyChain}
            disabled={verifying}
            style={{ fontSize: "0.75rem", padding: "6px 14px", borderRadius: "8px" }}
          >
            <ShieldCheckIcon />
            {verifying ? "Verifying…" : "Verify Ledger Chain"}
          </button>
          <button
            className="btn btn-ghost"
            onClick={handleRefresh}
            disabled={loading}
            style={{ fontSize: "0.75rem", padding: "6px 12px", borderRadius: "8px" }}
          >
            <RefreshIcon /> Refresh
          </button>
          <button
            id="btn-clear-audit-logs"
            className="btn btn-danger"
            onClick={() => setIsClearModalOpen(true)}
            style={{ fontSize: "0.75rem", padding: "6px 12px", borderRadius: "8px" }}
            title="Human Operator only: Clear and re-initialize audit ledger"
          >
            Clear Audit Logs
          </button>
        </div>
      </div>

      {purgeMessage && (
        <div
          style={{
            padding: "8px 14px",
            background: "rgba(16, 185, 129, 0.12)",
            border: "1px solid rgba(16, 185, 129, 0.3)",
            color: "#10B981",
            borderRadius: "8px",
            fontSize: "0.75rem",
            marginBottom: "14px",
            display: "flex",
            alignItems: "center",
            justifyContent: "space-between",
          }}
        >
          <span>✓ {purgeMessage}</span>
          <button
            onClick={() => setPurgeMessage(null)}
            style={{ background: "none", border: "none", color: "inherit", cursor: "pointer" }}
          >
            ✕
          </button>
        </div>
      )}

      {/* ── Verification Result Banner ── */}
      {verificationResult && (
        <div
          id="verification-result-banner"
          style={{
            padding: "10px 16px",
            borderRadius: "10px",
            fontSize: "0.8125rem",
            marginBottom: "16px",
            display: "flex",
            alignItems: "center",
            justifyContent: "space-between",
            background: verificationResult.verified ? "rgba(16, 185, 129, 0.12)" : "rgba(255, 73, 47, 0.14)",
            border: `1px solid ${verificationResult.verified ? "rgba(16, 185, 129, 0.35)" : "rgba(255, 73, 47, 0.45)"}`,
            color: verificationResult.verified ? "#10B981" : "#FF492F",
          }}
        >
          <span>
            <strong>
              {verificationResult.verified ? "✓ Cryptographic Proof Valid: " : "✗ Verification Failed: "}
            </strong>
            {verificationResult.message ||
              `Chained sequence of ${verificationResult.event_count} events verified with zero tampering.`}
          </span>
          <span style={{ fontSize: "0.6875rem", fontFamily: "var(--font-mono)", opacity: 0.8 }}>
            {new Date().toLocaleTimeString()}
          </span>
        </div>
      )}

      {/* ── Table Content ── */}
      {loading && events.length === 0 ? (
        <div className="empty-state">Loading audit records…</div>
      ) : events.length === 0 ? (
        <div className="empty-state">No audit events recorded in the database yet.</div>
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
                <th style={{ padding: "10px 14px" }}>Timestamp</th>
                <th style={{ padding: "10px 14px" }}>Event Type</th>
                <th style={{ padding: "10px 14px" }}>Agent / Scope</th>
                <th style={{ padding: "10px 14px" }}>Decision / State</th>
                <th style={{ padding: "10px 14px" }}>SHA-256 Hash</th>
              </tr>
            </thead>
            <tbody>
              {events.map((ev, idx) => (
                <tr
                  key={ev.id ? `${ev.id}-${idx}` : idx}
                  style={{ borderBottom: "1px solid rgba(255, 255, 255, 0.04)" }}
                >
                  {/* Timestamp */}
                  <td style={{ padding: "12px 14px" }}>
                    <span style={{ fontFamily: "var(--font-mono)", fontSize: "0.75rem", color: "#858585" }}>
                      {new Date(ev.timestamp).toLocaleString()}
                    </span>
                  </td>

                  {/* Event Type */}
                  <td style={{ padding: "12px 14px" }}>
                    <span className="code-pill">
                      {ev.event_type}
                    </span>
                  </td>

                  {/* Agent / Scope */}
                  <td style={{ padding: "12px 14px" }}>
                    <div style={{ color: "#F5F5F5", fontWeight: 500 }}>
                      {ev.agent_id || "system"}
                    </div>
                    <div style={{ fontSize: "0.6875rem", color: "#858585", marginTop: "2px", fontFamily: "var(--font-mono)" }}>
                      {ev.organization_id} / {ev.project_id}
                    </div>
                  </td>

                  {/* Decision / State */}
                  <td style={{ padding: "12px 14px" }}>
                    <div style={{ display: "flex", alignItems: "center", gap: "6px", flexWrap: "wrap" }}>
                      {ev.policy_decision && ev.policy_decision !== "N/A" ? (
                        <span
                          className={`badge ${
                            ev.policy_decision === "ALLOW"
                              ? "badge-allow"
                              : ev.policy_decision === "BLOCK"
                              ? "badge-block"
                              : ev.policy_decision === "REQUIRE_APPROVAL"
                              ? "badge-approval"
                              : "badge-neutral"
                          }`}
                        >
                          {ev.policy_decision}
                        </span>
                      ) : (
                        <span style={{ fontSize: "0.75rem", color: "#5E5E66", fontFamily: "var(--font-mono)" }}>
                          —
                        </span>
                      )}
                      {ev.execution_state && (
                        <span style={{ fontSize: "0.725rem", color: "#A1A1A8", fontFamily: "var(--font-mono)" }}>
                          {ev.execution_state}
                        </span>
                      )}
                    </div>
                  </td>

                  {/* Hash Chain */}
                  <td style={{ padding: "12px 14px" }}>
                    <div
                      title={`Event Hash: ${ev.event_hash}`}
                      style={{
                        fontFamily: "var(--font-mono)",
                        fontSize: "0.725rem",
                        color: "#10B981",
                        fontWeight: 500,
                      }}
                    >
                      {ev.event_hash ? ev.event_hash.slice(0, 20) + "…" : "genesis"}
                    </div>
                    <div
                      title={`Prev Hash: ${ev.prev_event_hash}`}
                      style={{
                        fontSize: "0.65rem",
                        color: "#858585",
                        fontFamily: "var(--font-mono)",
                        marginTop: "2px",
                      }}
                    >
                      prev: {ev.prev_event_hash ? ev.prev_event_hash.slice(0, 16) + "…" : "00000000"}
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {/* Human Purge Confirmation Modal */}
      <HumanPurgeModal
        isOpen={isClearModalOpen}
        onClose={() => setIsClearModalOpen(false)}
        title="Clear Cryptographic Audit Ledger"
        targetDescription={tenantId ? `Tenant ${tenantId} Audit Events` : "Global Audit Events (All Tenants)"}
        warningNote="Permanently removes all historical audit trail records and re-initializes a fresh cryptographic SHA-256 genesis event. Autonomous agents cannot perform this."
        actionButtonText="Authorize & Clear Audit Ledger"
        onConfirm={handleClearAuditLogs}
      />
    </section>
  );
};
