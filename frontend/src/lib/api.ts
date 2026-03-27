import type { Stats, Repo, Activity, ActivityLog, DashboardPayload } from "./types";

// Server-side: use INTERNAL_API_URL (Docker service name) if set
// Client-side: NEXT_PUBLIC_API_URL (browser-accessible host)
const API_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";
const INTERNAL_API_URL = process.env.INTERNAL_API_URL ?? API_URL;

function getBaseUrl() {
  // typeof window === "undefined" means we're running server-side
  return typeof window === "undefined" ? INTERNAL_API_URL : API_URL;
}

async function apiFetch<T>(path: string, init?: RequestInit): Promise<T | null> {
  try {
    const res = await fetch(`${getBaseUrl()}${path}`, {
      cache: "no-store",
      ...init,
      credentials: "include",
    });
    if (!res.ok) throw new Error(`API error ${res.status}: ${path}`);
    return res.json() as Promise<T>;
  } catch {
    return null;
  }
}

export async function getStats(init?: RequestInit): Promise<Stats | null> {
  return apiFetch<Stats>("/api/stats", init);
}

export async function getDashboard(init?: RequestInit): Promise<DashboardPayload | null> {
  return apiFetch<DashboardPayload>("/api/dashboard", init);
}

export async function getInstallUrl(): Promise<string | null> {
  const data = await apiFetch<{ url: string }>("/api/install-url");
  return data?.url ?? null;
}

export async function getRepos(init?: RequestInit): Promise<Repo[] | null> {
  return apiFetch<Repo[]>("/api/repos", init);
}

export async function getActivities(init?: RequestInit): Promise<Activity[] | null> {
  return apiFetch<Activity[]>("/api/activities", init);
}

export async function watchRepo(
  repoId: string
): Promise<{ status: string; activity_id: string | null } | { error: string } | null> {
  try {
    const res = await fetch(`${API_URL}/api/repos/${repoId}/watch`, { method: "POST", credentials: "include" });
    if (!res.ok) {
      try {
        const body = await res.json();
        return { error: body.detail ?? `HTTP ${res.status}` };
      } catch {
        return { error: `HTTP ${res.status}` };
      }
    }
    return res.json();
  } catch {
    return { error: "Network error" };
  }
}

export async function unwatchRepo(repoId: string): Promise<boolean> {
  try {
    const res = await fetch(`${API_URL}/api/repos/${repoId}/watch`, { method: "DELETE", credentials: "include" });
    return res.ok;
  } catch {
    return false;
  }
}

export async function retrySetup(
  repoId: string
): Promise<{ activity_id: string } | { error: string } | null> {
  try {
    const res = await fetch(`${API_URL}/api/repos/${repoId}/setup/retry`, { method: "POST", credentials: "include" });
    if (!res.ok) {
      try {
        const body = await res.json();
        return { error: body.detail ?? `HTTP ${res.status}` };
      } catch {
        return { error: `HTTP ${res.status}` };
      }
    }
    return res.json();
  } catch {
    return { error: "Network error" };
  }
}

export async function getActivity(activityId: string, init?: RequestInit): Promise<Activity | null> {
  return apiFetch<Activity>(`/api/activities/${activityId}`, init);
}

export async function getActivityLogs(activityId: string, init?: RequestInit): Promise<ActivityLog[] | null> {
  return apiFetch<ActivityLog[]>(`/api/activities/${activityId}/logs`, init);
}

export function getLogStreamUrl(activityId: string): string {
  return `${API_URL}/api/activities/${activityId}/logs/stream`;
}

export { API_URL };
