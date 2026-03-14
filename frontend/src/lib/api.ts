import type { Stats, Repo, Activity, ActivityLog, PatrolStatus } from "./types";

const API_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

async function apiFetch<T>(path: string, init?: RequestInit): Promise<T | null> {
  try {
    const res = await fetch(`${API_URL}${path}`, {
      cache: "no-store",
      ...init,
    });
    if (!res.ok) throw new Error(`API error ${res.status}: ${path}`);
    return res.json() as Promise<T>;
  } catch {
    return null;
  }
}

export async function getStats(): Promise<Stats | null> {
  return apiFetch<Stats>("/api/stats");
}

export async function getRepos(): Promise<Repo[] | null> {
  return apiFetch<Repo[]>("/api/repos");
}

export async function getActivities(): Promise<Activity[] | null> {
  return apiFetch<Activity[]>("/api/activities");
}

export async function deleteRepo(repoId: string): Promise<boolean> {
  try {
    const res = await fetch(`${API_URL}/api/repos/${repoId}`, { method: "DELETE" });
    return res.ok;
  } catch {
    return false;
  }
}

export async function getActivity(activityId: string): Promise<Activity | null> {
  return apiFetch<Activity>(`/api/activities/${activityId}`);
}

export async function getActivityLogs(activityId: string): Promise<ActivityLog[] | null> {
  return apiFetch<ActivityLog[]>(`/api/activities/${activityId}/logs`);
}

export function getLogStreamUrl(activityId: string): string {
  return `${API_URL}/api/activities/${activityId}/logs/stream`;
}

export async function getPatrolStatus(repoId: string): Promise<PatrolStatus | null> {
  return apiFetch<PatrolStatus>(`/api/repos/${repoId}/patrol/status`);
}

export async function updatePatrolSettings(
  repoId: string,
  settings: {
    patrol_enabled: boolean;
    patrol_interval_hours: number;
    patrol_max_issues: number;
    patrol_window_hours: number;
  }
): Promise<boolean> {
  try {
    const res = await fetch(`${API_URL}/api/repos/${repoId}/patrol`, {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(settings),
    });
    return res.ok;
  } catch {
    return false;
  }
}

export async function triggerPatrol(
  repoId: string
): Promise<{ activity_id: string } | { error: string } | null> {
  try {
    const res = await fetch(`${API_URL}/api/repos/${repoId}/patrol/trigger`, { method: "POST" });
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

export { API_URL };
