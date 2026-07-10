"use client";

import { useState, useRef, useEffect } from "react";
import { Message } from "@/lib/types";
import { Button } from "./ui/button";
import { Input } from "./ui/input";
import { ScrollArea } from "./ui/scroll-area";
import { MessageItem } from "./message-item";
import { Send, PanelRight, Bot } from "lucide-react";

interface ChatInterfaceProps {
  messages: Message[];
  onSendMessage: (query: string) => void;
  isLoading: boolean;
  onToggleSidebar: () => void;
}

export function ChatInterface({ messages, onSendMessage, isLoading, onToggleSidebar }: ChatInterfaceProps) {
  const [input, setInput] = useState("");
  const scrollRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (scrollRef.current) {
      scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
    }
  }, [messages]);

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (input.trim() && !isLoading) {
      onSendMessage(input);
      setInput("");
    }
  };

  return (
    <div className="flex flex-col h-full relative">
      <header className="flex items-center justify-between px-6 py-4 border-b border-border bg-background/80 backdrop-blur-md sticky top-0 z-10">
        <div className="flex items-center gap-2">
          <Bot className="w-6 h-6 text-primary" />
          <h1 className="text-lg font-semibold">Production RAG Assistant</h1>
        </div>
        <Button variant="ghost" size="icon" onClick={onToggleSidebar}>
          <PanelRight className="w-5 h-5" />
        </Button>
      </header>

      <ScrollArea className="flex-1 p-6" ref={scrollRef}>
        <div className="max-w-3xl mx-auto space-y-8">
          {messages.length === 0 && (
            <div className="flex flex-col items-center justify-center h-[60vh] text-center space-y-4">
              <Bot className="w-16 h-16 text-muted-foreground/20" />
              <h2 className="text-2xl font-bold text-muted-foreground">How can I help you today?</h2>
              <p className="text-muted-foreground max-w-sm">
                Ask me anything about your uploaded documents. I&apos;ll provide cited answers with real-time sources.
              </p>
            </div>
          )}
          {messages.map((msg) => (
            <MessageItem key={msg.id} message={msg} />
          ))}
          {isLoading && messages[messages.length - 1]?.role !== 'assistant' && (
             <div className="flex gap-4 animate-pulse">
                <div className="w-8 h-8 rounded-full bg-muted" />
                <div className="space-y-2 flex-1">
                  <div className="h-4 bg-muted rounded w-1/4" />
                  <div className="h-4 bg-muted rounded w-3/4" />
                </div>
             </div>
          )}
        </div>
      </ScrollArea>

      <div className="p-6 border-t border-border bg-background/80 backdrop-blur-md">
        <form onSubmit={handleSubmit} className="max-w-3xl mx-auto relative">
          <Input
            value={input}
            onChange={(e) => setInput(e.target.value)}
            placeholder="Ask a question..."
            className="pr-12 py-6 text-base rounded-2xl shadow-lg focus-visible:ring-primary/20"
            disabled={isLoading}
          />
          <Button 
            type="submit" 
            size="icon" 
            className="absolute right-2 top-1/2 -translate-y-1/2 rounded-xl transition-transform active:scale-95"
            disabled={isLoading || !input.trim()}
          >
            <Send className="w-5 h-5" />
          </Button>
        </form>
        <p className="text-[10px] text-center text-muted-foreground mt-4">
          AI can make mistakes. Check important information.
        </p>
      </div>
    </div>
  );
}
