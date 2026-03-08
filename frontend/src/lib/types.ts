export interface User {
  id: string;
  github_login: string;
  github_email: string | null;
  avatar_url: string | null;
  created_at: string;
  last_login_at: string;
}

export interface Repo {
  id: string;
  repo_url: string;
  watch: number;
  user_id: string | null;
  patrol_interval_hours: number;
  created_at: string;
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
