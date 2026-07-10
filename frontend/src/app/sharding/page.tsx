"use client";

import { useState, useRef } from "react";
import { ChatInterface } from "@/components/chat-interface";
import { SourcePanel } from "@/components/source-panel";
import { Message, SearchResult } from "@/lib/types";
import { streamQuery } from "@/lib/api";
import { v4 as uuidv4 } from "uuid";
import { Switch } from "@/components/ui/switch";
import { Label } from "@/components/ui/label";
import { BrainCircuit } from "lucide-react";

export default function ShardingPage() {
  const [messages, setMessages] = useState<Message[]>([]);
  const [activeSources, setActiveSources] = useState<SearchResult[]>([]);
  const [isSidebarOpen, setIsSidebarOpen] = useState(true);
  const [isLoading, setIsLoading] = useState(false);
  const [useReasoning, setUseReasoning] = useState(false);
  const sessionId = useRef(uuidv4()).current;

  const handleSendMessage = async (query: string) => {
    const userMsg: Message = {
      id: uuidv4(),
      role: "user",
      content: query,
      timestamp: new Date().toISOString(),
    };

    setMessages((prev) => [...prev, userMsg]);
    setIsLoading(true);

    const assistantMsgId = uuidv4();
    let currentContent = "";
    
    try {
      const stream = streamQuery({
        query,
        session_id: sessionId,
        stream: true,
        use_sharding: true, // Explicitly use sharding
        use_reasoning: useReasoning,
      });

      for await (const chunk of stream) {
        if (chunk.token) {
          currentContent += chunk.token;
          setMessages((prev) => {
            const last = prev[prev.length - 1];
            if (last?.id === assistantMsgId) {
              return [...prev.slice(0, -1), { ...last, content: currentContent }];
            } else {
              return [
                ...prev,
                {
                  id: assistantMsgId,
                  role: "assistant",
                  content: currentContent,
                  timestamp: new Date().toISOString(),
                },
              ];
            }
          });
        }

        if (chunk.sources) {
          setActiveSources(chunk.sources);
          setMessages((prev) => {
            const last = prev[prev.length - 1];
            if (last?.id === assistantMsgId) {
              return [...prev.slice(0, -1), { ...last, sources: chunk.sources, trace: chunk.trace }];
            }
            return prev;
          });
        }
      }
    } catch (error) {
      console.error("Chat error:", error);
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <div className="flex h-screen w-full overflow-hidden bg-background">
      <div className={`flex flex-col flex-1 transition-all duration-300 ${isSidebarOpen ? 'w-3/4' : 'w-full'}`}>
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
          onSendMessage={handleSendMessage} 
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
