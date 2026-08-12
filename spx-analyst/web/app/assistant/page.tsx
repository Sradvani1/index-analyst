import { notFound } from "next/navigation";

import { AssistantWorkspace } from "@/components/chat/assistant-workspace";

export default function AssistantPage() {
  if (process.env.SPX_CHAT_ENABLED === "false") {
    notFound();
  }

  return <AssistantWorkspace />;
}

export const metadata = {
  title: "Assistant · SPX Analyst",
};
