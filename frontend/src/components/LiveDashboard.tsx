"use client";

import { useEffect, useState, useCallback } from "react";
import type { Stats, Activity, Repo } from "@/lib/types";
import { getStats, getActivities, getRepos } from "@/lib/api";
import { StatCard } from "@/components/StatCard";
import { RepoList } from "@/components/RepoList";
import { GroupedActivityTable } from "@/components/GroupedActivityTable";

interface LiveDashboardProps {
  initialStats: Stats | null;
  initialActivities: Activity[];
  initialRepos: Repo[];
}

export function LiveDashboard({ initialStats, initialActivities, initialRepos }: LiveDashboardProps) {
  const [stats, setStats] = useState<Stats | null>(initialStats);
  const [activities, setActivities] = useState<Activity[]>(initialActivities);
  const [repos, setRepos] = useState<Repo[]>(initialRepos);

  const refresh = useCallback(async () => {
    const [newStats, newActivities, newRepos] = await Promise.all([
      getStats(),
      getActivities(),
      getRepos(),
    ]);
    if (newStats) setStats(newStats);
    if (newActivities) setActivities(newActivities);
    if (newRepos) setRepos(newRepos);
  }, []);

  useEffect(() => {
    const interval = setInterval(refresh, 5000);
    return () => clearInterval(interval);
  }, [refresh]);

  const displayActivities = stats?.recent_activities ?? activities;

  return (
    <>
      {/* Stat cards */}
      {stats && (
        <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
          <StatCard
            label="Repos Watched"
            value={stats.repos.watched}
            icon="📦"
          />
          <StatCard
            label="Total Activities"
            value={stats.activities.total}
            icon="⚡"
          />
          <StatCard
            label="Completed"
            value={stats.activities.by_status.done ?? 0}
            icon="✅"
            accent="text-emerald-400"
          />
          <StatCard
            label="Total Cost"
            value={`$${stats.cost_usd.toFixed(2)}`}
            icon="💰"
            accent="text-amber-400"
          />
        </div>
      )}

      {/* Watched Repositories — above activities */}
      <section className="glass rounded-xl p-5">
        <div className="flex items-center justify-between mb-4">
          <h2 className="text-sm font-semibold text-gray-300 flex items-center gap-2">
            <span className="w-1.5 h-1.5 rounded-full bg-accent" />
            Watched Repositories
          </h2>
          <span className="text-xs text-gray-600">
            {repos.length} repos
          </span>
        </div>
        <RepoList repos={repos} />
      </section>

      {/* Recent Activities — grouped by repo */}
      <section className="glass rounded-xl p-5">
        <div className="flex items-center justify-between mb-4">
          <h2 className="text-sm font-semibold text-gray-300 flex items-center gap-2">
            <span className="w-1.5 h-1.5 rounded-full bg-accent" />
            Recent Activities
          </h2>
          <span className="text-xs text-gray-600">
            {displayActivities.length} entries
          </span>
        </div>
        <GroupedActivityTable activities={displayActivities} repos={repos} />
      </section>
    </>
  );
}
