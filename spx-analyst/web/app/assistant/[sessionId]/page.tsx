import { AssistantWorkspace } from "@/components/chat/assistant-workspace";

interface AssistantSessionPageProps {
  params: Promise<{ sessionId: string }>;
}

export default async function AssistantSessionPage({ params }: AssistantSessionPageProps) {
  const { sessionId } = await params;
  return <AssistantWorkspace sessionId={sessionId} />;
}

export async function generateMetadata({ params }: AssistantSessionPageProps) {
  const { sessionId } = await params;
  return {
    title: `Assistant · ${sessionId.slice(0, 8)} · SPX Analyst`,
  };
}
