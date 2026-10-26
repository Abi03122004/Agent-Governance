/**
 * Frontend Authentication and Tenant Context Management
 */

export interface AuthContext {
  userId: string;
  userEmail: string;
  organizationId: string;
  role: string;
  token?: string;
}

const DEFAULT_AUTH: AuthContext = {
  userId: "usr_admin",
  userEmail: "security_admin@enterprise.internal",
  organizationId: "org_enterprise",
  role: "administrator",
};

export function getAuthContext(): AuthContext {
  if (typeof window === "undefined") {
    return DEFAULT_AUTH;
  }
  const saved = localStorage.getItem("ag_auth_context");
  if (!saved) return DEFAULT_AUTH;
  try {
    return JSON.parse(saved);
  } catch {
    return DEFAULT_AUTH;
  }
}

export function setAuthContext(ctx: AuthContext): void {
  if (typeof window !== "undefined") {
    localStorage.setItem("ag_auth_context", JSON.stringify(ctx));
  }
}

export function getAdminHeaders(): Record<string, string> {
  const ctx = getAuthContext();
  const headers: Record<string, string> = {
    "X-Organization-Id": ctx.organizationId,
  };
  if (ctx.token) {
    headers["Authorization"] = `Bearer ${ctx.token}`;
  } else {
    headers["X-User-Email"] = ctx.userEmail;
  }
  return headers;
}
