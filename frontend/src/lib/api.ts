import { HealthStatus, PageRankStats, QueryRequest, SearchResult, StreamChunk, UploadResult } from "./types";
import { loadSettings } from "./settings";

export const BASE_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

function headers(extra: Record<string, string> = {}): Record<string, string> {
  const key = process.env.NEXT_PUBLIC_API_KEY;
  return key ? { "X-API-Key": key, ...extra } : extra;
}

async function errorMessage(res: Response): Promise<string> {
  try {
    const body = await res.json();
    if (typeof body.detail === "string") return body.detail;
  } catch {
    /* not JSON */
  }
  return `${res.status} ${res.statusText}`;
}

async function request<T>(path: string, init: RequestInit = {}): Promise<T> {
  const res = await fetch(`${BASE_URL}${path}`, {
    ...init,
    headers: headers((init.headers as Record<string, string>) || {}),
  });
  if (!res.ok) throw new Error(await errorMessage(res));
  return res.json();
}

export const api = {
  health: () => request<HealthStatus>("/health/"),

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

  upload: (file: File, useSharding = true, chunkSize?: number) => {
    const form = new FormData();
    form.append("file", file);
    form.append("use_sharding", String(useSharding));
    if (chunkSize) form.append("chunk_size", String(chunkSize));
    return request<UploadResult>("/api/v1/ingest/", { method: "POST", body: form });
  },

  triggerPageRank: () =>
    request<{ status: string; message: string; result?: { nodes: number; edges: number } }>(
      "/api/v1/pagerank/trigger?inline=true",
      { method: "POST" }
    ),

  pageRankStats: () => request<PageRankStats>("/api/v1/pagerank/stats"),
};

/** Streams /api/v1/query as parsed server-sent events. Applies the saved Settings. */
export async function* streamQuery(body: QueryRequest): AsyncGenerator<StreamChunk> {
  const s = loadSettings();
  const res = await fetch(`${BASE_URL}/api/v1/query/`, {
    method: "POST",
    headers: headers({ "Content-Type": "application/json" }),
    body: JSON.stringify({
      ...body,
      model: s.model,
      top_k: s.topK[0],
      cache_ttl: s.cacheTtl[0],
      input_guard: s.inputGuard,
      content_filter: s.contentFilter,
      output_guard: s.outputGuard,
    }),
  });
  if (!res.ok || !res.body) throw new Error(await errorMessage(res));

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
        /* ignore a malformed event */
      }
    }
  }
}
