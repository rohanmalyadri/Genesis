"use client";

import { SearchResult } from "@/lib/types";
import { Card, CardHeader, CardTitle, CardContent } from "./ui/card";
import { Progress } from "./ui/progress";
import { ScrollArea } from "./ui/scroll-area";
import { FileText, ExternalLink, Hash, Info } from "lucide-react";
import { motion, AnimatePresence } from "framer-motion";
import { Badge } from "./ui/badge";

interface SourcePanelProps {
  sources: SearchResult[];
}

export function SourcePanel({ sources }: SourcePanelProps) {
  const getScoreColor = (score: number) => {
    if (score > 0.8) return "bg-green-500";
    if (score > 0.5) return "bg-amber-500";
    return "bg-red-500";
  };

  return (
    <div className="flex flex-col h-full">
      <div className="px-4 py-4 border-b border-border bg-background flex items-center justify-between">
        <div className="flex items-center gap-2">
          <Hash className="w-5 h-5 text-muted-foreground" />
          <h2 className="font-semibold text-sm">Relevant Sources</h2>
        </div>
        <Badge variant="outline" className="text-[10px]">
          {sources.length} Found
        </Badge>
      </div>

      <ScrollArea className="flex-1 p-4">
        <AnimatePresence mode="popLayout">
          <div className="space-y-4">
            {sources.length === 0 ? (
              <div className="flex flex-col items-center justify-center py-12 text-center text-muted-foreground opacity-50">
                <Info className="w-10 h-10 mb-2" />
                <p className="text-xs">No sources retrieved yet.</p>
              </div>
            ) : (
              sources.map((source, index) => (
                <motion.div
                  key={source.id || index}
                  id={`source-${index + 1}`}
                  initial={{ opacity: 0, x: 20 }}
                  animate={{ opacity: 1, x: 0 }}
                  exit={{ opacity: 0, scale: 0.95 }}
                  transition={{ delay: index * 0.1 }}
                >
                  <Card className="overflow-hidden border-border/50 hover:border-primary/50 transition-colors cursor-pointer group">
                    <CardHeader className="p-3 pb-2 flex flex-row items-center justify-between space-y-0">
                      <div className="flex items-center gap-2 overflow-hidden">
                        <FileText className="w-4 h-4 text-primary flex-shrink-0" />
                        <CardTitle className="text-xs truncate font-medium">
                          {source.metadata.filename || "Untitled Document"}
                        </CardTitle>
                      </div>
                      <ExternalLink className="w-3 h-3 text-muted-foreground group-hover:text-primary transition-colors" />
                    </CardHeader>
                    <CardContent className="p-3 pt-0 space-y-3">
                      <div className="space-y-1">
                        <div className="flex justify-between text-[10px] text-muted-foreground">
                          <span>Relevance Score</span>
                          <span className="font-mono">{(source.score * 100).toFixed(0)}%</span>
                        </div>
                        <Progress 
                          value={source.score * 100} 
                          className="h-1" 
                          indicatorClassName={getScoreColor(source.score)}
                        />
                      </div>
                      <p className="text-[11px] leading-relaxed text-muted-foreground line-clamp-3 italic">
                        &quot;...{source.content.slice(0, 150)}...&quot;
                      </p>
                      <div className="flex flex-wrap gap-1">
                        {source.metadata.source_type && (
                          <Badge variant="outline" className="text-[9px] py-0 px-1 capitalize">
                            {source.metadata.source_type}
                          </Badge>
                        )}
                        <Badge variant="outline" className="text-[9px] py-0 px-1">
                          Page {source.metadata.page || 1}
                        </Badge>
                      </div>
                    </CardContent>
                  </Card>
                </motion.div>
              ))
            )}
          </div>
        </AnimatePresence>
      </ScrollArea>
    </div>
  );
}
