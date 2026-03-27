"use client";

import type { Activity } from "@/lib/types";
import { PipelineStages } from "@/components/PipelineStages";
import { useRouter } from "next/navigation";

const STATUS_STYLES: Record<string, string> = {
  done: "text-emerald-400 bg-emerald-400/10",
  failed: "text-red-400 bg-red-400/10",
  running: "text-blue-400 bg-blue-400/10",
  pending: "text-amber-400 bg-amber-400/10",
  pending_approval: "text-purple-400 bg-purple-400/10",
};

interface ActivityTableProps {
  activities: Activity[];
  hideRepo?: boolean;
}

export function ActivityTable({ activities, hideRepo = false }: ActivityTableProps) {
  const router = useRouter();

  if (!activities.length) {
    return (
      <div className="flex flex-col items-center justify-center py-8 text-gray-600">
        <span className="text-2xl mb-2">📋</span>
        <p className="text-sm">No activities yet.</p>
      </div>
    );
  }

  return (
    <div className="overflow-x-auto -mx-5 px-5">
      <table className="w-full text-xs">
        <thead>
          <tr className="text-gray-500 border-b border-border-subtle">
            {!hideRepo && (
              <th className="text-left py-2.5 pr-4 font-medium uppercase tracking-wider">Repo</th>
            )}
            <th className="text-left py-2.5 pr-4 font-medium uppercase tracking-wider">Kind</th>
            <th className="text-left py-2.5 pr-4 font-medium uppercase tracking-wider">Trigger</th>
            <th className="text-left py-2.5 pr-4 font-medium uppercase tracking-wider">Status</th>
            <th className="text-left py-2.5 pr-4 font-medium uppercase tracking-wider">Progress</th>
            <th className="text-left py-2.5 pr-4 font-medium uppercase tracking-wider">Cost</th>
            <th className="text-left py-2.5 font-medium uppercase tracking-wider">Updated</th>
          </tr>
        </thead>
        <tbody>
          {activities.map((a) => {
            const stage = a.pipeline_stage ?? a.status;
            return (
              <tr
                key={a.id}
                onClick={() => router.push(`/dashboard/activity/${a.id}`)}
                onMouseEnter={() => router.prefetch(`/dashboard/activity/${a.id}`)}
                onFocus={() => router.prefetch(`/dashboard/activity/${a.id}`)}
                className="text-gray-400 border-b border-border-subtle/50 hover:bg-white/[0.03] transition-colors cursor-pointer"
              >
                {!hideRepo && (
                  <td className="py-2.5 pr-4 text-gray-300 font-medium">{a.repo_id}</td>
                )}
                <td className="py-2.5 pr-4">{a.kind}</td>
                <td className="py-2.5 pr-4 font-mono text-gray-500">{a.trigger ?? ""}</td>
                <td className="py-2.5 pr-4">
                  <span
                    className={`inline-flex items-center gap-1.5 px-2 py-0.5 rounded-full text-xs font-medium ${
                      STATUS_STYLES[stage] ?? "text-gray-400 bg-gray-400/10"
                    }`}
                  >
                    {stage === "running" && (
                      <span className="w-1.5 h-1.5 rounded-full bg-blue-400 animate-pulse" />
                    )}
                    {stage.replace("_", " ")}
                  </span>
                </td>
                <td className="py-2.5 pr-4">
                  <PipelineStages stage={stage} compact />
                </td>
                <td className="py-2.5 pr-4 font-mono">
                  {a.cost_usd != null ? `$${a.cost_usd.toFixed(4)}` : "—"}
                </td>
                <td className="py-2.5 text-gray-500">
                  {a.updated_at ? new Date(a.updated_at).toLocaleString() : ""}
                </td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}
