import { ActivityDetail } from "@/components/ActivityDetail";

interface PageProps {
  params: Promise<{ id: string }>;
}

export default async function ActivityPage({ params }: PageProps) {
  const { id } = await params;
  return <ActivityDetail activityId={id} />;
}
