export interface SearchResult {
  id?: string;
  content: string;
  metadata: Record<string, string | number | boolean | undefined>;
  score: number;
  dense_score?: number;
  bm25_score?: number;
  rrf_score?: number;
  pagerank_score?: number;
  boosted_score?: number;
}

export interface TraceStep {
  type: "thought" | "observation";
  step: number;
  reasoning?: string;
  action?: string;
  action_input?: Record<string, unknown>;
  confidence?: number;
  tool?: string;
  result_summary?: string;
  latency_ms?: number;
}

export interface ReActTrace {
  query?: string;
  final_answer?: string;
  final_confidence?: number;
  hops: number;
  stopped_reason: string;
}

export interface PipelineTrace {
  latencies: Record<string, number>;
  model: string;
  cache_hit: boolean;
  crag_path: string;
  shard_stats?: Record<string, unknown> | null;
}

export interface Message {
  id: string;
  role: "user" | "assistant";
  content: string;
  timestamp: string;
  sources?: SearchResult[];
  trace?: PipelineTrace;
  reasoningTrace?: TraceStep[];
  finalTrace?: ReActTrace;
  isError?: boolean;
}

export interface QueryRequest {
  query: string;
  session_id: string;
  stream?: boolean;
  use_sharding?: boolean;
  use_reasoning?: boolean;
}

/** One server-sent event from /api/v1/query. */
export interface StreamChunk {
  type?: "thought" | "observation" | "trace";
  token?: string;
  done?: boolean;
  error?: string;
  sources?: SearchResult[];
  trace?: PipelineTrace | ReActTrace;
  // thought / observation fields
  step?: number;
  reasoning?: string;
  action?: string;
  action_input?: Record<string, unknown>;
  confidence?: number;
  tool?: string;
  result_summary?: string;
  latency_ms?: number;
}

export interface HealthStatus {
  status: string;
  chroma?: string;
  redis?: string;
  neo4j?: string;
  model?: string;
  [key: string]: unknown;
}

export interface UploadResult {
  filename: string;
  status: "indexed" | "duplicate";
  sharded: boolean;
  chunks: number;
  document_id: string;
}

export interface PageRankStats {
  total_nodes: number;
  total_edges: number;
  density: number;
  computed: boolean;
  top: { id: string; score: number; citations: number }[];
}
