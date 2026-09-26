"use client";

import React, { useState, useEffect } from "react";

export interface AddAgentModalProps {
  isOpen: boolean;
  onClose: () => void;
  apiBaseUrl: string;
  currentTenant: string;
  onAgentRegistered: (
    newAgent: {
      agent_id: string;
      name: string;
      organization_id: string;
      project_id: string;
      environment: string;
      status: string;
      last_activity: string | null;
      action_count: number;
    },
    credential?: {
      id: string;
      plaintext_secret: string;
    }
  ) => void;
}

interface ProjectOption {
  id: string;
  name: string;
  organization_id: string;
}

export const AddAgentModal: React.FC<AddAgentModalProps> = ({
  isOpen,
  onClose,
  apiBaseUrl,
  currentTenant,
  onAgentRegistered,
}) => {
  // Form fields
  const [name, setName] = useState("");
  const [agentId, setAgentId] = useState("");
  const [agentIdTouched, setAgentIdTouched] = useState(false);
  const [owner, setOwner] = useState("security_admin@enterprise.internal");
  const [environment, setEnvironment] = useState("development");
  const [purpose, setPurpose] = useState("");
  const [organizationId, setOrganizationId] = useState(currentTenant || "org_enterprise");
  const [projectId, setProjectId] = useState("proj_operations");
  const [isCustomProject, setIsCustomProject] = useState(false);
  const [customProjectId, setCustomProjectId] = useState("");

  // Projects list for tenant
  const [availableProjects, setAvailableProjects] = useState<ProjectOption[]>([]);
  const [loadingProjects, setLoadingProjects] = useState(false);

  // Submission & UI states
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);

  // Success & Credential display state
  const [successData, setSuccessData] = useState<{
    agent: {
      id: string;
      name: string;
      organization_id: string;
      project_id: string;
      environment: string;
      owner: string;
      status: string;
    };
    credential?: {
      id: string;
      plaintext_secret: string;
    };
  } | null>(null);

  const [copiedSecret, setCopiedSecret] = useState(false);
  const [showSecret, setShowSecret] = useState(false);

  // Sync organization when currentTenant changes without triggering cascading renders
  const [prevTenant, setPrevTenant] = useState(currentTenant);
  if (currentTenant !== prevTenant) {
    setPrevTenant(currentTenant);
    setOrganizationId(currentTenant);
  }

  // Load existing projects for current organization
  useEffect(() => {
    let ignore = false;
    if (isOpen && organizationId) {
      const controller = new AbortController();
      fetch(`${apiBaseUrl}/api/v1/projects?organization_id=${encodeURIComponent(organizationId)}`, {
        signal: controller.signal,
      })
        .then((res) => (res.ok ? res.json() : []))
        .then((data: ProjectOption[]) => {
          if (!ignore) {
            setAvailableProjects(data || []);
            if (data && data.length > 0) {
              setProjectId(data[0].id);
              setIsCustomProject(false);
            } else {
              setIsCustomProject(true);
              setCustomProjectId("proj_operations");
            }
            setLoadingProjects(false);
          }
        })
        .catch((err: unknown) => {
          if (!ignore && !(err instanceof DOMException && err.name === "AbortError")) {
            setAvailableProjects([]);
            setIsCustomProject(true);
            setCustomProjectId("proj_operations");
            setLoadingProjects(false);
          }
        });

      return () => {
        ignore = true;
        controller.abort();
      };
    }
  }, [isOpen, organizationId, apiBaseUrl]);

  // Automatically slugify name into agentId if not manually edited
  const handleNameChange = (val: string) => {
    setName(val);
    if (!agentIdTouched) {
      const slug = val
        .toLowerCase()
        .replace(/[^a-z0-9\-_]+/g, "-")
        .replace(/^-+|-+$/g, "")
        .slice(0, 60);
      setAgentId(slug);
    }
  };

  const handleClose = () => {
    // Clear sensitive state from memory upon closing
    setSuccessData(null);
    setCopiedSecret(false);
    setShowSecret(false);
    setErrorMessage(null);
    setName("");
    setAgentId("");
    setAgentIdTouched(false);
    setPurpose("");
    setIsSubmitting(false);
    onClose();
  };

  const copyToClipboard = async (text: string) => {
    try {
      await navigator.clipboard.writeText(text);
      setCopiedSecret(true);
      setTimeout(() => setCopiedSecret(false), 3000);
    } catch {
      // Fallback
      setCopiedSecret(false);
    }
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setErrorMessage(null);

    const finalAgentId = agentId.trim().toLowerCase();
    const finalProjectId = isCustomProject ? customProjectId.trim() : projectId.trim();
    const finalOrgId = organizationId.trim();
    const finalOwner = owner.trim();
    const finalName = name.trim();

    // Client-side validations matching backend constraints
    if (!finalName) {
      setErrorMessage("Agent name is required.");
      return;
    }

    if (!finalAgentId || finalAgentId.length < 3) {
      setErrorMessage("Agent ID must be at least 3 characters long.");
      return;
    }

    if (!/^[a-z0-9\-_]+$/.test(finalAgentId)) {
      setErrorMessage("Agent ID may only contain lowercase letters, numbers, hyphens, and underscores.");
      return;
    }

    if (!finalOwner || !finalOwner.includes("@")) {
      setErrorMessage("A valid owner email address is required.");
      return;
    }

    if (!finalProjectId) {
      setErrorMessage("Project is required.");
      return;
    }

    try {
      setIsSubmitting(true);

      // Pre-flight bootstrap: Ensure organization, project, and user exist
      // so foreign key checks on the backend do not fail if setting up a new tenant/project scope.
      try {
        await fetch(`${apiBaseUrl}/api/v1/organizations`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            id: finalOrgId,
            name: finalOrgId,
          }),
        });
      } catch {
        // ignore if exists
      }

      try {
        await fetch(`${apiBaseUrl}/api/v1/users`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            id: `usr_${finalOwner.replace(/[^a-z0-9]/gi, "_").toLowerCase().slice(0, 30)}`,
            email: finalOwner,
            display_name: finalOwner.split("@")[0],
          }),
        });
      } catch {
        // ignore if exists
      }

      try {
        await fetch(`${apiBaseUrl}/api/v1/projects`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            id: finalProjectId,
            organization_id: finalOrgId,
            name: finalProjectId,
          }),
        });
      } catch {
        // ignore if exists
      }

      // 1. Submit to existing Agent Registration API
      const registerRes = await fetch(`${apiBaseUrl}/api/v1/agents`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          "X-User-Email": finalOwner,
        },
        body: JSON.stringify({
          id: finalAgentId,
          organization_id: finalOrgId,
          project_id: finalProjectId,
          name: finalName,
          environment: environment,
          purpose: purpose.trim() || undefined,
        }),
      });

      if (!registerRes.ok) {
        let errText = "Failed to register agent identity.";
        try {
          const errJson = await registerRes.json();
          if (errJson.detail) {
            if (typeof errJson.detail === "string") {
              errText = errJson.detail;
            } else if (Array.isArray(errJson.detail)) {
              errText = errJson.detail
                .map((d: { loc?: (string | number)[]; msg?: string }) => `${d.loc ? d.loc.slice(1).join(".") + ": " : ""}${d.msg || ""}`)
                .join(", ");
            }
          }
        } catch {
          errText = `Registration failed with HTTP ${registerRes.status}: ${registerRes.statusText}`;
        }
        setErrorMessage(errText);
        setIsSubmitting(false);
        return;
      }

      const registeredAgent = await registerRes.json();

      // 2. Issue initial cryptographic credential for the agent
      let issuedCredential: { id: string; plaintext_secret: string } | undefined = undefined;
      try {
        const credRes = await fetch(`${apiBaseUrl}/api/v1/agents/${registeredAgent.id}/credentials`, {
          method: "POST",
          headers: {
            "Content-Type": "application/json",
            "X-User-Email": finalOwner,
          },
        });

        if (credRes.ok) {
          issuedCredential = await credRes.json();
        }
      } catch {
        // credential generation could fail if already generated, still proceed
      }

      // Notify parent to immediately refresh and show newly registered agent
      onAgentRegistered(
        {
          agent_id: registeredAgent.id,
          name: registeredAgent.name,
          organization_id: registeredAgent.organization_id,
          project_id: registeredAgent.project_id,
          environment: registeredAgent.environment,
          status: registeredAgent.status || "active",
          last_activity: null,
          action_count: 0,
        },
        issuedCredential
      );

      // Transition to secure success display
      setSuccessData({
        agent: registeredAgent,
        credential: issuedCredential,
      });
    } catch (err: unknown) {
      const message = err instanceof Error ? err.message : "An unexpected network error occurred.";
      setErrorMessage(message);
    } finally {
      setIsSubmitting(false);
    }
  };

  if (!isOpen) return null;

  return (
    <div
      id="modal-add-agent-backdrop"
      style={{
        position: "fixed",
        top: 0,
        left: 0,
        right: 0,
        bottom: 0,
        backgroundColor: "rgba(13, 17, 23, 0.85)",
        display: "flex",
        alignItems: "center",
        justifyContent: "center",
        zIndex: 1000,
        padding: "16px",
      }}
      onClick={handleClose}
    >
      <div
        id="modal-add-agent-content"
        style={{
          width: "100%",
          maxWidth: "620px",
          maxHeight: "90vh",
          overflowY: "auto",
          background: "var(--panel-bg)",
          border: "1px solid var(--border-rule)",
          borderRadius: "4px",
          padding: "20px 24px",
          boxShadow: "0 12px 28px rgba(0,0,0,0.6)",
          display: "flex",
          flexDirection: "column",
          gap: "16px",
        }}
        onClick={(e) => e.stopPropagation()}
      >
        {/* Modal Header */}
        <div
          style={{
            display: "flex",
            alignItems: "center",
            justifyContent: "space-between",
            borderBottom: "1px solid var(--border-rule)",
            paddingBottom: "12px",
          }}
        >
          <div style={{ display: "flex", alignItems: "center", gap: "10px" }}>
            <div
              style={{
                width: "32px",
                height: "32px",
                borderRadius: "3px",
                background: "var(--surface-plate)",
                border: "1px solid var(--border-rule)",
                display: "flex",
                alignItems: "center",
                justifyContent: "center",
                fontSize: "1rem",
              }}
            >
              🤖
            </div>
            <div>
              <h2 style={{ fontSize: "1rem", fontWeight: 600, color: "var(--text-primary)" }}>
                {successData ? "Agent Identity Provisioned" : "Register Autonomous Agent"}
              </h2>
              <div style={{ fontSize: "0.75rem", color: "var(--text-muted)", maxWidth: "55ch" }}>
                {successData
                  ? "Identity verified with secure cryptographic credentials"
                  : "Onboard a new autonomous identity into runtime security mediation"}
              </div>
            </div>
          </div>
          <button
            id="btn-close-modal"
            className="btn btn-ghost"
            onClick={handleClose}
            style={{ fontSize: "0.85rem", padding: "4px 8px" }}
            aria-label="Close"
          >
            ✕
          </button>
        </div>

        {/* Error Banner */}
        {errorMessage && (
          <div
            id="add-agent-error-alert"
            style={{
              padding: "10px 14px",
              borderRadius: "3px",
              background: "var(--status-block-bg)",
              border: "1px solid var(--status-block-border)",
              color: "#FFA198",
              fontSize: "0.8125rem",
              display: "flex",
              alignItems: "flex-start",
              gap: "8px",
            }}
          >
            <span style={{ fontSize: "0.9rem" }}>■</span>
            <div style={{ flex: 1, lineHeight: "1.4" }}>{errorMessage}</div>
          </div>
        )}

        {/* View 1: Secure Credential Display (Success State) */}
        {successData ? (
          <div style={{ display: "flex", flexDirection: "column", gap: "16px" }}>
            {/* Success summary pill */}
            <div
              style={{
                padding: "12px 14px",
                background: "var(--status-allow-bg)",
                border: "1px solid var(--status-allow-border)",
                borderRadius: "3px",
                display: "flex",
                alignItems: "center",
                gap: "10px",
              }}
            >
              <span style={{ fontSize: "1.1rem" }}>✅</span>
              <div>
                <div style={{ fontWeight: 600, color: "var(--status-allow-fg)", fontSize: "0.875rem" }}>
                  Agent Identity Successfully Registered
                </div>
                <div style={{ fontSize: "0.75rem", color: "var(--text-secondary)", marginTop: "2px" }}>
                  <span style={{ fontWeight: 500, color: "var(--text-primary)" }}>{successData.agent.name}</span> (
                  <code className="code-pill">{successData.agent.id}</code>) is now actively monitored.
                </div>
              </div>
            </div>

            {/* Agent Metadata Card */}
            <div
              style={{
                display: "grid",
                gridTemplateColumns: "repeat(auto-fit, minmax(130px, 1fr))",
                gap: "8px",
                background: "var(--surface-plate)",
                padding: "12px",
                borderRadius: "3px",
                border: "1px solid var(--border-rule)",
              }}
            >
              <div>
                <div style={{ fontSize: "0.6875rem", color: "var(--text-muted)", fontFamily: "var(--font-mono)" }}>TENANT</div>
                <div style={{ fontSize: "0.8125rem", color: "var(--text-primary)", fontWeight: 500, fontFamily: "var(--font-mono)" }}>
                  {successData.agent.organization_id}
                </div>
              </div>
              <div>
                <div style={{ fontSize: "0.6875rem", color: "var(--text-muted)", fontFamily: "var(--font-mono)" }}>PROJECT</div>
                <div style={{ fontSize: "0.8125rem", color: "var(--text-primary)", fontWeight: 500, fontFamily: "var(--font-mono)" }}>
                  {successData.agent.project_id}
                </div>
              </div>
              <div>
                <div style={{ fontSize: "0.6875rem", color: "var(--text-muted)", fontFamily: "var(--font-mono)" }}>ENVIRONMENT</div>
                <div style={{ fontSize: "0.8125rem", color: "#79C0FF", fontWeight: 600, textTransform: "uppercase" }}>
                  {successData.agent.environment}
                </div>
              </div>
              <div>
                <div style={{ fontSize: "0.6875rem", color: "var(--text-muted)", fontFamily: "var(--font-mono)" }}>OWNER</div>
                <div style={{ fontSize: "0.8125rem", color: "var(--text-primary)", fontWeight: 500 }}>
                  {successData.agent.owner}
                </div>
              </div>
            </div>

            {/* Generated Credential Section */}
            {successData.credential ? (
              <div
                style={{
                  display: "flex",
                  flexDirection: "column",
                  gap: "10px",
                  background: "var(--surface-plate)",
                  border: "1px solid var(--border-rule)",
                  borderRadius: "3px",
                  padding: "14px",
                }}
              >
                <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between" }}>
                  <div style={{ display: "flex", alignItems: "center", gap: "6px" }}>
                    <span style={{ fontSize: "0.95rem" }}>🔑</span>
                    <span style={{ fontWeight: 600, color: "var(--text-primary)", fontSize: "0.8125rem" }}>
                      Cryptographic Runtime Secret
                    </span>
                  </div>
                  <span className="code-pill" style={{ fontSize: "0.7rem", color: "var(--text-muted)" }}>
                    {successData.credential.id}
                  </span>
                </div>

                {/* Secret Display Box */}
                <div
                  style={{
                    display: "flex",
                    alignItems: "center",
                    gap: "8px",
                    background: "#090D13",
                    border: "1px solid var(--border-rule)",
                    borderRadius: "3px",
                    padding: "6px 10px",
                  }}
                >
                  <input
                    id="input-agent-credential-secret"
                    type={showSecret ? "text" : "password"}
                    readOnly
                    value={successData.credential.plaintext_secret}
                    style={{
                      flex: 1,
                      background: "transparent",
                      border: "none",
                      color: "#FFFFFF",
                      fontFamily: "var(--font-mono)",
                      fontSize: "0.8125rem",
                      letterSpacing: showSecret ? "normal" : "0.12em",
                      outline: "none",
                    }}
                  />
                  <button
                    type="button"
                    className="btn btn-ghost"
                    onClick={() => setShowSecret(!showSecret)}
                    style={{ padding: "3px 8px", fontSize: "0.72rem" }}
                    title={showSecret ? "Hide Secret" : "Show Secret"}
                  >
                    {showSecret ? "Hide" : "Show"}
                  </button>
                  <button
                    id="btn-copy-secret"
                    type="button"
                    className="btn btn-primary"
                    onClick={() => copyToClipboard(successData.credential!.plaintext_secret)}
                    style={{ padding: "4px 10px", fontSize: "0.72rem" }}
                  >
                    {copiedSecret ? "Copied" : "Copy"}
                  </button>
                </div>

                {/* Warning callout */}
                <div
                  id="credential-security-warning"
                  style={{
                    padding: "8px 10px",
                    background: "var(--status-approval-bg)",
                    border: "1px solid var(--status-approval-border)",
                    borderRadius: "3px",
                    fontSize: "0.75rem",
                    color: "var(--status-approval-fg)",
                    lineHeight: "1.4",
                    display: "flex",
                    alignItems: "flex-start",
                    gap: "6px",
                  }}
                >
                  <span>■</span>
                  <span>
                    <strong>Save this secret immediately:</strong> This cryptographic credential is generated once and cannot be retrieved again. If lost, you must revoke this credential and generate a replacement.
                  </span>
                </div>
              </div>
            ) : (
              <div style={{ fontSize: "0.75rem", color: "var(--text-muted)", padding: "8px" }}>
                Identity registered. Issue credentials at any time from the agent details panel.
              </div>
            )}

            {/* Modal Actions */}
            <div style={{ display: "flex", justifyContent: "flex-end", gap: "8px", marginTop: "8px" }}>
              <button
                id="btn-done-modal"
                className="btn btn-primary"
                onClick={handleClose}
                style={{ padding: "6px 20px", fontSize: "0.8125rem" }}
              >
                Done
              </button>
            </div>
          </div>
        ) : (
          /* View 2: Registration Form */
          <form onSubmit={handleSubmit} style={{ display: "flex", flexDirection: "column", gap: "12px" }}>
            {/* Scope Row: Organization & Project */}
            <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "12px" }}>
              {/* Organization / Tenant */}
              <div>
                <label
                  htmlFor="agent-org-id"
                  style={{ display: "block", fontSize: "0.75rem", fontWeight: 600, color: "var(--text-secondary)", marginBottom: "4px", fontFamily: "var(--font-mono)" }}
                >
                  ORGANIZATION / TENANT *
                </label>
                <input
                  id="agent-org-id"
                  type="text"
                  required
                  value={organizationId}
                  onChange={(e) => setOrganizationId(e.target.value)}
                  placeholder="e.g. org_enterprise"
                  style={{
                    width: "100%",
                    background: "#090D13",
                    border: "1px solid var(--border-rule)",
                    borderRadius: "3px",
                    padding: "6px 10px",
                    color: "var(--text-primary)",
                    fontFamily: "var(--font-mono)",
                    fontSize: "0.8125rem",
                    outline: "none",
                  }}
                />
              </div>

              {/* Project */}
              <div>
                <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "4px" }}>
                  <label
                    htmlFor={isCustomProject ? "agent-custom-project-id" : "agent-project-id"}
                    style={{ fontSize: "0.75rem", fontWeight: 600, color: "var(--text-secondary)", fontFamily: "var(--font-mono)" }}
                  >
                    PROJECT SCOPE *
                  </label>
                  {availableProjects.length > 0 && (
                    <button
                      type="button"
                      onClick={() => setIsCustomProject(!isCustomProject)}
                      style={{
                        background: "none",
                        border: "none",
                        color: "var(--accent-telegraph)",
                        fontSize: "0.7rem",
                        cursor: "pointer",
                        textDecoration: "underline",
                      }}
                    >
                      {isCustomProject ? "Select existing" : "+ New project ID"}
                    </button>
                  )}
                </div>

                {isCustomProject || availableProjects.length === 0 ? (
                  <input
                    id="agent-custom-project-id"
                    type="text"
                    required
                    value={customProjectId}
                    onChange={(e) => setCustomProjectId(e.target.value)}
                    placeholder="e.g. proj_operations"
                    style={{
                      width: "100%",
                      background: "#090D13",
                      border: "1px solid var(--border-rule)",
                      borderRadius: "3px",
                      padding: "6px 10px",
                      color: "var(--text-primary)",
                      fontFamily: "var(--font-mono)",
                      fontSize: "0.8125rem",
                      outline: "none",
                    }}
                  />
                ) : (
                  <select
                    id="agent-project-id"
                    value={projectId}
                    onChange={(e) => setProjectId(e.target.value)}
                    disabled={loadingProjects}
                    style={{
                      width: "100%",
                      background: "#090D13",
                      border: "1px solid var(--border-rule)",
                      borderRadius: "3px",
                      padding: "6px 10px",
                      color: "var(--text-primary)",
                      fontFamily: "var(--font-mono)",
                      fontSize: "0.8125rem",
                      outline: "none",
                      cursor: "pointer",
                    }}
                  >
                    {availableProjects.map((p) => (
                      <option key={p.id} value={p.id}>
                        {p.name} ({p.id})
                      </option>
                    ))}
                  </select>
                )}
              </div>
            </div>

            {/* Agent Name */}
            <div>
              <label
                htmlFor="agent-name-input"
                style={{ display: "block", fontSize: "0.75rem", fontWeight: 600, color: "var(--text-secondary)", marginBottom: "4px" }}
              >
                Agent Name *
              </label>
              <input
                id="agent-name-input"
                type="text"
                required
                maxLength={128}
                value={name}
                onChange={(e) => handleNameChange(e.target.value)}
                placeholder="e.g., Finance Reconciliation Agent"
                style={{
                  width: "100%",
                  background: "#090D13",
                  border: "1px solid var(--border-rule)",
                  borderRadius: "3px",
                  padding: "6px 10px",
                  color: "var(--text-primary)",
                  fontSize: "0.8125rem",
                  outline: "none",
                }}
              />
            </div>

            {/* Agent Machine ID */}
            <div>
              <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "4px" }}>
                <label
                  htmlFor="agent-id-input"
                  style={{ fontSize: "0.75rem", fontWeight: 600, color: "var(--text-secondary)", fontFamily: "var(--font-mono)" }}
                >
                  AGENT MACHINE IDENTIFIER *
                </label>
                <span style={{ fontSize: "0.6875rem", color: "var(--text-muted)" }}>
                  Lowercase alphanumeric, hyphens
                </span>
              </div>
              <input
                id="agent-id-input"
                type="text"
                required
                minLength={3}
                maxLength={64}
                value={agentId}
                onChange={(e) => {
                  setAgentIdTouched(true);
                  setAgentId(e.target.value.toLowerCase());
                }}
                placeholder="e.g., finance-reconciliation-agent"
                style={{
                  width: "100%",
                  background: "#090D13",
                  border: "1px solid var(--border-rule)",
                  borderRadius: "3px",
                  padding: "6px 10px",
                  color: "#79C0FF",
                  fontFamily: "var(--font-mono)",
                  fontSize: "0.8125rem",
                  outline: "none",
                }}
              />
            </div>

            {/* Owner Email & Environment Row */}
            <div style={{ display: "grid", gridTemplateColumns: "1.2fr 1fr", gap: "12px" }}>
              {/* Owner */}
              <div>
                <label
                  htmlFor="agent-owner-input"
                  style={{ display: "block", fontSize: "0.75rem", fontWeight: 600, color: "var(--text-secondary)", marginBottom: "4px" }}
                >
                  Owner (Security Officer) *
                </label>
                <input
                  id="agent-owner-input"
                  type="email"
                  required
                  value={owner}
                  onChange={(e) => setOwner(e.target.value)}
                  placeholder="e.g. security_admin@enterprise.internal"
                  style={{
                    width: "100%",
                    background: "#090D13",
                    border: "1px solid var(--border-rule)",
                    borderRadius: "3px",
                    padding: "6px 10px",
                    color: "var(--text-primary)",
                    fontSize: "0.8125rem",
                    outline: "none",
                  }}
                />
              </div>

              {/* Environment */}
              <div>
                <label
                  htmlFor="agent-environment-select"
                  style={{ display: "block", fontSize: "0.75rem", fontWeight: 600, color: "var(--text-secondary)", marginBottom: "4px" }}
                >
                  Environment *
                </label>
                <select
                  id="agent-environment-select"
                  value={environment}
                  onChange={(e) => setEnvironment(e.target.value)}
                  style={{
                    width: "100%",
                    background: "#090D13",
                    border: "1px solid var(--border-rule)",
                    borderRadius: "3px",
                    padding: "6px 10px",
                    color: "var(--text-primary)",
                    fontSize: "0.8125rem",
                    outline: "none",
                    cursor: "pointer",
                  }}
                >
                  <option value="development">Development (dev)</option>
                  <option value="staging">Staging (staging)</option>
                  <option value="production">Production (prod)</option>
                </select>
              </div>
            </div>

            {/* Purpose */}
            <div>
              <label
                htmlFor="agent-purpose-input"
                style={{ display: "block", fontSize: "0.75rem", fontWeight: 600, color: "var(--text-secondary)", marginBottom: "4px" }}
              >
                Capability & Scope Mandate
              </label>
              <textarea
                id="agent-purpose-input"
                rows={3}
                maxLength={512}
                value={purpose}
                onChange={(e) => setPurpose(e.target.value)}
                placeholder="Describe operational mandate and allowed tools..."
                style={{
                  width: "100%",
                  background: "#090D13",
                  border: "1px solid var(--border-rule)",
                  borderRadius: "3px",
                  padding: "6px 10px",
                  color: "var(--text-primary)",
                  fontSize: "0.8125rem",
                  resize: "vertical",
                  outline: "none",
                  fontFamily: "var(--font-family)",
                }}
              />
            </div>

            {/* Form Action Buttons */}
            <div
              style={{
                display: "flex",
                justifyContent: "flex-end",
                alignItems: "center",
                gap: "10px",
                borderTop: "1px solid var(--border-rule)",
                paddingTop: "12px",
                marginTop: "4px",
              }}
            >
              <button
                type="button"
                className="btn btn-ghost"
                onClick={handleClose}
                disabled={isSubmitting}
                style={{ fontSize: "0.8125rem" }}
              >
                Cancel
              </button>
              <button
                id="btn-submit-add-agent"
                type="submit"
                className="btn btn-primary"
                disabled={isSubmitting}
                style={{ fontSize: "0.8125rem", padding: "6px 16px" }}
              >
                {isSubmitting ? "Registering Agent..." : "+ Register & Issue Credentials"}
              </button>
            </div>
          </form>
        )}
      </div>
    </div>
  );
};
