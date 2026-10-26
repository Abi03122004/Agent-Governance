"use client";

import React, { useState } from "react";

interface HumanPurgeModalProps {
  isOpen: boolean;
  onClose: () => void;
  title: string;
  targetDescription: string;
  warningNote: string;
  actionButtonText?: string;
  onConfirm: (rationale: string) => Promise<void>;
}

export const HumanPurgeModal: React.FC<HumanPurgeModalProps> = ({
  isOpen,
  onClose,
  title,
  targetDescription,
  warningNote,
  actionButtonText = "Authorize & Permanently Delete",
  onConfirm,
}) => {
  const [confirmationInput, setConfirmationInput] = useState("");
  const [rationale, setRationale] = useState("");
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);

  if (!isOpen) return null;

  const isConfirmed = confirmationInput.trim().toUpperCase() === "CONFIRM";

  const handleExecute = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!isConfirmed) return;

    setIsSubmitting(true);
    setErrorMessage(null);
    try {
      await onConfirm(rationale || "Human Operator Authorized Purge");
      setConfirmationInput("");
      setRationale("");
      onClose();
    } catch (err: unknown) {
      setErrorMessage(err instanceof Error ? err.message : "Failed to execute deletion operation");
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <div
      role="dialog"
      aria-modal="true"
      style={{
        position: "fixed",
        inset: 0,
        background: "rgba(5, 10, 14, 0.88)",
        backdropFilter: "blur(6px)",
        display: "flex",
        alignItems: "center",
        justifyContent: "center",
        zIndex: 200,
        padding: "20px",
      }}
      onClick={onClose}
    >
      <div
        style={{
          background: "var(--bg-panel)",
          border: "1px solid rgba(239, 68, 68, 0.4)",
          borderRadius: "var(--radius-lg)",
          width: "100%",
          maxWidth: "520px",
          padding: "24px",
          display: "flex",
          flexDirection: "column",
          gap: "18px",
          boxShadow: "0 24px 48px rgba(0, 0, 0, 0.7), 0 0 24px rgba(239, 68, 68, 0.15)",
        }}
        onClick={(e) => e.stopPropagation()}
      >
        {/* Header */}
        <div style={{ display: "flex", alignItems: "flex-start", justifyContent: "space-between", gap: "12px" }}>
          <div style={{ display: "flex", alignItems: "center", gap: "10px" }}>
            <div
              style={{
                width: "36px",
                height: "36px",
                borderRadius: "8px",
                background: "rgba(239, 68, 68, 0.12)",
                border: "1px solid rgba(239, 68, 68, 0.35)",
                display: "flex",
                alignItems: "center",
                justifyContent: "center",
                color: "var(--danger-fg)",
                flexShrink: 0,
              }}
            >
              <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                <path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z" />
                <line x1="12" y1="8" x2="12" y2="12" />
                <line x1="12" y1="16" x2="12.01" y2="16" />
              </svg>
            </div>
            <div>
              <div
                style={{
                  fontSize: "0.625rem",
                  fontFamily: "var(--font-mono)",
                  fontWeight: 700,
                  letterSpacing: "0.08em",
                  textTransform: "uppercase",
                  color: "var(--danger-fg)",
                }}
              >
                HUMAN-ONLY CONTROL PLANE
              </div>
              <h2
                style={{
                  fontSize: "1.0625rem",
                  fontWeight: 700,
                  color: "var(--text-primary)",
                  margin: "2px 0 0",
                  letterSpacing: "-0.01em",
                }}
              >
                {title}
              </h2>
            </div>
          </div>
          <button
            onClick={onClose}
            style={{
              background: "transparent",
              border: "none",
              color: "var(--text-muted)",
              fontSize: "1.25rem",
              cursor: "pointer",
              padding: "4px",
            }}
          >
            ✕
          </button>
        </div>

        {/* Security Warning Notice */}
        <div
          style={{
            background: "rgba(239, 68, 68, 0.08)",
            border: "1px solid rgba(239, 68, 68, 0.25)",
            borderRadius: "6px",
            padding: "12px 14px",
            display: "flex",
            flexDirection: "column",
            gap: "6px",
          }}
        >
          <div style={{ display: "flex", alignItems: "center", gap: "6px", color: "var(--danger-fg)", fontSize: "0.75rem", fontWeight: 600 }}>
            <span>⚠️</span>
            <span>RESTRICTED HUMAN OPERATOR PRIVILEGE</span>
          </div>
          <div style={{ fontSize: "0.75rem", color: "var(--text-secondary)", lineHeight: 1.45 }}>
            {warningNote}
          </div>
          <div style={{ fontSize: "0.6875rem", fontFamily: "var(--font-mono)", color: "var(--text-muted)", marginTop: "2px" }}>
            Target: <span style={{ color: "var(--text-primary)" }}>{targetDescription}</span>
          </div>
        </div>

        {/* Form */}
        <form onSubmit={handleExecute} style={{ display: "flex", flexDirection: "column", gap: "14px" }}>
          <div>
            <label
              htmlFor="confirmation-input"
              style={{
                display: "block",
                fontSize: "0.75rem",
                color: "var(--text-secondary)",
                marginBottom: "6px",
                fontFamily: "var(--font-mono)",
              }}
            >
              Type <strong style={{ color: "var(--danger-fg)" }}>CONFIRM</strong> to authorize deletion:
            </label>
            <input
              id="confirmation-input"
              type="text"
              autoFocus
              value={confirmationInput}
              onChange={(e) => setConfirmationInput(e.target.value)}
              placeholder="CONFIRM"
              style={{
                width: "100%",
                padding: "8px 12px",
                background: "var(--bg-code)",
                border: isConfirmed ? "1px solid var(--danger-fg)" : "1px solid var(--border-primary)",
                borderRadius: "var(--radius-sm)",
                color: "var(--text-primary)",
                fontFamily: "var(--font-mono)",
                fontSize: "0.875rem",
                letterSpacing: "0.05em",
                outline: "none",
              }}
            />
          </div>

          <div>
            <label
              htmlFor="operator-rationale"
              style={{
                display: "block",
                fontSize: "0.75rem",
                color: "var(--text-secondary)",
                marginBottom: "4px",
              }}
            >
              Operator Rationale (Recorded in immutable audit event):
            </label>
            <input
              id="operator-rationale"
              type="text"
              value={rationale}
              onChange={(e) => setRationale(e.target.value)}
              placeholder="e.g. End-of-cycle cleanup / Test agent decommission"
              style={{
                width: "100%",
                padding: "7px 10px",
                background: "var(--bg-code)",
                border: "1px solid var(--border-primary)",
                borderRadius: "var(--radius-sm)",
                color: "var(--text-primary)",
                fontSize: "0.8125rem",
              }}
            />
          </div>

          {errorMessage && (
            <div
              style={{
                padding: "8px 12px",
                borderRadius: "4px",
                background: "var(--danger-bg)",
                border: "1px solid var(--danger-border)",
                color: "var(--danger-fg)",
                fontSize: "0.75rem",
              }}
            >
              {errorMessage}
            </div>
          )}

          {/* Footer actions */}
          <div style={{ display: "flex", justifyContent: "flex-end", gap: "10px", marginTop: "4px" }}>
            <button
              type="button"
              className="btn btn-ghost"
              onClick={onClose}
              disabled={isSubmitting}
              style={{ padding: "6px 14px" }}
            >
              Cancel
            </button>
            <button
              type="submit"
              disabled={!isConfirmed || isSubmitting}
              style={{
                display: "inline-flex",
                alignItems: "center",
                gap: "6px",
                padding: "6px 16px",
                borderRadius: "var(--radius-sm)",
                background: isConfirmed ? "var(--danger-fg)" : "rgba(239, 68, 68, 0.2)",
                color: isConfirmed ? "#081115" : "var(--text-muted)",
                border: "none",
                fontWeight: 700,
                fontSize: "0.8125rem",
                fontFamily: "var(--font-mono)",
                cursor: isConfirmed && !isSubmitting ? "pointer" : "not-allowed",
                transition: "all 0.15s ease",
              }}
            >
              {isSubmitting ? "Purging..." : actionButtonText}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
};
