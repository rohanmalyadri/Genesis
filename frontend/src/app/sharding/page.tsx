"use client";

import { useState } from "react";
import { ChatInterface } from "@/components/chat-interface";
import { SourcePanel } from "@/components/source-panel";
import { useRagChat } from "@/lib/use-rag-chat";
import { Switch } from "@/components/ui/switch";
import { Label } from "@/components/ui/label";
import { BrainCircuit } from "lucide-react";

export default function ShardingPage() {
  const { messages, activeSources, isLoading, useReasoning, setUseReasoning, send } = useRagChat(true);
  const [isSidebarOpen, setIsSidebarOpen] = useState(true);

  return (
    <div className="flex h-full w-full overflow-hidden bg-background">
      <div className={`flex flex-col flex-1 min-w-0 transition-all duration-300 ${isSidebarOpen ? 'w-3/4' : 'w-full'}`}>
        <div className="p-4 bg-orange-500/10 border-b border-orange-500/20 text-orange-600 text-xs font-medium flex items-center justify-between">
          <div className="flex items-center gap-2">
            <div className="w-2 h-2 bg-orange-500 rounded-full animate-pulse" />
            Multi-Tenant Sharding Architecture Active (16x Chroma Shards)
          </div>
          <div className="flex items-center gap-3 bg-orange-500/5 px-3 py-1.5 rounded-lg border border-orange-500/10">
            <div className="flex items-center gap-2">
              <BrainCircuit className="w-3.5 h-3.5" />
              <Label htmlFor="reasoning-toggle-sharding" className="cursor-pointer">Force Multi-Hop Reasoning</Label>
            </div>
            <Switch
              id="reasoning-toggle-sharding"
              checked={useReasoning}
              onCheckedChange={setUseReasoning}
              className="data-[state=checked]:bg-orange-500"
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
