import { cookies } from "next/headers";

import { ActivityDetail } from "@/components/ActivityDetail";
import { getActivity, getActivityLogs } from "@/lib/api";

interface PageProps {
  params: Promise<{ id: string }>;
}

export default async function ActivityPage({ params }: PageProps) {
  const { id } = await params;
  const cookieHeader = (await cookies()).toString();
  const requestInit = cookieHeader ? { headers: { cookie: cookieHeader } } : undefined;
  const [activity, logs] = await Promise.all([getActivity(id, requestInit), getActivityLogs(id, requestInit)]);

  return <ActivityDetail activityId={id} initialActivity={activity} initialLogs={logs ?? []} />;
}
