export interface Repo {
  id: string;
  repo_url: string;
  watch: number;
  user_id: string | null;
  lifecycle_status: string;
  last_ready_at: string | null;
  last_error: string | null;
  last_setup_activity_id: string | null;
  patrol_interval_hours: number;
  patrol_enabled: number;
  patrol_max_issues: number;
  patrol_window_hours: number;
  last_patrol_sha: string | null;
  created_at: string;
}

export interface RuntimeSession {
  id: string;
  repo_id: string;
  sdk_session_id: string | null;
  entry_kind: string;
  status: string;
  worktree_path: string;
  branch_name: string;
  fork_from_session_id: string | null;
  created_at: string;
  updated_at: string;
  last_activity_at: string;
  terminal_at: string | null;
  gc_eligible_at: string | null;
  gc_delete_after: string | null;
  gc_status: string | null;
  gc_error?: string | null;
  latest_checkpoint?: Record<string, unknown> | null;
  resolution_state?: {
    hypotheses?: Array<Record<string, unknown>>;
    todos?: Array<Record<string, unknown>>;
    checkpoints?: Array<Record<string, unknown>>;
  } | null;
}

export interface ActivityStep {
  activity_id: string;
  step_key: string;
  status: string | null;
  started_at: string | null;
  finished_at: string | null;
  duration_ms: number | null;
  reason: string | null;
  metadata: string | null;
}

export interface RuntimeResult {
  status?: string;
  summary?: string;
  session?: {
    sdk_session_id?: string | null;
    continued?: boolean;
  };
  writebacks?: Array<Record<string, unknown>>;
  artifacts?: Record<string, unknown>;
  metrics?: {
    cost_usd?: number | null;
    duration_ms?: number | null;
    turns?: number | null;
  };
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
  session_id: string | null;
  pipeline_stage?: string;
  summary: string | null;
  cost_usd: number | null;
  requires_approval?: number;
  runtime_session?: RuntimeSession | null;
  runtime_result?: RuntimeResult | null;
  steps?: ActivityStep[];
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
