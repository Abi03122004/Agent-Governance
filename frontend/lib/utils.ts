/**
 * Formatting and Helper Utilities
 */

export function formatDate(dateString: string | null | undefined): string {
  if (!dateString) return "—";
  try {
    const d = new Date(dateString);
    return d.toLocaleString("en-US", {
      month: "short",
      day: "numeric",
      hour: "2-digit",
      minute: "2-digit",
      second: "2-digit",
    });
  } catch {
    return dateString;
  }
}

export function truncateHash(hash: string | null | undefined, length = 12): string {
  if (!hash) return "—";
  if (hash.length <= length) return hash;
  return `${hash.slice(0, length)}...`;
}

export function getDecisionBadgeClass(decision: string): string {
  switch (decision?.toUpperCase()) {
    case "ALLOW":
      return "badge-allow";
    case "BLOCK":
      return "badge-block";
    case "REQUIRE_APPROVAL":
      return "badge-approval";
    case "SUSPEND":
      return "badge-suspend";
    default:
      return "badge-default";
  }
}
