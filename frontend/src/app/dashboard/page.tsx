import { getStats, getRepos, getActivities } from "@/lib/api";
import { LiveDashboard } from "@/components/LiveDashboard";

export default async function DashboardPage() {
  const [stats, repos, activities] = await Promise.all([
    getStats(),
    getRepos(),
    getActivities(),
  ]);

  return (
    <div className="space-y-6">
      <LiveDashboard
        initialStats={stats}
        initialActivities={stats?.recent_activities ?? activities ?? []}
        initialRepos={repos ?? []}
      />
    </div>
  );
}
