export interface Repo {
  id: string;
  repo_url: string;
  watch: number;
  user_id: string | null;
  patrol_interval_hours: number;
  patrol_enabled: number;
  patrol_max_issues: number;
  patrol_window_hours: number;
  last_patrol_sha: string | null;
  created_at: string;
}

export interface PatrolStatus {
  enabled: boolean;
  patrol_interval_hours: number;
  patrol_max_issues: number;
  patrol_window_hours: number;
  budget_remaining: number;
  last_patrol_at: string | null;
  last_patrol_sha: string | null;
  embedding_service_status: "ok" | "error" | "not_configured" | string;
}

export interface Activity {
  id: string;
  repo_id: string;
  kind: string;
  trigger: string | null;
  status: string;
  pipeline_stage?: string;
  summary: string | null;
  cost_usd: number | null;
  requires_approval?: number;
  created_at: string;
  updated_at: string;
}

export interface ActivityLog {
  id: number;
  activity_id: string;
  line: string;
  ts: string;
}

export interface Stats {
  repos: { total: number; watched: number };
  activities: {
    by_status: Record<string, number>;
    by_kind: Record<string, number>;
    total: number;
  };
  cost_usd: number;
  recent_activities: Activity[];
}
