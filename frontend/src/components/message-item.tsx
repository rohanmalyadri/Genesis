"use client";

import { Message } from "@/lib/types";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import { Badge } from "./ui/badge";
import { Bot, User, Copy, RotateCcw, ThumbsUp, ThumbsDown, Check } from "lucide-react";
import { useState } from "react";
import { Button } from "./ui/button";
import { toast } from "sonner";
import { ReasoningTrace } from "./ReasoningTrace";

interface MessageItemProps {
  message: Message;
}

export function MessageItem({ message }: MessageItemProps) {
  const isAssistant = message.role === "assistant";
  const [copied, setCopied] = useState(false);

  const handleCopy = () => {
    navigator.clipboard.writeText(message.content);
    setCopied(true);
    toast.success("Copied to clipboard");
    setTimeout(() => setCopied(false), 2000);
  };

  const renderContent = (content: string) => {
    // Regex to find [N] patterns
    const parts = content.split(/(\[\d+\])/g);
    return parts.map((part, i) => {
      const match = part.match(/\[(\d+)\]/);
      if (match) {
        const num = match[1];
        return (
          <Badge 
            key={i} 
            variant="secondary" 
            className="mx-0.5 bg-blue-500/10 text-blue-500 hover:bg-blue-500/20 cursor-pointer text-[10px] py-0 px-1"
            onClick={() => {
              const element = document.getElementById(`source-${num}`);
              element?.scrollIntoView({ behavior: 'smooth', block: 'center' });
              element?.classList.add('ring-2', 'ring-primary');
              setTimeout(() => element?.classList.remove('ring-2', 'ring-primary'), 2000);
            }}
          >
            {num}
          </Badge>
        );
      }
      return <ReactMarkdown key={i} remarkPlugins={[remarkGfm]} className="inline">{part}</ReactMarkdown>;
    });
  };

  return (
    <div className={`flex gap-4 ${isAssistant ? "" : "flex-row-reverse"}`}>
      <div className={`flex-shrink-0 w-9 h-9 rounded-full flex items-center justify-center ${
        isAssistant ? "bg-primary text-primary-foreground shadow-lg" : "bg-muted border border-border"
      }`}>
        {isAssistant ? <Bot className="w-5 h-5" /> : <User className="w-5 h-5" />}
      </div>

      <div className={`flex flex-col gap-2 max-w-[85%] ${!isAssistant && "items-end"}`}>
        <div className={`px-4 py-3 rounded-2xl text-sm leading-relaxed shadow-sm ${
          isAssistant 
            ? "bg-muted/50 border border-border" 
            : "bg-primary text-primary-foreground"
        }`}>
          {isAssistant ? (
             <div className="prose prose-sm dark:prose-invert max-w-none">
                {renderContent(message.content)}
                {isAssistant && message.content === "" && !message.reasoningTrace && (
                  <span className="inline-block w-2 h-4 bg-primary animate-pulse ml-1" />
                )}
                {isAssistant && message.reasoningTrace && (
                  <ReasoningTrace 
                    steps={message.reasoningTrace} 
                    finalTrace={message.finalTrace}
                    isReasoning={!message.finalTrace} 
                  />
                )}
              </div>
          ) : (
            message.content
          )}
        </div>

        {isAssistant && message.content && (
          <div className="flex items-center gap-1 ml-1">
            <Button variant="ghost" size="icon" className="w-8 h-8 hov" onClick={handleCopy}>
              {copied ? <Check className="w-3.5 h-3.5 text-green-500" /> : <Copy className="w-3.5 h-3.5" />}
            </Button>
            <Button variant="ghost" size="icon" className="w-8 h-8">
              <RotateCcw className="w-3.5 h-3.5" />
            </Button>
            <Button variant="ghost" size="icon" className="w-8 h-8">
              <ThumbsUp className="w-3.5 h-3.5" />
            </Button>
            <Button variant="ghost" size="icon" className="w-8 h-8">
              <ThumbsDown className="w-3.5 h-3.5" />
            </Button>
            {message.trace && (
               <span className="text-[10px] text-muted-foreground ml-2">
                 {message.trace.model} • {message.trace.latencies.llm_stream?.toFixed(0)}ms
               </span>
            )}
          </div>
        )}
        
        <span className="text-[10px] text-muted-foreground px-2">
          {new Date(message.timestamp).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}
        </span>
      </div>
    </div>
  );
}
