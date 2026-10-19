"use client";

import { useCallback, useRef, useState } from "react";
import { v4 as uuidv4 } from "uuid";
import { toast } from "sonner";
import { streamQuery } from "@/lib/api";
import { Message, PipelineTrace, ReActTrace, SearchResult, TraceStep } from "@/lib/types";

/** Shared chat logic for the Enterprise and Sharding pages. */
export function useRagChat(useSharding: boolean) {
  const [messages, setMessages] = useState<Message[]>([]);
  const [activeSources, setActiveSources] = useState<SearchResult[]>([]);
  const [isLoading, setIsLoading] = useState(false);
  const [useReasoning, setUseReasoning] = useState(false);
  const sessionId = useRef(uuidv4()).current;

  const send = useCallback(
    async (query: string) => {
      const assistantId = uuidv4();
      const now = () => new Date().toISOString();

      // create the assistant message on first update, then patch it
      const upsert = (patch: Partial<Message>) =>
        setMessages((prev) => {
          const i = prev.findIndex((m) => m.id === assistantId);
          if (i === -1) {
            return [...prev, { id: assistantId, role: "assistant", content: "", timestamp: now(), ...patch }];
          }
          const next = [...prev];
          next[i] = { ...next[i], ...patch };
          return next;
        });

      setMessages((prev) => [...prev, { id: uuidv4(), role: "user", content: query, timestamp: now() }]);
      setIsLoading(true);

      let content = "";
      const steps: TraceStep[] = [];
      try {
        for await (const chunk of streamQuery({
          query,
          session_id: sessionId,
          stream: true,
          use_sharding: useSharding,
          use_reasoning: useReasoning,
        })) {
          if (chunk.error) {
            upsert({ content: chunk.error, isError: true });
            toast.error(chunk.error);
            continue;
          }
          if (chunk.type === "thought" || chunk.type === "observation") {
            steps.push(chunk as TraceStep);
            upsert({ reasoningTrace: [...steps] });
            continue;
          }
          if (chunk.type === "trace") {
            upsert({ finalTrace: chunk.trace as ReActTrace });
            continue;
          }
          if (chunk.token) {
            content += chunk.token;
            upsert({ content });
          }
          if (chunk.sources) {
            setActiveSources(chunk.sources);
            upsert({ sources: chunk.sources, trace: chunk.trace as PipelineTrace });
          }
        }
      } catch (e) {
        const msg = e instanceof Error ? e.message : "Request failed";
        upsert({ content: `Sorry, the request failed: ${msg}`, isError: true });
        toast.error(`Could not reach the Genesis API: ${msg}`);
      } finally {
        setIsLoading(false);
      }
    },
    [sessionId, useSharding, useReasoning]
  );

  return { messages, activeSources, isLoading, useReasoning, setUseReasoning, send };
}
