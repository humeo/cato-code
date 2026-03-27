import { describe, expect, it, mock } from "bun:test";
import type { ReactNode } from "react";

const activityPayload = { id: "activity-1", status: "done" };
const logsPayload = [{ id: 1, message: "log-1" }];
const cookies = mock(async () => ({ toString: () => "session=session-1" }));
const getDashboard = mock(async () => null);
const getActivity = mock(async (_activityId: string, _init?: RequestInit) => activityPayload);
const getActivityLogs = mock(async (_activityId: string, _init?: RequestInit) => logsPayload);

mock.module("next/headers", () => ({
  cookies,
}));

mock.module("@/lib/api", () => ({
  getDashboard,
  getActivity,
  getActivityLogs,
}));

mock.module("@/components/ActivityDetail", () => ({
  ActivityDetail: (props: {
    activityId: string;
    initialActivity: unknown;
    initialLogs: unknown[];
  }): ReactNode => ({
    type: "mock-activity-detail",
    props,
  }),
}));

describe("ActivityPage", () => {
  it("hydrates ActivityDetail with server-fetched activity data", async () => {
    const mod = await import("./page");
    const page = await mod.default({ params: Promise.resolve({ id: "activity-1" }) });

    expect(cookies).toHaveBeenCalled();
    expect(getActivity).toHaveBeenCalledWith("activity-1", { headers: { cookie: "session=session-1" } });
    expect(getActivityLogs).toHaveBeenCalledWith("activity-1", { headers: { cookie: "session=session-1" } });
    expect(page.props.activityId).toBe("activity-1");
    expect(page.props.initialActivity).toEqual(activityPayload);
    expect(page.props.initialLogs).toEqual(logsPayload);
  });
});
