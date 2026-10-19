/* eslint-disable @typescript-eslint/no-explicit-any */
export interface SearchResult {
  id?: string;
  content: string;
  metadata: Record<string, any>;
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
  action_input?: Record<string, any>;
  confidence?: number;
  tool?: string;
  result_summary?: string;
  latency_ms?: number;
  [key: string]: any;
}

export interface ReActTrace {
  query?: string;
  final_answer?: string;
  final_confidence?: number;
  hops: number;
  stopped_reason: string;
  [key: string]: any;
}

export interface PipelineTrace {
  latencies: Record<string, number>;
  model: string;
  cache_hit: boolean;
  crag_path: string;
  shard_stats?: Record<string, any> | null;
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
}

export interface QueryRequest {
  query: string;
  session_id: string;
  stream?: boolean;
  use_sharding?: boolean;
  use_reasoning?: boolean;
}

export interface StreamChunk {
  type?: string;
  token?: string;
  done?: boolean;
  error?: string;
  sources?: SearchResult[];
  trace?: any;
  [key: string]: any;
}
