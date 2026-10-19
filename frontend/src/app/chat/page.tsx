"use client";

import { useState } from "react";
import { ChatInterface } from "@/components/chat-interface";
import { SourcePanel } from "@/components/source-panel";
import { useRagChat } from "@/lib/use-rag-chat";
import { Switch } from "@/components/ui/switch";
import { Label } from "@/components/ui/label";
import { BrainCircuit } from "lucide-react";

export default function ChatPage() {
  const { messages, activeSources, isLoading, useReasoning, setUseReasoning, send } = useRagChat(false);
  const [isSidebarOpen, setIsSidebarOpen] = useState(true);

  return (
    <div className="flex h-full w-full overflow-hidden bg-background">
      <div className={`flex flex-col flex-1 min-w-0 transition-all duration-300 ${isSidebarOpen ? 'w-3/4' : 'w-full'}`}>
        <div className="p-4 bg-blue-500/10 border-b border-blue-500/20 text-blue-600 text-xs font-medium flex items-center justify-between">
          <div className="flex items-center gap-2">
            <div className="w-2 h-2 bg-blue-500 rounded-full" />
            Enterprise mode active (single collection)
          </div>
          <div className="flex items-center gap-3 bg-blue-500/5 px-3 py-1.5 rounded-lg border border-blue-500/10">
            <div className="flex items-center gap-2">
              <BrainCircuit className="w-3.5 h-3.5" />
              <Label htmlFor="reasoning-toggle" className="cursor-pointer">Force Multi-Hop Reasoning</Label>
            </div>
            <Switch
              id="reasoning-toggle"
              checked={useReasoning}
              onCheckedChange={setUseReasoning}
              className="data-[state=checked]:bg-blue-500"
            />
          </div>
        </div>
        <ChatInterface
          messages={messages}
          onSendMessage={send}
          isLoading={isLoading}
          onToggleSidebar={() => setIsSidebarOpen(!isSidebarOpen)}
        />
      </div>

      {isSidebarOpen && (
        <div className="w-1/4 border-l border-border bg-muted/30 hidden md:block">
          <SourcePanel sources={activeSources} />
        </div>
      )}
    </div>
  );
}
