import { QueryRequest, SearchResult, StreamChunk } from "./types";

const BASE_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8005";

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${BASE_URL}${path}`, init);
  if (!res.ok) throw new Error(`${res.status} ${res.statusText}`);
  return res.json();
}

export const api = {
  health: () => request<{ status: string; [key: string]: unknown }>("/health/"),

  search: (
    q: string,
    topK = 10,
    useSharding = true,
    opts: { authority_mode?: boolean; use_reasoning?: boolean } = {}
  ) => {
    const params = new URLSearchParams({
      q,
      top_k: String(topK),
      use_sharding: String(useSharding),
      authority_mode: String(!!opts.authority_mode),
      use_reasoning: String(!!opts.use_reasoning),
    });
    return request<{
      query: string;
      decomposed_queries?: string[] | null;
      results: SearchResult[];
    }>(`/api/v1/search/?${params}`);
  },

  upload: (file: File, useSharding = true) => {
    const form = new FormData();
    form.append("file", file);
    form.append("use_sharding", String(useSharding));
    return request<{ filename: string; status: string; sharded: boolean }>(
      "/api/v1/ingest/",
      { method: "POST", body: form }
    );
  },

  triggerPageRank: () =>
    request<{ status: string; message: string; task_id: string }>(
      "/api/v1/pagerank/trigger",
      { method: "POST" }
    ),
};

export async function* streamQuery(body: QueryRequest): AsyncGenerator<StreamChunk> {
  const res = await fetch(`${BASE_URL}/api/v1/query/`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  if (!res.ok || !res.body) throw new Error(`Query failed: ${res.status}`);

  const reader = res.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";
  while (true) {
    const { done, value } = await reader.read();
    if (done) break;
    buffer += decoder.decode(value, { stream: true });
    const events = buffer.split("\n\n");
    buffer = events.pop() ?? "";
    for (const evt of events) {
      const line = evt.trim();
      if (!line.startsWith("data:")) continue;
      try {
        yield JSON.parse(line.slice(5).trim());
      } catch {
        /* ignore malformed chunk */
      }
    }
  }
}
