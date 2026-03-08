"use client";

import { useEffect, useRef, useState, useCallback } from "react";
import type { Activity, ActivityLog } from "@/lib/types";
import { getActivity, getActivityLogs, getLogStreamUrl } from "@/lib/api";
import { PipelineStages } from "@/components/PipelineStages";
import { LogLine } from "@/components/LogLine";
import Link from "next/link";

interface ActivityDetailProps {
  activityId: string;
}

export function ActivityDetail({ activityId }: ActivityDetailProps) {
  const [activity, setActivity] = useState<Activity | null>(null);
  const [logs, setLogs] = useState<ActivityLog[]>([]);
  const [streaming, setStreaming] = useState(false);
  const [loading, setLoading] = useState(true);
  const logEndRef = useRef<HTMLDivElement>(null);
  const autoScroll = useRef(true);
  const containerRef = useRef<HTMLDivElement>(null);

  const scrollToBottom = useCallback(() => {
    if (autoScroll.current) {
      logEndRef.current?.scrollIntoView({ behavior: "smooth" });
    }
  }, []);

  // Handle scroll to detect if user scrolled up
  const handleScroll = useCallback(() => {
    const el = containerRef.current;
    if (!el) return;
    const atBottom = el.scrollHeight - el.scrollTop - el.clientHeight < 50;
    autoScroll.current = atBottom;
  }, []);

  // Fetch initial data
  useEffect(() => {
    let cancelled = false;
    async function load() {
      const [a, l] = await Promise.all([
        getActivity(activityId),
        getActivityLogs(activityId),
      ]);
      if (cancelled) return;
      setActivity(a);
      setLogs(l ?? []);
      setLoading(false);
    }
    load();
    return () => { cancelled = true; };
  }, [activityId]);

  // SSE streaming for running activities
  useEffect(() => {
    if (!activity || activity.status !== "running") return;

    const lastId = logs.length > 0 ? logs[logs.length - 1].id : 0;
    const url = getLogStreamUrl(activityId);
    const es = new EventSource(url, { withCredentials: true });
    setStreaming(true);

    es.onmessage = (e) => {
      try {
        const log: ActivityLog = JSON.parse(e.data);
        if (log.id > lastId) {
          setLogs((prev) => [...prev, log]);
        }
      } catch {
        // skip malformed messages
      }
    };

    es.addEventListener("status", (e) => {
      try {
        const data = JSON.parse((e as MessageEvent).data);
        setActivity((prev) =>
          prev ? { ...prev, status: data.status, pipeline_stage: data.status } : prev
        );
      } catch {
        // ignore
      }
      es.close();
      setStreaming(false);
    });

    es.onerror = () => {
      es.close();
      setStreaming(false);
    };

    return () => {
      es.close();
      setStreaming(false);
    };
  }, [activity?.status, activityId]); // eslint-disable-line react-hooks/exhaustive-deps

  // Auto-scroll on new logs
  useEffect(() => {
    scrollToBottom();
  }, [logs, scrollToBottom]);

  if (loading) {
    return (
      <div className="flex items-center justify-center py-20">
        <div className="animate-spin h-6 w-6 border-2 border-accent border-t-transparent rounded-full" />
      </div>
    );
  }

  if (!activity) {
    return (
      <div className="text-center py-20 text-gray-500">
        Activity not found.
      </div>
    );
  }

  const stage = activity.pipeline_stage ?? activity.status;

  return (
    <div className="space-y-4">
      {/* Back link */}
      <Link
        href="/dashboard"
        className="inline-flex items-center gap-1 text-xs text-gray-500 hover:text-gray-300 transition-colors"
      >
        <svg className="w-3 h-3" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
          <path strokeLinecap="round" strokeLinejoin="round" d="M15 19l-7-7 7-7" />
        </svg>
        Dashboard
      </Link>

      {/* Pipeline stage */}
      <div className="glass rounded-xl p-4">
        <PipelineStages stage={stage} />
      </div>

      {/* Metadata */}
      <div className="glass rounded-xl p-4">
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4 text-xs">
          <div>
            <span className="text-gray-600 block">Repository</span>
            <span className="text-gray-300 font-mono">{activity.repo_id.substring(0, 12)}</span>
          </div>
          <div>
            <span className="text-gray-600 block">Kind</span>
            <span className="text-gray-300">{activity.kind}</span>
          </div>
          <div>
            <span className="text-gray-600 block">Trigger</span>
            <span className="text-gray-300 font-mono">{activity.trigger ?? "—"}</span>
          </div>
          <div>
            <span className="text-gray-600 block">Cost</span>
            <span className="text-amber-400 font-mono">
              {activity.cost_usd != null ? `$${activity.cost_usd.toFixed(4)}` : "—"}
            </span>
          </div>
          <div>
            <span className="text-gray-600 block">Created</span>
            <span className="text-gray-400">{activity.created_at.substring(0, 19).replace("T", " ")}</span>
          </div>
          <div>
            <span className="text-gray-600 block">Updated</span>
            <span className="text-gray-400">{activity.updated_at.substring(0, 19).replace("T", " ")}</span>
          </div>
          {activity.summary && (
            <div className="col-span-2">
              <span className="text-gray-600 block">Summary</span>
              <span className="text-gray-300">{activity.summary}</span>
            </div>
          )}
        </div>
      </div>

      {/* Log viewer */}
      <div className="glass rounded-xl p-4">
        <div className="flex items-center justify-between mb-3">
          <h3 className="text-sm font-semibold text-gray-300 flex items-center gap-2">
            <span className="w-1.5 h-1.5 rounded-full bg-accent" />
            Execution Logs
          </h3>
          {streaming && (
            <span className="flex items-center gap-1.5 text-xs text-blue-400">
              <span className="w-1.5 h-1.5 rounded-full bg-blue-400 animate-pulse" />
              Streaming live...
            </span>
          )}
        </div>

        <div
          ref={containerRef}
          onScroll={handleScroll}
          className="bg-black/30 rounded-lg p-3 max-h-[600px] overflow-y-auto font-mono"
        >
          {logs.length === 0 ? (
            <p className="text-gray-600 text-xs text-center py-4">
              No logs yet.
            </p>
          ) : (
            logs.map((log) => (
              <LogLine key={log.id} line={log.line} ts={log.ts} />
            ))
          )}
          <div ref={logEndRef} />
        </div>
      </div>
    </div>
  );
}
