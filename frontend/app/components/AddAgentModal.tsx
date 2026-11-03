"use client";

import React, { useState, useEffect } from "react";
import { getAdminHeaders } from "../../lib/auth";

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

interface OrgOption {
  id: string;
  name: string;
  status?: string;
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
  const [isCustomOrg, setIsCustomOrg] = useState(false);
  const [projectId, setProjectId] = useState("proj_operations");
  const [isCustomProject, setIsCustomProject] = useState(false);
  const [customProjectId, setCustomProjectId] = useState("");

  // External Agent & LLM Provider Fields
  const [framework, setFramework] = useState("custom");
  const [llmProvider, setLlmProvider] = useState("openai");
  const [defaultModel, setDefaultModel] = useState("gpt-4o-mini");
  const [providerApiKey, setProviderApiKey] = useState("");

  // Organizations & Projects lists
  const [availableOrgs, setAvailableOrgs] = useState<OrgOption[]>([]);
  const [loadingOrgs, setLoadingOrgs] = useState(false);
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
      framework?: string;
      llm_provider?: string;
      default_model?: string;
      provider_key_configured?: boolean;
      key_fingerprint?: string | null;
    };
    credential?: {
      id: string;
      plaintext_secret: string;
    };
  } | null>(null);

  const [copiedSecret, setCopiedSecret] = useState(false);
  const [showSecret, setShowSecret] = useState(false);
  const [activeSnippetTab, setActiveSnippetTab] = useState<"python" | "langgraph" | "crewai" | "autogen" | "openhands">("python");

  // Sync organization when currentTenant changes without triggering cascading renders
  const [prevTenant, setPrevTenant] = useState(currentTenant);
  if (currentTenant !== prevTenant) {
    setPrevTenant(currentTenant);
    setOrganizationId(currentTenant);
  }

  // Load existing organizations when modal opens
  useEffect(() => {
    let ignore = false;
    if (!isOpen) return;

    const loadOrgs = async () => {
      try {
        setLoadingOrgs(true);
        const res = await fetch(`${apiBaseUrl}/api/v1/organizations`, {
          headers: { ...getAdminHeaders() },
        });
        if (res.ok) {
          const data: OrgOption[] = await res.json();
          if (!ignore) {
            setAvailableOrgs(data);
            if (data.length > 0 && !data.some((o) => o.id === organizationId)) {
              setOrganizationId(data[0].id);
            }
          }
        }
      } catch (err) {
        console.error("Failed to load organizations:", err);
      } finally {
        if (!ignore) setLoadingOrgs(false);
      }
    };

    loadOrgs();
    return () => {
      ignore = true;
    };
  }, [isOpen, apiBaseUrl]);

  // Load projects whenever selected organization changes
  useEffect(() => {
    let ignore = false;
    if (!isOpen || !organizationId || isCustomOrg) return;

    const loadProjects = async () => {
      try {
        setLoadingProjects(true);
        const res = await fetch(`${apiBaseUrl}/api/v1/projects?organization_id=${organizationId}`, {
          headers: { ...getAdminHeaders() },
        });
        if (res.ok) {
          const data: ProjectOption[] = await res.json();
          if (!ignore) {
            setAvailableProjects(data);
            if (data.length > 0) {
              setProjectId(data[0].id);
              setIsCustomProject(false);
            } else {
              setIsCustomProject(true);
              setCustomProjectId("proj_default");
            }
          }
        }
      } catch (err) {
        console.error("Failed to load projects:", err);
      } finally {
        if (!ignore) setLoadingProjects(false);
      }
    };

    loadProjects();
    return () => {
      ignore = true;
    };
  }, [isOpen, organizationId, isCustomOrg, apiBaseUrl]);

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
    setSuccessData(null);
    setCopiedSecret(false);
    setShowSecret(false);
    setErrorMessage(null);
    setName("");
    setAgentId("");
    setAgentIdTouched(false);
    setPurpose("");
    setProviderApiKey("");
    setIsSubmitting(false);
    onClose();
  };

  const copyToClipboard = async (text: string) => {
    try {
      await navigator.clipboard.writeText(text);
      setCopiedSecret(true);
      setTimeout(() => setCopiedSecret(false), 3000);
    } catch {
      setCopiedSecret(false);
    }
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setErrorMessage(null);

    const finalAgentId = agentId.trim().toLowerCase();
    const finalProjectId = (isCustomProject ? customProjectId : projectId).trim().toLowerCase();
    const finalOrgId = organizationId.trim().toLowerCase();
    const finalOwner = owner.trim();
    const finalName = name.trim();

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

    if (!finalOrgId || finalOrgId.length < 3) {
      setErrorMessage("Organization / Tenant ID must be at least 3 characters long.");
      return;
    }

    if (!/^[a-z0-9\-_]+$/.test(finalOrgId)) {
      setErrorMessage("Organization / Tenant ID may only contain lowercase alphanumeric characters, hyphens, and underscores.");
      return;
    }

    if (!finalProjectId || finalProjectId.length < 3) {
      setErrorMessage("Project Scope ID must be at least 3 characters long.");
      return;
    }

    if (!/^[a-z0-9\-_]+$/.test(finalProjectId)) {
      setErrorMessage("Project Scope ID may only contain lowercase alphanumeric characters, hyphens, and underscores.");
      return;
    }

    if (!finalOwner || !finalOwner.includes("@")) {
      setErrorMessage("A valid owner email address is required.");
      return;
    }

    try {
      setIsSubmitting(true);

      // Pre-flight bootstrap: Check if organization exists
      const orgAlreadyExists = availableOrgs.some((o) => o.id === finalOrgId);
      if (!orgAlreadyExists) {
        try {
          await fetch(`${apiBaseUrl}/api/v1/organizations`, {
            method: "POST",
            headers: { "Content-Type": "application/json", ...getAdminHeaders() },
            body: JSON.stringify({
              id: finalOrgId,
              name: finalOrgId.replace(/[-_]/g, " ").replace(/\b\w/g, (c) => c.toUpperCase()),
            }),
          });
        } catch {
          // ignore
        }
      }

      // Resolve user id
      let resolvedUserId = "usr_admin";
      try {
        const usersRes = await fetch(`${apiBaseUrl}/api/v1/users`, {
          headers: { ...getAdminHeaders() },
        });
        if (usersRes.ok) {
          const usersList: { id: string; email: string }[] = await usersRes.json();
          const matchUser = usersList.find((u) => u.email.toLowerCase() === finalOwner.toLowerCase());
          if (matchUser) {
            resolvedUserId = matchUser.id;
          } else {
            resolvedUserId = `usr_${finalOwner.replace(/[^a-z0-9]/gi, "_").toLowerCase().slice(0, 30)}`;
            await fetch(`${apiBaseUrl}/api/v1/users`, {
              method: "POST",
              headers: { "Content-Type": "application/json", ...getAdminHeaders() },
              body: JSON.stringify({
                id: resolvedUserId,
                email: finalOwner,
                display_name: finalOwner.split("@")[0],
              }),
            });
          }
        }
      } catch {
        // fallback
      }

      // Ensure membership exists
      try {
        await fetch(`${apiBaseUrl}/api/v1/users/memberships`, {
          method: "POST",
          headers: { "Content-Type": "application/json", ...getAdminHeaders() },
          body: JSON.stringify({
            id: `mem_${finalOrgId.slice(0, 16)}_${resolvedUserId.slice(0, 16)}`,
            user_id: resolvedUserId,
            organization_id: finalOrgId,
            role: "administrator",
          }),
        });
      } catch {
        // ignore
      }

      // Check if project exists
      const projAlreadyExists = availableProjects.some((p) => p.id === finalProjectId);
      if (!projAlreadyExists) {
        try {
          await fetch(`${apiBaseUrl}/api/v1/projects`, {
            method: "POST",
            headers: { "Content-Type": "application/json", ...getAdminHeaders() },
            body: JSON.stringify({
              id: finalProjectId,
              organization_id: finalOrgId,
              name: finalProjectId,
            }),
          });
        } catch {
          // ignore
        }
      }

      // 1. Submit to Agent Registration API with Framework & Provider Vault Key
      const registerRes = await fetch(`${apiBaseUrl}/api/v1/agents`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          ...getAdminHeaders(),
          "X-Organization-Id": finalOrgId,
          "X-User-Email": finalOwner,
        },
        body: JSON.stringify({
          id: finalAgentId,
          organization_id: finalOrgId,
          project_id: finalProjectId,
          name: finalName,
          environment: environment,
          purpose: purpose.trim() || undefined,
          framework: framework,
          llm_provider: llmProvider,
          default_model: defaultModel,
          provider_api_key: providerApiKey.trim() || undefined,
        }),
      });

      if (!registerRes.ok) {
        let errText = "Failed to register agent identity.";
        try {
          const errJson = await registerRes.json();
          if (errJson.error && errJson.error.message) {
            errText = errJson.error.message;
          } else if (errJson.detail) {
            errText = typeof errJson.detail === "string" ? errJson.detail : JSON.stringify(errJson.detail);
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
            "X-Organization-Id": finalOrgId,
            "X-User-Email": finalOwner,
          },
        });

        if (credRes.ok) {
          issuedCredential = await credRes.json();
        }
      } catch {
        // proceed
      }

      // Notify parent to refresh list
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
      // Clear sensitive provider key from form state memory immediately
      setProviderApiKey("");
    } catch (err: unknown) {
      const message = err instanceof Error ? err.message : "An unexpected network error occurred.";
      setErrorMessage(message);
    } finally {
      setIsSubmitting(false);
    }
  };

  if (!isOpen) return null;

  const gatewayUrl = typeof window !== "undefined" ? `${window.location.protocol}//${window.location.hostname}:8000` : "http://127.0.0.1:8000";
  const proxyUrl = `${gatewayUrl}/api/v1/proxy/v1`;

  const getSnippetContent = (tab: string) => {
    const tokenDisplay = successData?.credential ? successData.credential.plaintext_secret : "<YOUR_AGENT_BEARER_TOKEN>";
    const modelDisplay = successData?.agent.default_model || defaultModel || "gpt-4o-mini";

    if (tab === "python") {
      return `from openai import OpenAI

# The external agent holds ONLY its governance bearer token (${tokenDisplay.slice(0, 8)}...)
# The real provider API key resides securely inside the gateway vault!
client = OpenAI(
    base_url="${proxyUrl}",
    api_key="${tokenDisplay}"
)

response = client.chat.completions.create(
    model="${modelDisplay}",
    messages=[
        {"role": "user", "content": "Explain what an autonomous agent is."}
    ]
)
print(response.choices[0].message.content)`;
    }
    if (tab === "langgraph") {
      return `from langchain_openai import ChatOpenAI

llm = ChatOpenAI(
    base_url="${proxyUrl}",
    api_key="${tokenDisplay}",
    model="${modelDisplay}",
)
response = llm.invoke("Summarize policy status.")
print(response.content)`;
    }
    if (tab === "crewai") {
      return `from crewai import Agent, Crew, Task
from governance_sdk.client import GovernanceClient
from governance_sdk.adapters.crewai import CrewAIGovernanceHook

gov_client = GovernanceClient(
    base_url="${proxyUrl}",
    agent_token="${tokenDisplay}",
)

# Intercept and govern all CrewAI tool executions
with CrewAIGovernanceHook(client=gov_client) as hook:
    # Autonomous agent crew executions are deterministically mediated
    crew.kickoff()`;
    }
    if (tab === "autogen") {
      return `config_list = [
    {
        "model": "${modelDisplay}",
        "base_url": "${proxyUrl}",
        "api_key": "${tokenDisplay}",
    }
]`;
    }
    return `# In external/OpenHands/.env:
OPENAI_BASE_URL=${proxyUrl}
OPENAI_API_KEY=${tokenDisplay}
LLM_MODEL=${modelDisplay}`;
  };

  return (
    <div
      id="modal-add-agent-backdrop"
      style={{
        position: "fixed",
        top: 0,
        left: 0,
        right: 0,
        bottom: 0,
        background: "rgba(10, 15, 25, 0.75)",
        backdropFilter: "blur(4px)",
        display: "flex",
        alignItems: "center",
        justifyContent: "center",
        zIndex: 9999,
        padding: "16px",
      }}
    >
      <div
        id="modal-add-agent-container"
        style={{
          background: "#ffffff",
          border: "1px solid #cbd5e1",
          borderRadius: "8px",
          width: "100%",
          maxWidth: "680px",
          maxHeight: "90vh",
          overflowY: "auto",
          padding: "24px",
          display: "flex",
          flexDirection: "column",
          gap: "18px",
          boxShadow: "0 20px 25px -5px rgba(0, 0, 0, 0.1), 0 10px 10px -5px rgba(0, 0, 0, 0.04)",
          color: "#0f172a",
        }}
      >
        {/* Modal Header */}
        <div
          style={{
            display: "flex",
            alignItems: "center",
            justifyContent: "space-between",
            borderBottom: "1px solid #e2e8f0",
            paddingBottom: "12px",
          }}
        >
          <div style={{ display: "flex", alignItems: "center", gap: "10px" }}>
            <div
              style={{
                width: "36px",
                height: "36px",
                borderRadius: "8px",
                background: "#f1f5f9",
                border: "1px solid #cbd5e1",
                display: "flex",
                alignItems: "center",
                justifyContent: "center",
                fontSize: "1.2rem",
              }}
            >
              🤖
            </div>
            <div>
              <h2 style={{ fontSize: "1.05rem", fontWeight: 700, color: "#0f172a" }}>
                {successData ? "External Agent Integrated" : "Register External AI Agent"}
              </h2>
              <div style={{ fontSize: "0.78rem", color: "#64748b" }}>
                {successData
                  ? "Identity verified & provider credentials vaulted securely"
                  : "Connect OpenHands, LangGraph, CrewAI, AutoGen, or custom Python agents"}
              </div>
            </div>
          </div>
          <button
            id="btn-close-modal"
            onClick={handleClose}
            style={{
              background: "none",
              border: "none",
              fontSize: "1.1rem",
              cursor: "pointer",
              color: "#64748b",
              padding: "4px 8px",
            }}
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
              borderRadius: "6px",
              background: "#fef2f2",
              border: "1px solid #f87171",
              color: "#991b1b",
              fontSize: "0.8125rem",
              display: "flex",
              alignItems: "flex-start",
              gap: "8px",
            }}
          >
            <span>⚠️</span>
            <div style={{ flex: 1, lineHeight: "1.4" }}>{errorMessage}</div>
          </div>
        )}

        {/* VIEW 1: SUCCESS & INTEGRATION INSTRUCTIONS */}
        {successData ? (
          <div style={{ display: "flex", flexDirection: "column", gap: "16px" }}>
            {/* Success summary pill */}
            <div
              style={{
                padding: "12px 14px",
                background: "#f0fdf4",
                border: "1px solid #86efac",
                borderRadius: "6px",
                display: "flex",
                alignItems: "center",
                gap: "10px",
              }}
            >
              <span style={{ fontSize: "1.2rem" }}>✅</span>
              <div>
                <div style={{ fontWeight: 700, color: "#166534", fontSize: "0.875rem" }}>
                  External Agent Successfully Registered & Vaulted
                </div>
                <div style={{ fontSize: "0.75rem", color: "#374151", marginTop: "2px" }}>
                  <span style={{ fontWeight: 600 }}>{successData.agent.name}</span> (
                  <code style={{ background: "#e2e8f0", padding: "1px 5px", borderRadius: "3px", fontFamily: "var(--font-mono)" }}>
                    {successData.agent.id}
                  </code>
                  ) is governed under {successData.agent.organization_id}.
                </div>
              </div>
            </div>

            {/* Endpoints & Vault Status */}
            <div
              style={{
                display: "grid",
                gridTemplateColumns: "1fr 1fr",
                gap: "10px",
                background: "#f8fafc",
                border: "1px solid #e2e8f0",
                borderRadius: "6px",
                padding: "12px",
              }}
            >
              <div>
                <div style={{ fontSize: "0.7rem", color: "#64748b", fontWeight: 600 }}>LLM GOVERNANCE PROXY URL</div>
                <code style={{ fontSize: "0.75rem", color: "#0f172a", fontFamily: "var(--font-mono)", wordBreak: "break-all" }}>
                  {proxyUrl}
                </code>
              </div>
              <div>
                <div style={{ fontSize: "0.7rem", color: "#64748b", fontWeight: 600 }}>PROVIDER VAULT STATUS</div>
                <div style={{ fontSize: "0.75rem", color: "#15803d", fontWeight: 600 }}>
                  {successData.agent.provider_key_configured ? "🔒 AES-256-GCM Encrypted in Vault" : "ℹ️ No Upstream Key Vaulted"}
                </div>
              </div>
            </div>

            {/* Generated Runtime Secret */}
            {successData.credential && (
              <div
                style={{
                  display: "flex",
                  flexDirection: "column",
                  gap: "8px",
                  background: "#0f172a",
                  border: "1px solid #334155",
                  borderRadius: "6px",
                  padding: "14px",
                  color: "#ffffff",
                }}
              >
                <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between" }}>
                  <div style={{ display: "flex", alignItems: "center", gap: "6px" }}>
                    <span>🔑</span>
                    <span style={{ fontWeight: 600, fontSize: "0.8125rem" }}>Agent Runtime Bearer Token</span>
                  </div>
                  <span style={{ fontSize: "0.7rem", color: "#94a3b8", fontFamily: "var(--font-mono)" }}>
                    {successData.credential.id}
                  </span>
                </div>

                <div style={{ display: "flex", alignItems: "center", gap: "8px" }}>
                  <input
                    type={showSecret ? "text" : "password"}
                    readOnly
                    value={successData.credential.plaintext_secret}
                    style={{
                      flex: 1,
                      background: "#1e293b",
                      border: "1px solid #475569",
                      borderRadius: "4px",
                      padding: "6px 10px",
                      color: "#38bdf8",
                      fontFamily: "var(--font-mono)",
                      fontSize: "0.8125rem",
                      outline: "none",
                    }}
                  />
                  <button
                    type="button"
                    onClick={() => setShowSecret(!showSecret)}
                    style={{
                      background: "#334155",
                      border: "none",
                      color: "#ffffff",
                      padding: "6px 10px",
                      borderRadius: "4px",
                      fontSize: "0.75rem",
                      cursor: "pointer",
                    }}
                  >
                    {showSecret ? "Hide" : "Show"}
                  </button>
                  <button
                    type="button"
                    onClick={() => copyToClipboard(successData.credential!.plaintext_secret)}
                    style={{
                      background: "#2563eb",
                      border: "none",
                      color: "#ffffff",
                      padding: "6px 14px",
                      borderRadius: "4px",
                      fontSize: "0.75rem",
                      fontWeight: 600,
                      cursor: "pointer",
                    }}
                  >
                    {copiedSecret ? "Copied!" : "Copy"}
                  </button>
                </div>
                <div style={{ fontSize: "0.72rem", color: "#fbbf24" }}>
                  ⚠️ Save this token now. It will never be displayed in plaintext again.
                </div>
              </div>
            )}

            {/* Framework Integration Instructions */}
            <div>
              <div style={{ fontSize: "0.75rem", fontWeight: 700, color: "#334155", marginBottom: "6px" }}>
                CONNECT YOUR AGENT FRAMEWORK
              </div>
              <div style={{ display: "flex", gap: "6px", marginBottom: "8px" }}>
                {[
                  { id: "python", label: "OpenAI / Python SDK" },
                  { id: "langgraph", label: "LangGraph" },
                  { id: "crewai", label: "CrewAI" },
                  { id: "autogen", label: "AutoGen" },
                  { id: "openhands", label: "OpenHands" },
                ].map((t) => (
                  <button
                    key={t.id}
                    type="button"
                    onClick={() => setActiveSnippetTab(t.id as any)}
                    style={{
                      padding: "4px 10px",
                      borderRadius: "4px",
                      fontSize: "0.72rem",
                      fontWeight: 600,
                      border: "1px solid",
                      borderColor: activeSnippetTab === t.id ? "#2563eb" : "#cbd5e1",
                      background: activeSnippetTab === t.id ? "#eff6ff" : "#ffffff",
                      color: activeSnippetTab === t.id ? "#1d4ed8" : "#475569",
                      cursor: "pointer",
                    }}
                  >
                    {t.label}
                  </button>
                ))}
              </div>

              <div style={{ position: "relative" }}>
                <pre
                  style={{
                    background: "#0f172a",
                    color: "#f8fafc",
                    padding: "12px",
                    borderRadius: "6px",
                    fontSize: "0.75rem",
                    fontFamily: "var(--font-mono)",
                    overflowX: "auto",
                    whiteSpace: "pre-wrap",
                    margin: 0,
                  }}
                >
                  {getSnippetContent(activeSnippetTab)}
                </pre>
                <button
                  type="button"
                  onClick={() => copyToClipboard(getSnippetContent(activeSnippetTab))}
                  style={{
                    position: "absolute",
                    top: "8px",
                    right: "8px",
                    background: "#334155",
                    border: "none",
                    color: "#ffffff",
                    fontSize: "0.7rem",
                    padding: "3px 8px",
                    borderRadius: "4px",
                    cursor: "pointer",
                  }}
                >
                  Copy Snippet
                </button>
              </div>
            </div>

            <div style={{ display: "flex", justifyContent: "flex-end", marginTop: "8px" }}>
              <button
                type="button"
                onClick={handleClose}
                style={{
                  background: "#2563eb",
                  color: "#ffffff",
                  padding: "8px 20px",
                  borderRadius: "6px",
                  border: "none",
                  fontWeight: 600,
                  cursor: "pointer",
                }}
              >
                Done
              </button>
            </div>
          </div>
        ) : (
          /* VIEW 2: REGISTRATION FORM */
          <form onSubmit={handleSubmit} style={{ display: "flex", flexDirection: "column", gap: "14px" }}>
            {/* Tenant and Project row */}
            <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "12px" }}>
              <div>
                <label style={{ display: "block", fontSize: "0.75rem", fontWeight: 600, color: "#334155", marginBottom: "4px" }}>
                  TENANT / ORGANIZATION *
                </label>
                <select
                  value={organizationId}
                  onChange={(e) => setOrganizationId(e.target.value)}
                  style={{
                    width: "100%",
                    padding: "7px 10px",
                    borderRadius: "6px",
                    border: "1px solid #cbd5e1",
                    fontSize: "0.8125rem",
                  }}
                >
                  {availableOrgs.map((o) => (
                    <option key={o.id} value={o.id}>
                      {o.name} ({o.id})
                    </option>
                  ))}
                </select>
              </div>
              <div>
                <label style={{ display: "block", fontSize: "0.75rem", fontWeight: 600, color: "#334155", marginBottom: "4px" }}>
                  PROJECT SCOPE *
                </label>
                <select
                  value={projectId}
                  onChange={(e) => setProjectId(e.target.value)}
                  style={{
                    width: "100%",
                    padding: "7px 10px",
                    borderRadius: "6px",
                    border: "1px solid #cbd5e1",
                    fontSize: "0.8125rem",
                  }}
                >
                  {availableProjects.map((p) => (
                    <option key={p.id} value={p.id}>
                      {p.name} ({p.id})
                    </option>
                  ))}
                </select>
              </div>
            </div>

            {/* Agent Name and Machine ID */}
            <div style={{ display: "grid", gridTemplateColumns: "1.2fr 1fr", gap: "12px" }}>
              <div>
                <label style={{ display: "block", fontSize: "0.75rem", fontWeight: 600, color: "#334155", marginBottom: "4px" }}>
                  Agent Name *
                </label>
                <input
                  type="text"
                  required
                  value={name}
                  onChange={(e) => handleNameChange(e.target.value)}
                  placeholder="e.g. Production Support Agent"
                  style={{
                    width: "100%",
                    padding: "7px 10px",
                    borderRadius: "6px",
                    border: "1px solid #cbd5e1",
                    fontSize: "0.8125rem",
                  }}
                />
              </div>
              <div>
                <label style={{ display: "block", fontSize: "0.75rem", fontWeight: 600, color: "#334155", marginBottom: "4px" }}>
                  Agent Identifier *
                </label>
                <input
                  type="text"
                  required
                  value={agentId}
                  onChange={(e) => {
                    setAgentIdTouched(true);
                    setAgentId(e.target.value.toLowerCase());
                  }}
                  placeholder="e.g. prod-support-agent"
                  style={{
                    width: "100%",
                    padding: "7px 10px",
                    borderRadius: "6px",
                    border: "1px solid #cbd5e1",
                    fontSize: "0.8125rem",
                    fontFamily: "var(--font-mono)",
                  }}
                />
              </div>
            </div>

            {/* Framework & LLM Provider Row */}
            <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr 1fr", gap: "12px" }}>
              <div>
                <label style={{ display: "block", fontSize: "0.75rem", fontWeight: 600, color: "#334155", marginBottom: "4px" }}>
                  Agent Framework *
                </label>
                <select
                  value={framework}
                  onChange={(e) => setFramework(e.target.value)}
                  style={{
                    width: "100%",
                    padding: "7px 10px",
                    borderRadius: "6px",
                    border: "1px solid #cbd5e1",
                    fontSize: "0.8125rem",
                  }}
                >
                  <option value="custom">Custom Python Agent</option>
                  <option value="openhands">OpenHands</option>
                  <option value="langgraph">LangGraph</option>
                  <option value="crewai">CrewAI</option>
                  <option value="autogen">AutoGen</option>
                </select>
              </div>

              <div>
                <label style={{ display: "block", fontSize: "0.75rem", fontWeight: 600, color: "#334155", marginBottom: "4px" }}>
                  Upstream Provider *
                </label>
                <select
                  value={llmProvider}
                  onChange={(e) => setLlmProvider(e.target.value)}
                  style={{
                    width: "100%",
                    padding: "7px 10px",
                    borderRadius: "6px",
                    border: "1px solid #cbd5e1",
                    fontSize: "0.8125rem",
                  }}
                >
                  <option value="openai">OpenAI</option>
                  <option value="gemini">Google Gemini</option>
                  <option value="anthropic">Anthropic Claude</option>
                </select>
              </div>

              <div>
                <label style={{ display: "block", fontSize: "0.75rem", fontWeight: 600, color: "#334155", marginBottom: "4px" }}>
                  Default Model *
                </label>
                <input
                  type="text"
                  required
                  value={defaultModel}
                  onChange={(e) => setDefaultModel(e.target.value)}
                  placeholder="e.g. gpt-4o-mini"
                  style={{
                    width: "100%",
                    padding: "7px 10px",
                    borderRadius: "6px",
                    border: "1px solid #cbd5e1",
                    fontSize: "0.8125rem",
                  }}
                />
              </div>
            </div>

            {/* Provider API Key Vaulting Box */}
            <div
              style={{
                background: "#f8fafc",
                border: "1px solid #cbd5e1",
                borderRadius: "6px",
                padding: "12px",
                display: "flex",
                flexDirection: "column",
                gap: "6px",
              }}
            >
              <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between" }}>
                <label style={{ fontSize: "0.75rem", fontWeight: 700, color: "#0f172a" }}>
                  🔒 UPSTREAM PROVIDER API KEY (VAULT ENCRYPTED)
                </label>
                <span style={{ fontSize: "0.68rem", color: "#166534", fontWeight: 600, background: "#dcfce7", padding: "1px 6px", borderRadius: "3px" }}>
                  AES-256-GCM
                </span>
              </div>
              <input
                type="password"
                value={providerApiKey}
                onChange={(e) => setProviderApiKey(e.target.value)}
                placeholder="sk-proj-... or AIzaSy... (Encrypted at rest on Gateway)"
                style={{
                  width: "100%",
                  padding: "8px 12px",
                  borderRadius: "6px",
                  border: "1px solid #94a3b8",
                  fontSize: "0.8125rem",
                  fontFamily: "var(--font-mono)",
                  outline: "none",
                }}
              />
              <div style={{ fontSize: "0.7rem", color: "#64748b" }}>
                This key is encrypted before saving. Your external agent will connect with its agent bearer token (
                <code>agt_...</code>) and will never possess this secret directly.
              </div>
            </div>

            {/* Owner Email & Environment */}
            <div style={{ display: "grid", gridTemplateColumns: "1.2fr 1fr", gap: "12px" }}>
              <div>
                <label style={{ display: "block", fontSize: "0.75rem", fontWeight: 600, color: "#334155", marginBottom: "4px" }}>
                  Owner (Security Officer) *
                </label>
                <input
                  type="email"
                  required
                  value={owner}
                  onChange={(e) => setOwner(e.target.value)}
                  style={{
                    width: "100%",
                    padding: "7px 10px",
                    borderRadius: "6px",
                    border: "1px solid #cbd5e1",
                    fontSize: "0.8125rem",
                  }}
                />
              </div>

              <div>
                <label style={{ display: "block", fontSize: "0.75rem", fontWeight: 600, color: "#334155", marginBottom: "4px" }}>
                  Environment *
                </label>
                <select
                  value={environment}
                  onChange={(e) => setEnvironment(e.target.value)}
                  style={{
                    width: "100%",
                    padding: "7px 10px",
                    borderRadius: "6px",
                    border: "1px solid #cbd5e1",
                    fontSize: "0.8125rem",
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
              <label style={{ display: "block", fontSize: "0.75rem", fontWeight: 600, color: "#334155", marginBottom: "4px" }}>
                Operational Mandate & Allowed Scope
              </label>
              <textarea
                rows={2}
                maxLength={512}
                value={purpose}
                onChange={(e) => setPurpose(e.target.value)}
                placeholder="Describe the agent's function, tools, and intended security boundary..."
                style={{
                  width: "100%",
                  padding: "7px 10px",
                  borderRadius: "6px",
                  border: "1px solid #cbd5e1",
                  fontSize: "0.8125rem",
                  resize: "vertical",
                }}
              />
            </div>

            {/* Submit and Cancel Buttons */}
            <div
              style={{
                display: "flex",
                justifyContent: "flex-end",
                gap: "10px",
                borderTop: "1px solid #e2e8f0",
                paddingTop: "12px",
              }}
            >
              <button
                type="button"
                onClick={handleClose}
                disabled={isSubmitting}
                style={{
                  padding: "8px 16px",
                  borderRadius: "6px",
                  border: "1px solid #cbd5e1",
                  background: "#f8fafc",
                  color: "#334155",
                  fontWeight: 600,
                  fontSize: "0.8125rem",
                  cursor: "pointer",
                }}
              >
                Cancel
              </button>
              <button
                type="submit"
                disabled={isSubmitting}
                style={{
                  padding: "8px 20px",
                  borderRadius: "6px",
                  border: "none",
                  background: "#2563eb",
                  color: "#ffffff",
                  fontWeight: 600,
                  fontSize: "0.8125rem",
                  cursor: "pointer",
                }}
              >
                {isSubmitting ? "Registering & Encrypting Vault..." : "+ Register & Issue Credentials"}
              </button>
            </div>
          </form>
        )}
      </div>
    </div>
  );
};
