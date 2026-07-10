"use client";

import { useState, useEffect, Suspense } from "react";
import { useSearchParams } from "next/navigation";
import { api } from "@/lib/api";
import { SearchResult } from "@/lib/types";
import { Input } from "@/components/ui/input";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Search, Loader2, Info, Building2, Layers, Network, BrainCircuit } from "lucide-react";
import { Switch } from "@/components/ui/switch";
import { Label } from "@/components/ui/label";

function SearchPageContent() {
  const searchParams = useSearchParams();
  const initialQuery = searchParams.get("q") || "";
  
  const [query, setQuery] = useState(initialQuery);
  const [loading, setLoading] = useState(false);
  const [hasSearched, setHasSearched] = useState(false);
  const [useReasoning, setUseReasoning] = useState(false);
  const [decomposedQueries, setDecomposedQueries] = useState<string[]>([]);
  
  const [results, setResults] = useState<{
    enterprise: SearchResult[];
    sharding: SearchResult[];
    pageRank: SearchResult[];
  }>({
    enterprise: [],
    sharding: [],
    pageRank: []
  });
  
  const [latencies, setLatencies] = useState({
    enterprise: 0,
    sharding: 0,
    pageRank: 0
  });

  const handleSearch = async (overrideQuery?: string) => {
    const q = overrideQuery || query;
    if (!q) return;
    setLoading(true);
    setHasSearched(true);
    
    try {
      const measure = async (promise: Promise<{ results: SearchResult[] }>) => {
        const start = performance.now();
        const result = await promise;
        return { result, latency: performance.now() - start };
      };

      const [ent, shard, pr] = await Promise.all([
        measure(api.search(q, 5, false, { authority_mode: false, use_reasoning: useReasoning })),
        measure(api.search(q, 5, true, { authority_mode: false, use_reasoning: useReasoning })),
        measure(api.search(q, 5, false, { authority_mode: true, use_reasoning: useReasoning }))
      ]);

      if (ent.result.decomposed_queries) {
        setDecomposedQueries(ent.result.decomposed_queries);
      }

      setResults({
        enterprise: ent.result.results,
        sharding: shard.result.results,
        pageRank: pr.result.results
      });
      
      setLatencies({
        enterprise: ent.latency,
        sharding: shard.latency,
        pageRank: pr.latency
      });
    } catch (error) {
      console.error(error);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    if (initialQuery) {
      setTimeout(() => {
        handleSearch(initialQuery);
      }, 0);
    }
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [initialQuery]);

  const ResultCard = ({ res }: { res: SearchResult }) => (
    <div className="p-4 bg-muted/30 rounded-xl border hover:border-primary/50 transition-colors text-left space-y-3">
      <p className="text-xs leading-relaxed italic text-muted-foreground line-clamp-3">
        &quot;{res.content}&quot;
      </p>
      <div className="grid grid-cols-2 gap-2 text-[10px] font-mono">
        <div>Dense: <span className="text-primary">{res.dense_score?.toFixed(4) || "0.0000"}</span></div>
        <div>RRF: <span className="text-primary">{res.rrf_score?.toFixed(4) || "0.0000"}</span></div>
        <div>PageRank: <span className="text-primary">{res.pagerank_score?.toFixed(4) || "0.0000"}</span></div>
        <div>Boosted: <span className="text-primary font-bold">{res.boosted_score?.toFixed(4) || "0.0000"}</span></div>
      </div>
      <div className="flex gap-1 pt-1">
        <Badge variant="outline" className="text-[9px]">{res.metadata.filename as string || "unknown"}</Badge>
        <Badge variant="secondary" className="text-[9px]">P{res.metadata.page as number || 1}</Badge>
      </div>
    </div>
  );

  return (
    <div className="max-w-7xl mx-auto p-8 space-y-8 h-screen overflow-y-auto">
      <div className="space-y-2">
        <h1 className="text-3xl font-bold">3-Way RAG Comparison</h1>
        <p className="text-muted-foreground">Compare retrieval accuracy and latency across Enterprise, Multi-Tenant, and Authority Boosted modes.</p>
      </div>

      <div className="flex gap-4">
        <div className="relative flex-1">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-muted-foreground" />
          <Input 
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            onKeyDown={(e) => e.key === 'Enter' && handleSearch()}
            placeholder="Enter search query or document name..." 
            className="pl-10 h-12"
          />
        </div>
        <Button onClick={() => handleSearch()} disabled={loading} className="h-12 px-8">
          {loading ? <Loader2 className="w-4 h-4 animate-spin mr-2" /> : <Search className="w-4 h-4 mr-2" />}
          Run Comparison
        </Button>
      </div>

      <div className="flex items-center gap-2 bg-primary/5 p-3 rounded-xl border border-primary/10 w-fit">
        <BrainCircuit className="w-4 h-4 text-primary" />
        <Label htmlFor="reasoning-mode" className="text-sm font-medium">Multi-Hop Reasoning</Label>
        <Switch 
          id="reasoning-mode" 
          checked={useReasoning} 
          onCheckedChange={setUseReasoning} 
        />
        <span className="text-[10px] text-muted-foreground ml-2">Engages LLM to decompose complex queries</span>
      </div>

      {decomposedQueries.length > 0 && hasSearched && useReasoning && (
        <div className="flex flex-wrap gap-2 animate-in fade-in slide-in-from-top-2 duration-300">
          <span className="text-xs font-medium text-muted-foreground py-1">Agent Thought:</span>
          {decomposedQueries.map((dq, i) => (
            <Badge key={i} variant="secondary" className="text-[10px] bg-primary/10 text-primary hover:bg-primary/20 border-primary/20">
              {dq}
            </Badge>
          ))}
        </div>
      )}

      {!hasSearched ? (
        <div className="h-64 flex flex-col items-center justify-center text-muted-foreground border-2 border-dashed rounded-3xl">
          <Info className="w-8 h-8 mb-4 opacity-50" />
          <p>Run a query to benchmark the RAG architectures.</p>
        </div>
      ) : (
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-6 pb-20">
          {/* Column 1: Enterprise */}
          <div className="space-y-4">
            <div className="p-4 bg-blue-500/10 border border-blue-500/20 rounded-2xl">
              <div className="flex items-center justify-between mb-2">
                <h3 className="font-bold flex items-center gap-2 text-blue-600">
                  <Building2 className="w-4 h-4" /> Enterprise RAG
                </h3>
                <span className="text-xs font-mono bg-blue-500/20 px-2 py-1 rounded text-blue-700">{latencies.enterprise.toFixed(0)}ms</span>
              </div>
              <p className="text-[10px] text-muted-foreground">Standard single collection retrieval.</p>
            </div>
            <div className="space-y-3">
              {results.enterprise.map((res, i) => <ResultCard key={`ent-${i}`} res={res} />)}
              {results.enterprise.length === 0 && !loading && <div className="text-xs text-center p-4 text-muted-foreground">No results found.</div>}
            </div>
          </div>

          {/* Column 2: Sharding */}
          <div className="space-y-4">
            <div className="p-4 bg-orange-500/10 border border-orange-500/20 rounded-2xl">
              <div className="flex items-center justify-between mb-2">
                <h3 className="font-bold flex items-center gap-2 text-orange-600">
                  <Layers className="w-4 h-4" /> Multi-Tenant
                </h3>
                <span className="text-xs font-mono bg-orange-500/20 px-2 py-1 rounded text-orange-700">{latencies.sharding.toFixed(0)}ms</span>
              </div>
              <p className="text-[10px] text-muted-foreground">16x Chroma Sharding architecture.</p>
            </div>
            <div className="space-y-3">
              {results.sharding.map((res, i) => <ResultCard key={`shard-${i}`} res={res} />)}
              {results.sharding.length === 0 && !loading && <div className="text-xs text-center p-4 text-muted-foreground">No results found.</div>}
            </div>
          </div>

          {/* Column 3: PageRank */}
          <div className="space-y-4">
            <div className="p-4 bg-green-500/10 border border-green-500/20 rounded-2xl">
              <div className="flex items-center justify-between mb-2">
                <h3 className="font-bold flex items-center gap-2 text-green-600">
                  <Network className="w-4 h-4" /> PageRank Boost
                </h3>
                <span className="text-xs font-mono bg-green-500/20 px-2 py-1 rounded text-green-700">{latencies.pageRank.toFixed(0)}ms</span>
              </div>
              <p className="text-[10px] text-muted-foreground">Graph-based authority normalization.</p>
            </div>
            <div className="space-y-3">
              {results.pageRank.map((res, i) => <ResultCard key={`pr-${i}`} res={res} />)}
              {results.pageRank.length === 0 && !loading && <div className="text-xs text-center p-4 text-muted-foreground">No results found.</div>}
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

export default function SearchPage() {
  return (
    <Suspense fallback={<div className="p-8 text-center"><Loader2 className="w-6 h-6 animate-spin mx-auto" /></div>}>
      <SearchPageContent />
    </Suspense>
  );
}
