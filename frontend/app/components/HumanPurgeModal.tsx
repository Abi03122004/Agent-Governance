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
        background: "rgba(0, 0, 0, 0.85)",
        backdropFilter: "blur(8px)",
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
          background: "#18171B",
          border: "1px solid rgba(255, 73, 47, 0.4)",
          borderRadius: "22px",
          width: "100%",
          maxWidth: "520px",
          padding: "24px 26px",
          display: "flex",
          flexDirection: "column",
          gap: "18px",
          boxShadow: "0 24px 48px rgba(0, 0, 0, 0.7), 0 0 30px rgba(255, 73, 47, 0.15)",
        }}
        onClick={(e) => e.stopPropagation()}
      >
        {/* Header */}
        <div style={{ display: "flex", alignItems: "flex-start", justifyContent: "space-between", gap: "12px" }}>
          <div style={{ display: "flex", alignItems: "center", gap: "12px" }}>
            <div
              style={{
                width: "40px",
                height: "40px",
                borderRadius: "12px",
                background: "rgba(255, 73, 47, 0.14)",
                border: "1px solid rgba(255, 73, 47, 0.35)",
                display: "flex",
                alignItems: "center",
                justifyContent: "center",
                color: "#FF492F",
                flexShrink: 0,
              }}
            >
              <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                <path d="M10.29 3.86L1.82 18a2 2 0 0 0 1.71 3h16.94a2 2 0 0 0 1.71-3L13.71 3.86a2 2 0 0 0-3.42 0z" />
                <line x1="12" y1="9" x2="12" y2="13" />
                <line x1="12" y1="17" x2="12.01" y2="17" />
              </svg>
            </div>
            <div>
              <div style={{ fontSize: "0.6875rem", fontFamily: "var(--font-mono)", color: "#FF492F", fontWeight: 700, letterSpacing: "0.08em", textTransform: "uppercase" }}>
                Human Operator Action
              </div>
              <h2 style={{ fontSize: "1.05rem", fontWeight: 700, color: "#F5F5F5", margin: "2px 0 0" }}>
                {title}
              </h2>
            </div>
          </div>
          <button
            onClick={onClose}
            style={{
              background: "transparent",
              border: "none",
              color: "#858585",
              cursor: "pointer",
              fontSize: "1.2rem",
              padding: "4px",
              lineHeight: 1,
            }}
            aria-label="Close modal"
          >
            ✕
          </button>
        </div>

        {/* Target Description */}
        <div
          style={{
            background: "#141316",
            border: "1px solid #262529",
            borderRadius: "12px",
            padding: "12px 14px",
            display: "flex",
            flexDirection: "column",
            gap: "4px",
          }}
        >
          <span style={{ fontSize: "0.6875rem", color: "#858585", textTransform: "uppercase", fontFamily: "var(--font-mono)" }}>
            Scope Target:
          </span>
          <span style={{ fontSize: "0.875rem", color: "#F5F5F5", fontWeight: 600, fontFamily: "var(--font-mono)" }}>
            {targetDescription}
          </span>
        </div>

        {/* Warning Note */}
        <div
          style={{
            background: "rgba(255, 73, 47, 0.08)",
            border: "1px solid rgba(255, 73, 47, 0.25)",
            borderRadius: "12px",
            padding: "12px 14px",
            color: "#FFA198",
            fontSize: "0.78125rem",
            lineHeight: "1.5",
          }}
        >
          <strong>Warning: </strong>{warningNote}
        </div>

        {errorMessage && (
          <div
            style={{
              padding: "10px 14px",
              background: "rgba(255, 73, 47, 0.15)",
              border: "1px solid rgba(255, 73, 47, 0.4)",
              color: "#FF492F",
              borderRadius: "8px",
              fontSize: "0.75rem",
            }}
          >
            {errorMessage}
          </div>
        )}

        {/* Confirmation Form */}
        <form onSubmit={handleExecute} style={{ display: "flex", flexDirection: "column", gap: "14px" }}>
          <div>
            <label
              htmlFor="purge-rationale"
              style={{ display: "block", fontSize: "0.75rem", fontWeight: 600, color: "#F5F5F5", marginBottom: "6px" }}
            >
              Operator Rationale <span style={{ color: "#858585" }}>(Required for cryptographic audit trail)</span>
            </label>
            <textarea
              id="purge-rationale"
              required
              rows={2}
              placeholder="e.g. End of sprint test cleanup authorized by security engineer"
              value={rationale}
              onChange={(e) => setRationale(e.target.value)}
              style={{
                width: "100%",
                background: "#141316",
                color: "#F5F5F5",
                border: "1px solid #262529",
                borderRadius: "10px",
                padding: "8px 12px",
                fontSize: "0.8125rem",
                outline: "none",
                resize: "vertical",
              }}
            />
          </div>

          <div>
            <label
              htmlFor="purge-confirmation-input"
              style={{ display: "block", fontSize: "0.75rem", fontWeight: 600, color: "#F5F5F5", marginBottom: "6px" }}
            >
              Type <strong style={{ color: "#FF492F" }}>CONFIRM</strong> to authorize this destructive operation
            </label>
            <input
              id="purge-confirmation-input"
              type="text"
              autoComplete="off"
              required
              placeholder="CONFIRM"
              value={confirmationInput}
              onChange={(e) => setConfirmationInput(e.target.value)}
              style={{
                width: "100%",
                background: "#141316",
                color: "#F5F5F5",
                border: "1px solid #262529",
                borderRadius: "10px",
                padding: "8px 12px",
                fontSize: "0.875rem",
                fontFamily: "var(--font-mono)",
                outline: "none",
              }}
            />
          </div>

          <div style={{ display: "flex", alignItems: "center", justifyContent: "flex-end", gap: "10px", marginTop: "6px" }}>
            <button
              type="button"
              className="btn btn-ghost"
              onClick={onClose}
              disabled={isSubmitting}
              style={{ padding: "8px 16px" }}
            >
              Cancel
            </button>
            <button
              type="submit"
              className="btn btn-primary"
              disabled={!isConfirmed || isSubmitting || !rationale.trim()}
              style={{
                padding: "8px 18px",
                background: isConfirmed && rationale.trim() ? "linear-gradient(135deg, #FF492F 0%, #D32F2F 100%)" : "#262529",
                color: isConfirmed && rationale.trim() ? "#FFFFFF" : "#858585",
                border: "none",
                boxShadow: isConfirmed && rationale.trim() ? "0 4px 14px rgba(255, 73, 47, 0.4)" : "none",
              }}
            >
              {isSubmitting ? "Purging…" : actionButtonText}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
};
