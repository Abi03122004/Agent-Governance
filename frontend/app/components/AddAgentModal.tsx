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
        inset: 0,
        background: "rgba(0, 0, 0, 0.85)",
        backdropFilter: "blur(8px)",
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
          background: "#18171B",
          border: "1px solid #262529",
          borderRadius: "22px",
          width: "100%",
          maxWidth: "720px",
          maxHeight: "90vh",
          overflowY: "auto",
          padding: "24px 28px",
          display: "flex",
          flexDirection: "column",
          gap: "18px",
          boxShadow: "0 24px 48px rgba(0, 0, 0, 0.7), 0 0 24px rgba(255, 73, 47, 0.12)",
          color: "#F5F5F5",
        }}
      >
        {/* Modal Header */}
        <div
          style={{
            display: "flex",
            alignItems: "center",
            justifyContent: "space-between",
            borderBottom: "1px solid #262529",
            paddingBottom: "14px",
          }}
        >
          <div style={{ display: "flex", alignItems: "center", gap: "12px" }}>
            <div
              style={{
                width: "40px",
                height: "40px",
                borderRadius: "12px",
                background: "linear-gradient(135deg, #FF492F 0%, #FF7043 100%)",
                display: "flex",
                alignItems: "center",
                justifyContent: "center",
                fontSize: "1.2rem",
                color: "#FFFFFF",
                boxShadow: "0 0 16px rgba(255, 73, 47, 0.35)",
              }}
            >
              🤖
            </div>
            <div>
              <h2 style={{ fontSize: "1.05rem", fontWeight: 700, color: "#F5F5F5", margin: 0 }}>
                {successData ? "External Agent Integrated" : "Register External AI Agent"}
              </h2>
              <div style={{ fontSize: "0.78rem", color: "#858585", marginTop: "2px" }}>
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
              fontSize: "1.2rem",
              cursor: "pointer",
              color: "#858585",
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
              borderRadius: "10px",
              background: "rgba(255, 73, 47, 0.14)",
              border: "1px solid rgba(255, 73, 47, 0.4)",
              color: "#FF492F",
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
                padding: "12px 16px",
                background: "rgba(16, 185, 129, 0.12)",
                border: "1px solid rgba(16, 185, 129, 0.3)",
                borderRadius: "12px",
                display: "flex",
                alignItems: "center",
                gap: "10px",
              }}
            >
              <span style={{ fontSize: "1.2rem" }}>✅</span>
              <div>
                <div style={{ fontWeight: 700, color: "#10B981", fontSize: "0.875rem" }}>
                  External Agent Successfully Registered &amp; Vaulted
                </div>
                <div style={{ fontSize: "0.75rem", color: "#A1A1A8", marginTop: "2px" }}>
                  <span style={{ fontWeight: 600, color: "#F5F5F5" }}>{successData.agent.name}</span> (
                  <code style={{ background: "#141316", color: "#FF7043", padding: "1px 6px", borderRadius: "4px", fontFamily: "var(--font-mono)" }}>
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
                background: "#141316",
                border: "1px solid #262529",
                borderRadius: "12px",
                padding: "14px",
              }}
            >
              <div>
                <div style={{ fontSize: "0.6875rem", color: "#858585", fontWeight: 600 }}>LLM GOVERNANCE PROXY URL</div>
                <code style={{ fontSize: "0.75rem", color: "#FF7043", fontFamily: "var(--font-mono)", wordBreak: "break-all" }}>
                  {proxyUrl}
                </code>
              </div>
              <div>
                <div style={{ fontSize: "0.6875rem", color: "#858585", fontWeight: 600 }}>PROVIDER VAULT STATUS</div>
                <div style={{ fontSize: "0.75rem", color: "#10B981", fontWeight: 600 }}>
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
                  background: "#141316",
                  border: "1px solid #262529",
                  borderRadius: "12px",
                  padding: "14px 16px",
                  color: "#F5F5F5",
                }}
              >
                <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between" }}>
                  <div style={{ display: "flex", alignItems: "center", gap: "6px" }}>
                    <span>🔑</span>
                    <span style={{ fontWeight: 600, fontSize: "0.8125rem", color: "#F5F5F5" }}>Agent Runtime Bearer Token</span>
                  </div>
                  <span style={{ fontSize: "0.7rem", color: "#858585", fontFamily: "var(--font-mono)" }}>
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
                      background: "#0B0B0D",
                      border: "1px solid #262529",
                      borderRadius: "8px",
                      padding: "7px 12px",
                      color: "#FF8A65",
                      fontFamily: "var(--font-mono)",
                      fontSize: "0.8125rem",
                      outline: "none",
                    }}
                  />
                  <button
                    type="button"
                    onClick={() => setShowSecret(!showSecret)}
                    className="btn btn-ghost"
                    style={{ padding: "6px 12px", fontSize: "0.75rem" }}
                  >
                    {showSecret ? "Hide" : "Show"}
                  </button>
                  <button
                    type="button"
                    onClick={() => copyToClipboard(successData.credential!.plaintext_secret)}
                    className="btn btn-primary"
                    style={{ padding: "6px 16px", fontSize: "0.75rem", whiteSpace: "nowrap" }}
                  >
                    {copiedSecret ? "Copied!" : "Copy"}
                  </button>
                </div>
                <div style={{ fontSize: "0.72rem", color: "#FF9800" }}>
                  ⚠️ Save this token now. It will never be displayed in plaintext again.
                </div>
              </div>
            )}

            {/* Framework Integration Instructions */}
            <div>
              <div style={{ fontSize: "0.75rem", fontWeight: 700, color: "#858585", marginBottom: "8px", textTransform: "uppercase" }}>
                Connect Your Agent Framework
              </div>
              <div style={{ display: "flex", gap: "6px", marginBottom: "8px", flexWrap: "wrap" }}>
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
                      padding: "5px 12px",
                      borderRadius: "8px",
                      fontSize: "0.72rem",
                      fontWeight: 600,
                      border: "1px solid",
                      borderColor: activeSnippetTab === t.id ? "#FF492F" : "#262529",
                      background: activeSnippetTab === t.id ? "rgba(255, 73, 47, 0.15)" : "#141316",
                      color: activeSnippetTab === t.id ? "#FF7043" : "#858585",
                      cursor: "pointer",
                      transition: "all 0.15s ease",
                    }}
                  >
                    {t.label}
                  </button>
                ))}
              </div>

              <div style={{ position: "relative" }}>
                <pre
                  style={{
                    background: "#0B0B0D",
                    color: "#F5F5F5",
                    padding: "14px",
                    borderRadius: "10px",
                    border: "1px solid #262529",
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
                  className="btn btn-ghost"
                  style={{
                    position: "absolute",
                    top: "8px",
                    right: "8px",
                    fontSize: "0.7rem",
                    padding: "4px 10px",
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
                className="btn btn-primary"
                style={{ padding: "8px 24px" }}
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
                <label style={{ display: "block", fontSize: "0.75rem", fontWeight: 600, color: "#858585", marginBottom: "6px" }}>
                  TENANT / ORGANIZATION *
                </label>
                <select
                  value={organizationId}
                  onChange={(e) => setOrganizationId(e.target.value)}
                  style={{
                    width: "100%",
                    background: "#141316",
                    color: "#F5F5F5",
                    border: "1px solid #262529",
                    borderRadius: "10px",
                    padding: "8px 12px",
                    fontSize: "0.8125rem",
                    outline: "none",
                  }}
                >
                  {availableOrgs.map((o) => (
                    <option key={o.id} value={o.id} style={{ background: "#1C1B1F", color: "#F5F5F5" }}>
                      {o.name} ({o.id})
                    </option>
                  ))}
                </select>
              </div>
              <div>
                <label style={{ display: "block", fontSize: "0.75rem", fontWeight: 600, color: "#858585", marginBottom: "6px" }}>
                  PROJECT SCOPE *
                </label>
                <select
                  value={projectId}
                  onChange={(e) => setProjectId(e.target.value)}
                  style={{
                    width: "100%",
                    background: "#141316",
                    color: "#F5F5F5",
                    border: "1px solid #262529",
                    borderRadius: "10px",
                    padding: "8px 12px",
                    fontSize: "0.8125rem",
                    outline: "none",
                  }}
                >
                  {availableProjects.map((p) => (
                    <option key={p.id} value={p.id} style={{ background: "#1C1B1F", color: "#F5F5F5" }}>
                      {p.name} ({p.id})
                    </option>
                  ))}
                </select>
              </div>
            </div>

            {/* Agent Name and Machine ID */}
            <div style={{ display: "grid", gridTemplateColumns: "1.2fr 1fr", gap: "12px" }}>
              <div>
                <label style={{ display: "block", fontSize: "0.75rem", fontWeight: 600, color: "#858585", marginBottom: "6px" }}>
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
                    background: "#141316",
                    color: "#F5F5F5",
                    border: "1px solid #262529",
                    borderRadius: "10px",
                    padding: "8px 12px",
                    fontSize: "0.8125rem",
                    outline: "none",
                  }}
                />
              </div>
              <div>
                <label style={{ display: "block", fontSize: "0.75rem", fontWeight: 600, color: "#858585", marginBottom: "6px" }}>
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
                    background: "#141316",
                    color: "#F5F5F5",
                    border: "1px solid #262529",
                    borderRadius: "10px",
                    padding: "8px 12px",
                    fontSize: "0.8125rem",
                    fontFamily: "var(--font-mono)",
                    outline: "none",
                  }}
                />
              </div>
            </div>

            {/* Framework & LLM Provider Row */}
            <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr 1fr", gap: "12px" }}>
              <div>
                <label style={{ display: "block", fontSize: "0.75rem", fontWeight: 600, color: "#858585", marginBottom: "6px" }}>
                  Agent Framework *
                </label>
                <select
                  value={framework}
                  onChange={(e) => setFramework(e.target.value)}
                  style={{
                    width: "100%",
                    background: "#141316",
                    color: "#F5F5F5",
                    border: "1px solid #262529",
                    borderRadius: "10px",
                    padding: "8px 12px",
                    fontSize: "0.8125rem",
                    outline: "none",
                  }}
                >
                  <option value="custom" style={{ background: "#1C1B1F" }}>Custom Python Agent</option>
                  <option value="openhands" style={{ background: "#1C1B1F" }}>OpenHands</option>
                  <option value="langgraph" style={{ background: "#1C1B1F" }}>LangGraph</option>
                  <option value="crewai" style={{ background: "#1C1B1F" }}>CrewAI</option>
                  <option value="autogen" style={{ background: "#1C1B1F" }}>AutoGen</option>
                </select>
              </div>

              <div>
                <label style={{ display: "block", fontSize: "0.75rem", fontWeight: 600, color: "#858585", marginBottom: "6px" }}>
                  Upstream Provider *
                </label>
                <select
                  value={llmProvider}
                  onChange={(e) => setLlmProvider(e.target.value)}
                  style={{
                    width: "100%",
                    background: "#141316",
                    color: "#F5F5F5",
                    border: "1px solid #262529",
                    borderRadius: "10px",
                    padding: "8px 12px",
                    fontSize: "0.8125rem",
                    outline: "none",
                  }}
                >
                  <option value="openai" style={{ background: "#1C1B1F" }}>OpenAI</option>
                  <option value="gemini" style={{ background: "#1C1B1F" }}>Google Gemini</option>
                  <option value="anthropic" style={{ background: "#1C1B1F" }}>Anthropic Claude</option>
                </select>
              </div>

              <div>
                <label style={{ display: "block", fontSize: "0.75rem", fontWeight: 600, color: "#858585", marginBottom: "6px" }}>
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
                    background: "#141316",
                    color: "#F5F5F5",
                    border: "1px solid #262529",
                    borderRadius: "10px",
                    padding: "8px 12px",
                    fontSize: "0.8125rem",
                    outline: "none",
                  }}
                />
              </div>
            </div>

            {/* Provider API Key Vaulting Box */}
            <div
              style={{
                background: "#141316",
                border: "1px solid #262529",
                borderRadius: "12px",
                padding: "14px",
                display: "flex",
                flexDirection: "column",
                gap: "8px",
              }}
            >
              <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between" }}>
                <label style={{ fontSize: "0.75rem", fontWeight: 700, color: "#F5F5F5" }}>
                  🔒 UPSTREAM PROVIDER API KEY (VAULT ENCRYPTED)
                </label>
                <span style={{ fontSize: "0.68rem", color: "#10B981", fontWeight: 700, background: "rgba(16, 185, 129, 0.12)", border: "1px solid rgba(16, 185, 129, 0.25)", padding: "1px 6px", borderRadius: "6px" }}>
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
                  background: "#0B0B0D",
                  color: "#F5F5F5",
                  border: "1px solid #262529",
                  borderRadius: "8px",
                  padding: "8px 12px",
                  fontSize: "0.8125rem",
                  fontFamily: "var(--font-mono)",
                  outline: "none",
                }}
              />
              <div style={{ fontSize: "0.7rem", color: "#858585" }}>
                This key is encrypted before saving. Your external agent will connect with its agent bearer token (
                <code>agt_...</code>) and will never possess this secret directly.
              </div>
            </div>

            {/* Owner Email & Environment */}
            <div style={{ display: "grid", gridTemplateColumns: "1.2fr 1fr", gap: "12px" }}>
              <div>
                <label style={{ display: "block", fontSize: "0.75rem", fontWeight: 600, color: "#858585", marginBottom: "6px" }}>
                  Owner (Security Officer) *
                </label>
                <input
                  type="email"
                  required
                  value={owner}
                  onChange={(e) => setOwner(e.target.value)}
                  style={{
                    width: "100%",
                    background: "#141316",
                    color: "#F5F5F5",
                    border: "1px solid #262529",
                    borderRadius: "10px",
                    padding: "8px 12px",
                    fontSize: "0.8125rem",
                    outline: "none",
                  }}
                />
              </div>

              <div>
                <label style={{ display: "block", fontSize: "0.75rem", fontWeight: 600, color: "#858585", marginBottom: "6px" }}>
                  Environment *
                </label>
                <select
                  value={environment}
                  onChange={(e) => setEnvironment(e.target.value)}
                  style={{
                    width: "100%",
                    background: "#141316",
                    color: "#F5F5F5",
                    border: "1px solid #262529",
                    borderRadius: "10px",
                    padding: "8px 12px",
                    fontSize: "0.8125rem",
                    outline: "none",
                  }}
                >
                  <option value="development" style={{ background: "#1C1B1F" }}>Development (dev)</option>
                  <option value="staging" style={{ background: "#1C1B1F" }}>Staging (staging)</option>
                  <option value="production" style={{ background: "#1C1B1F" }}>Production (prod)</option>
                </select>
              </div>
            </div>

            {/* Purpose */}
            <div>
              <label style={{ display: "block", fontSize: "0.75rem", fontWeight: 600, color: "#858585", marginBottom: "6px" }}>
                Operational Mandate &amp; Allowed Scope
              </label>
              <textarea
                rows={2}
                maxLength={512}
                value={purpose}
                onChange={(e) => setPurpose(e.target.value)}
                placeholder="Describe the agent's function, tools, and intended security boundary..."
                style={{
                  width: "100%",
                  background: "#141316",
                  color: "#F5F5F5",
                  border: "1px solid #262529",
                  borderRadius: "10px",
                  padding: "8px 12px",
                  fontSize: "0.8125rem",
                  resize: "vertical",
                  outline: "none",
                }}
              />
            </div>

            {/* Submit and Cancel Buttons */}
            <div
              style={{
                display: "flex",
                justifyContent: "flex-end",
                gap: "10px",
                borderTop: "1px solid #262529",
                paddingTop: "14px",
              }}
            >
              <button
                type="button"
                onClick={handleClose}
                disabled={isSubmitting}
                className="btn btn-ghost"
                style={{ padding: "8px 18px" }}
              >
                Cancel
              </button>
              <button
                type="submit"
                disabled={isSubmitting}
                className="btn btn-primary"
                style={{ padding: "8px 24px" }}
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
