"use client";

import React, { useEffect, useState } from "react";
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

/* ── SVG icons ── */
const ShieldCheckIcon = () => (
  <svg width="13" height="13" viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
    <path d="M8 1.5L13.5 4v4.5c0 3-2.5 5-5.5 5.5C5 13.5 2.5 11.5 2.5 8.5V4L8 1.5Z" />
    <polyline points="5.5,8 7,9.5 10.5,6" />
  </svg>
);

const RefreshIcon = () => (
  <svg width="12" height="12" viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
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

  const handleRefresh = async () => {
    setLoading(true);
    try {
      const res = await api.getAuditEvents(100, tenantId);
      if (Array.isArray(res)) setEvents(processAuditEvents(res));
    } catch (e) {
      console.error("Failed to load audit events", e);
    } finally {
      setLoading(false);
    }
  };

  const handleClearAuditLogs = async (rationale: string) => {
    const res = await api.clearAuditLogs(tenantId, rationale);
    setPurgeMessage(res.message);
    setVerificationResult(null);
    await handleRefresh();
  };

  useEffect(() => {
    let active = true;
    const fetchAudit = async () => {
      try {
        const res = await api.getAuditEvents(100, tenantId);
        if (active && Array.isArray(res)) setEvents(processAuditEvents(res));
      } catch (e) {
        console.error("Failed to load audit events", e);
      }
    };
    void fetchAudit();
    return () => { active = false; };
  }, [tenantId]);

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
    <section id="audit-ledger-section" className="glass-panel" style={{ padding: "18px 20px" }}>
      {/* ── Panel header ── */}
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
            <h2 className="panel-title">Immutable Cryptographic Audit Ledger</h2>
          </div>
          <p className="panel-subtitle" style={{ marginTop: "4px" }}>
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
            style={{ fontSize: "0.75rem", padding: "5px 12px" }}
          >
            <ShieldCheckIcon />
            {verifying ? "Verifying…" : "Verify Ledger Chain"}
          </button>
          <button
            className="btn btn-ghost"
            onClick={handleRefresh}
            disabled={loading}
            style={{ fontSize: "0.75rem", padding: "5px 10px" }}
          >
            <RefreshIcon /> Refresh
          </button>
          <button
            id="btn-clear-audit-logs"
            className="btn btn-danger"
            onClick={() => setIsClearModalOpen(true)}
            style={{ fontSize: "0.75rem", padding: "5px 12px" }}
            title="Human Operator only: Clear and re-initialize audit ledger"
          >
            Clear Audit Logs
          </button>
        </div>
      </div>

      {purgeMessage && (
        <div className="alert alert-success" style={{ marginBottom: "14px" }}>
          <span>✓ {purgeMessage}</span>
          <button
            onClick={() => setPurgeMessage(null)}
            style={{ background: "none", border: "none", color: "inherit", cursor: "pointer", marginLeft: "auto" }}
          >
            ✕
          </button>
        </div>
      )}

      {/* ── Verification result banner ── */}
      {verificationResult && (
        <div
          id="verification-result-banner"
          className={`alert ${verificationResult.verified ? "alert-success" : "alert-danger"}`}
          style={{ marginBottom: "14px", justifyContent: "space-between" }}
        >
          <span>
            <strong>
              {verificationResult.verified ? "✓ Cryptographic Proof Valid: " : "✗ Verification Failed: "}
            </strong>
            {verificationResult.message ||
              `Chained sequence of ${verificationResult.event_count} events verified with zero tampering.`}
          </span>
          <span
            style={{
              fontSize: "0.6875rem",
              fontFamily: "var(--font-mono)",
              flexShrink: 0,
              opacity: 0.8,
            }}
          >
            {new Date().toLocaleTimeString()}
          </span>
        </div>
      )}

      {/* ── Table / states ── */}
      {loading && events.length === 0 ? (
        <div className="empty-state">Loading audit records…</div>
      ) : events.length === 0 ? (
        <div className="empty-state">No audit events recorded in the database yet.</div>
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
                <th>Timestamp</th>
                <th>Event Type</th>
                <th>Agent / Scope</th>
                <th>Decision / State</th>
                <th>SHA-256 Hash</th>
              </tr>
            </thead>
            <tbody>
              {events.map((ev, idx) => (
                <tr key={ev.id ? `${ev.id}-${idx}` : idx}>
                  {/* Timestamp */}
                  <td>
                    <span
                      style={{
                        fontFamily: "var(--font-mono)",
                        fontSize: "0.725rem",
                        color: "var(--text-muted)",
                      }}
                    >
                      {new Date(ev.timestamp).toLocaleString()}
                    </span>
                  </td>

                  {/* Event type */}
                  <td>
                    <span className="code-pill" style={{ color: "var(--info-fg)" }}>
                      {ev.event_type}
                    </span>
                  </td>

                  {/* Agent / scope */}
                  <td>
                    <div style={{ color: "var(--text-primary)", fontWeight: 500 }}>
                      {ev.agent_id || "system"}
                    </div>
                    <div
                      style={{
                        fontSize: "0.6875rem",
                        color: "var(--text-muted)",
                        marginTop: "2px",
                      }}
                    >
                      {ev.organization_id} / {ev.project_id}
                    </div>
                  </td>

                  {/* Decision / state */}
                  <td>
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
                        <span
                          style={{
                            fontSize: "0.725rem",
                            color: "var(--text-muted)",
                            fontFamily: "var(--font-mono)",
                          }}
                        >
                          —
                        </span>
                      )}
                      {ev.execution_state && (
                        <span
                          style={{
                            fontSize: "0.725rem",
                            color: "var(--text-secondary)",
                            fontFamily: "var(--font-mono)",
                          }}
                        >
                          {ev.execution_state}
                        </span>
                      )}
                    </div>
                  </td>

                  {/* Hash chain */}
                  <td>
                    <div
                      title={`Event Hash: ${ev.event_hash}`}
                      style={{
                        fontFamily: "var(--font-mono)",
                        fontSize: "0.7rem",
                        color: "var(--success-fg)",
                      }}
                    >
                      {ev.event_hash ? ev.event_hash.slice(0, 20) + "…" : "genesis"}
                    </div>
                    <div
                      title={`Prev Hash: ${ev.prev_event_hash}`}
                      style={{
                        fontSize: "0.65rem",
                        color: "var(--text-muted)",
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
        warningNote="Permanently removes all historical audit trail records and re-initializes a fresh cryptographic SHA-256 genesis event. AI agents are blocked from performing this operation."
        actionButtonText="Authorize & Clear Audit Ledger"
        onConfirm={handleClearAuditLogs}
      />
    </section>
  );
};
