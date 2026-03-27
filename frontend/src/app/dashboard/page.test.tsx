import { describe, expect, it, mock } from "bun:test";
import type { ReactNode } from "react";
import type { DashboardPayload } from "@/lib/types";

const dashboardPayload: DashboardPayload = {
  repos: { total: 1, watched: 1 },
  activities: { by_status: { done: 1 }, by_kind: { setup: 1 }, total: 1 },
  cost_usd: 0.12,
  recent_activities: [],
  stats: {
    repos: { total: 1, watched: 1 },
    activities: { by_status: { done: 1 }, by_kind: { setup: 1 }, total: 1 },
    cost_usd: 0.12,
    recent_activities: [],
  },
  activities: [{ id: "activity-1" }] as DashboardPayload["activities"],
  repos: [{ id: "repo-1" }] as DashboardPayload["repos"],
};

const getDashboard = mock(async (_init?: RequestInit) => dashboardPayload);
const getActivity = mock(async () => null);
const getActivityLogs = mock(async () => []);
const cookies = mock(async () => ({ toString: () => "session=session-1" }));

mock.module("next/headers", () => ({
  cookies,
}));

mock.module("@/lib/api", () => ({
  getDashboard,
  getActivity,
  getActivityLogs,
}));

mock.module("@/components/LiveDashboard", () => ({
  LiveDashboard: (props: { initialStats: unknown; initialActivities: unknown; initialRepos: unknown }): ReactNode => ({
    type: "mock-live-dashboard",
    props,
  }),
}));

describe("DashboardPage", () => {
  it("hydrates LiveDashboard with server-fetched data", async () => {
    const mod = await import("./page");
    const page = await mod.default();
    const liveDashboard = page.props.children;

    expect(cookies).toHaveBeenCalled();
    expect(getDashboard).toHaveBeenCalledWith({ headers: { cookie: "session=session-1" } });
    expect(liveDashboard.props.initialStats).toEqual(dashboardPayload.stats);
    expect(liveDashboard.props.initialActivities).toEqual(dashboardPayload.activities);
    expect(liveDashboard.props.initialRepos).toEqual(dashboardPayload.repos);
  });
});
