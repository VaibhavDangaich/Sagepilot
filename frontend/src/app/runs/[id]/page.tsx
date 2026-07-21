import RunDetailClient from "@/components/RunDetailClient";

// Next.js 16: dynamic route `params` are async and must be awaited.
export default async function RunDetailPage({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  const { id } = await params;
  return <RunDetailClient runId={id} />;
}
