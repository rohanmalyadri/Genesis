"use client";

import { useState } from "react";
import { Card, CardHeader, CardTitle, CardContent } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Network, Share2, TrendingUp, Info } from "lucide-react";
import { api } from "@/lib/api";
import { toast } from "sonner";

export default function PageRankPage() {
  const [isComputing, setIsComputing] = useState(false);

  // Mock data for the citation graph
  const stats = {
    totalNodes: 1240,
    totalEdges: 3420,
    topCitations: [
      { id: "https://openai.com/research/", score: 0.892, citations: 45 },
      { id: "https://arxiv.org/pdf/2301.12345", score: 0.754, citations: 32 },
      { id: "internal://Section-4.2", score: 0.612, citations: 28 },
      { id: "https://google.com/deepmind/", score: 0.543, citations: 21 },
    ]
  };

  const handleCompute = async () => {
    setIsComputing(true);
    try {
      await api.triggerPageRank();
      toast.success("PageRank computation queued successfully!");
    } catch (error) {
      toast.error("Failed to trigger PageRank job.");
      console.error(error);
    } finally {
      setIsComputing(false);
    }
  };

  return (
    <div className="max-w-6xl mx-auto p-8 space-y-8">
      <div className="flex justify-between items-start">
        <div className="space-y-2">
          <h1 className="text-3xl font-bold">Citation Graph & PageRank</h1>
          <p className="text-muted-foreground">Analyze document authority using link-based analysis.</p>
        </div>
        <Button onClick={handleCompute} disabled={isComputing}>
          <Network className={`w-4 h-4 mr-2 ${isComputing ? 'animate-pulse' : ''}`} />
          {isComputing ? "Computing..." : "Run PageRank Calculation"}
        </Button>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
        <Card className="bg-primary/5 border-primary/20">
          <CardHeader className="pb-2">
            <CardTitle className="text-sm font-medium text-muted-foreground">Total Nodes</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">{stats.totalNodes}</div>
            <p className="text-xs text-muted-foreground mt-1">Unique documents & URLs</p>
          </CardContent>
        </Card>
        <Card className="bg-blue-500/5 border-blue-500/20">
          <CardHeader className="pb-2">
            <CardTitle className="text-sm font-medium text-muted-foreground">Total Citations</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">{stats.totalEdges}</div>
            <p className="text-xs text-muted-foreground mt-1">Extracted edges</p>
          </CardContent>
        </Card>
        <Card className="bg-orange-500/5 border-orange-500/20">
          <CardHeader className="pb-2">
            <CardTitle className="text-sm font-medium text-muted-foreground">Graph Density</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">0.0022</div>
            <p className="text-xs text-muted-foreground mt-1">Connectivity ratio</p>
          </CardContent>
        </Card>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 gap-8">
        <Card className="rounded-3xl shadow-sm">
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <TrendingUp className="w-5 h-5 text-primary" />
              Top Authority Nodes (PageRank)
            </CardTitle>
          </CardHeader>
          <CardContent className="space-y-4">
            {stats.topCitations.map((item, i) => (
              <div key={item.id} className="flex items-center justify-between p-4 bg-muted/30 rounded-2xl border border-transparent hover:border-border transition-all">
                <div className="flex items-center gap-3">
                  <div className="w-8 h-8 rounded-full bg-primary/10 flex items-center justify-center text-primary font-bold text-xs">
                    {i + 1}
                  </div>
                  <div className="max-w-[200px]">
                    <p className="text-sm font-medium truncate">{item.id}</p>
                    <p className="text-[10px] text-muted-foreground">Citations: {item.citations}</p>
                  </div>
                </div>
                <div className="text-right">
                  <div className="text-lg font-bold text-primary">{(item.score * 100).toFixed(1)}%</div>
                  <p className="text-[10px] text-muted-foreground uppercase tracking-wider">Score</p>
                </div>
              </div>
            ))}
          </CardContent>
        </Card>

        <Card className="rounded-3xl shadow-sm border-dashed">
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <Info className="w-5 h-5 text-blue-500" />
              Graph Methodology
            </CardTitle>
          </CardHeader>
          <CardContent className="space-y-6">
            <div className="space-y-4">
              <div className="flex gap-4">
                <div className="p-2 bg-blue-500/10 rounded-lg h-fit">
                  <Share2 className="w-4 h-4 text-blue-600" />
                </div>
                <div>
                  <h4 className="text-sm font-bold">Weighted Edges</h4>
                  <p className="text-xs text-muted-foreground leading-relaxed">
                    Hyperlinks (1.0), Cross-refs (0.8), and Footnotes (0.6) are extracted during ingestion. 
                    Repeated citations are capped at 3.0 per pair.
                  </p>
                </div>
              </div>

              <div className="flex gap-4">
                <div className="p-2 bg-orange-500/10 rounded-lg h-fit">
                  <Network className="w-4 h-4 text-orange-600" />
                </div>
                <div>
                  <h4 className="text-sm font-bold">Normalisation</h4>
                  <p className="text-xs text-muted-foreground leading-relaxed">
                    URLs are canonicalized (stripping query params) to ensure authority isn&apos;t fragmented 
                    across tracking links.
                  </p>
                </div>
              </div>
            </div>

            <div className="p-4 bg-muted rounded-2xl">
              <h4 className="text-xs font-bold uppercase tracking-widest text-muted-foreground mb-2">Edge Storage (Redis)</h4>
              <code className="text-[10px] block font-mono text-primary">
                ZADD citations:doc_1 1.0 https://google.com<br/>
                RPUSH citation_graph:edges &quot;doc_1,https://google.com,1.0&quot;
              </code>
            </div>
          </CardContent>
        </Card>
      </div>
    </div>
  );
}
