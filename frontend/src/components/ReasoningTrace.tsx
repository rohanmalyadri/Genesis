/* eslint-disable @typescript-eslint/no-explicit-any */
"use client";

import { useState, useEffect, useRef } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { 
  Brain, 
  Database, 
  ChevronDown, 
  ChevronUp, 
  Clock, 
  AlertCircle, 
  CheckCircle2, 
  RefreshCcw,
  XCircle,
  Activity
} from "lucide-react";
import { Badge } from "./ui/badge";
import { Card } from "./ui/card";
import { TraceStep, ReActTrace } from "@/lib/types";
import * as d3 from "d3";

interface ReasoningTraceProps {
  steps: TraceStep[];
  finalTrace?: ReActTrace;
  isReasoning: boolean;
}

export function ReasoningTrace({ steps, finalTrace, isReasoning }: ReasoningTraceProps) {
  const [isOpen, setIsOpen] = useState(false);
  const scrollRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (isOpen && scrollRef.current) {
      scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
    }
  }, [steps, isOpen]);

  if (steps.length === 0) return null;

  const getConfidenceColor = (conf: number) => {
    const val = conf * 100;
    if (val <= 30) return "bg-red-500/10 text-red-600 border-red-500/20";
    if (val <= 60) return "bg-amber-500/10 text-amber-600 border-amber-500/20";
    if (val <= 85) return "bg-blue-500/10 text-blue-600 border-blue-500/20";
    return "bg-green-500/10 text-green-600 border-green-500/20";
  };

  const getStoppedReasonConfig = (reason: string) => {
    switch (reason) {
      case "confidence_threshold":
        return { icon: <CheckCircle2 className="w-4 h-4" />, text: `Confident after ${finalTrace?.hops} hops`, color: "text-green-600 bg-green-50" };
      case "max_hops":
        return { icon: <AlertCircle className="w-4 h-4" />, text: "Max hops reached", color: "text-amber-600 bg-amber-50" };
      case "no_new_info":
        return { icon: <RefreshCcw className="w-4 h-4" />, text: "No new information", color: "text-blue-600 bg-blue-50" };
      case "refusal":
        return { icon: <XCircle className="w-4 h-4" />, text: "Insufficient evidence", color: "text-red-600 bg-red-50" };
      default:
        return { icon: <Activity className="w-4 h-4" />, text: reason, color: "text-gray-600 bg-gray-50" };
    }
  };

  return (
    <div className="w-full my-4">
      <button 
        onClick={() => setIsOpen(!isOpen)}
        className="flex items-center gap-2 text-xs font-semibold text-muted-foreground hover:text-primary transition-colors mb-2 group"
      >
        <div className="flex -space-x-1">
          {isReasoning ? (
             <motion.div 
               animate={{ scale: [1, 1.2, 1] }} 
               transition={{ repeat: Infinity, duration: 2 }}
               className="w-2 h-2 rounded-full bg-blue-500" 
             />
          ) : (
            <Brain className="w-3.5 h-3.5" />
          )}
        </div>
        <span>Reasoning Trace ({steps.filter(s => s.type === "thought").length} hops)</span>
        {isOpen ? <ChevronUp className="w-3.5 h-3.5" /> : <ChevronDown className="w-3.5 h-3.5" />}
      </button>

      <AnimatePresence>
        {isOpen && (
          <motion.div
            initial={{ height: 0, opacity: 0 }}
            animate={{ height: "auto", opacity: 1 }}
            exit={{ height: 0, opacity: 0 }}
            className="overflow-hidden"
          >
            <Card className="p-4 bg-muted/30 border-border/50 space-y-4">
              <div 
                ref={scrollRef}
                className="max-h-[400px] overflow-y-auto pr-2 space-y-6 relative custom-scrollbar"
              >
                {steps.map((step, idx) => (
                  <motion.div 
                    key={`${step.step}-${step.type}-${idx}`}
                    initial={{ opacity: 0, x: -12 }}
                    animate={{ opacity: 1, x: 0 }}
                    transition={{ delay: 0.1 * idx }}
                    className="relative"
                  >
                    {step.type === "thought" ? (
                      <div className="flex flex-col gap-2 pl-4 border-l-2 border-blue-500/50">
                        <div className="flex items-center justify-between">
                          <div className="flex items-center gap-2">
                            <Brain className="w-4 h-4 text-blue-500" />
                            <span className="text-[11px] font-bold uppercase tracking-wider text-muted-foreground">
                              Step {step.step} · Thought
                            </span>
                          </div>
                          <div className="flex items-center gap-2">
                            <Badge variant="outline" className={`text-[10px] font-mono ${getConfidenceColor(step.confidence)}`}>
                              {(step.confidence * 100).toFixed(0)}% Conf
                            </Badge>
                            <code className="text-[10px] bg-muted px-1.5 py-0.5 rounded border border-border/50 text-blue-600 font-mono">
                              → {step.action}({Object.values(step.action_input)[0] || ""})
                            </code>
                          </div>
                        </div>
                        <p className="text-sm italic text-muted-foreground leading-relaxed">
                          {step.reasoning}
                        </p>
                      </div>
                    ) : (
                      <div className="flex flex-col gap-2 pl-4 border-l-2 border-teal-500/50 mt-2">
                        <div className="flex items-center justify-between">
                          <div className="flex items-center gap-2">
                            <Database className="w-4 h-4 text-teal-500" />
                            <span className="text-[11px] font-bold uppercase tracking-wider text-muted-foreground">
                              Step {step.step} · Observation ({step.tool})
                            </span>
                          </div>
                          {step.latency_ms && (
                            <div className="flex items-center gap-1 text-[10px] text-muted-foreground bg-muted px-2 py-0.5 rounded-full border border-border/50">
                              <Clock className="w-3 h-3" />
                              {step.latency_ms.toFixed(0)}ms
                            </div>
                          )}
                        </div>
                        <div className="text-xs text-muted-foreground bg-teal-50/30 dark:bg-teal-500/5 p-2 rounded border border-teal-500/10">
                          {step.result_summary}
                        </div>
                      </div>
                    )}

                    {/* Timeline connection */}
                    {idx < steps.length - 1 && (
                      <div className="absolute left-[-1px] top-[100%] h-6 w-0.5 bg-border flex items-center justify-center">
                         {steps[idx+1].type === "thought" && (
                           <span className="absolute left-4 text-[9px] text-muted-foreground whitespace-nowrap bg-background px-1 rounded border">
                              Hop {steps[idx+1].step} of {finalTrace?.hops || 5}
                           </span>
                         )}
                      </div>
                    )}
                  </motion.div>
                ))}

                {isReasoning && (
                  <div className="flex items-center gap-2 pl-4 py-2">
                    <span className="text-xs text-muted-foreground">Reasoning</span>
                    <motion.span
                      animate={{ opacity: [0, 1, 0] }}
                      transition={{ repeat: Infinity, duration: 1.5, times: [0, 0.5, 1] }}
                      className="flex gap-1"
                    >
                      <span className="w-1 h-1 rounded-full bg-muted-foreground" />
                      <span className="w-1 h-1 rounded-full bg-muted-foreground" />
                      <span className="w-1 h-1 rounded-full bg-muted-foreground" />
                    </motion.span>
                  </div>
                )}
              </div>

              {finalTrace && (
                <div className="pt-4 border-t border-border/50 flex flex-col gap-4">
                  <div className="flex items-center justify-between">
                    <div className={`flex items-center gap-2 px-3 py-1 rounded-full border ${getStoppedReasonConfig(finalTrace.stopped_reason).color} border-current/20 text-xs font-semibold`}>
                      {getStoppedReasonConfig(finalTrace.stopped_reason).icon}
                      {getStoppedReasonConfig(finalTrace.stopped_reason).text}
                    </div>
                    <div className="flex flex-col items-end">
                      <span className="text-[10px] text-muted-foreground uppercase font-bold tracking-tighter">Final Confidence</span>
                      <span className={`text-xl font-bold font-mono ${(finalTrace.final_confidence * 100) > 80 ? 'text-green-600' : 'text-primary'}`}>
                        {(finalTrace.final_confidence * 100).toFixed(0)}%
                      </span>
                    </div>
                  </div>

                  {/* D3 Graph Mini-map */}
                  <GraphMiniMap steps={steps} />
                </div>
              )}
            </Card>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
}

function GraphMiniMap({ steps }: { steps: TraceStep[] }) {
  const svgRef = useRef<SVGSVGElement>(null);
  const containerRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!svgRef.current || !containerRef.current) return;

    interface GraphNode extends d3.SimulationNodeDatum {
      id: string;
      type: string;
      val: number;
    }
    interface GraphLink extends d3.SimulationLinkDatum<GraphNode> {
      source: string | GraphNode;
      target: string | GraphNode;
      label: string;
    }

    // Extract entities and relationships from steps
    const nodes: GraphNode[] = [];
    const links: GraphLink[] = [];
    const nodeMap = new Map<string, GraphNode>();

    steps.forEach(step => {
      if (step.type === "observation" && typeof step.result_summary === "string") {
         // Crude extraction for the mini-map visualization
         // In a real app, the backend would provide a structured graph object
         if (step.tool === "graph_neighbors" || step.tool === "graph_path" || step.tool === "entity_context") {
            const matches = step.result_summary.match(/'([^']+)'/g) || [];
            matches.forEach(m => {
              const name = m.replace(/'/g, "");
              if (!nodeMap.has(name)) {
                const node = { id: name, type: "Entity", val: 1 };
                nodes.push(node);
                nodeMap.set(name, node);
              } else {
                nodeMap.get(name).val += 1;
              }
            });
         }
      }
    });

    // Create some random links between entities found in the same step for visualization
    for (let i = 0; i < nodes.length - 1; i++) {
       if (links.length < 20) {
         links.push({ source: nodes[i].id, target: nodes[i+1].id, label: "related" });
       }
    }

    if (nodes.length === 0) return;

    const width = containerRef.current.clientWidth;
    const height = 200;

    const svg = d3.select(svgRef.current);
    svg.selectAll("*").remove();

    const simulation = d3.forceSimulation(nodes)
      .force("link", d3.forceLink(links).id((d: any) => (d as GraphNode).id).distance(60))
      .force("charge", d3.forceManyBody().strength(-150))
      .force("center", d3.forceCenter(width / 2, height / 2));

    const link = svg.append("g")
      .attr("stroke", "#94a3b8")
      .attr("stroke-opacity", 0.4)
      .selectAll("line")
      .data(links)
      .join("line")
      .attr("stroke-width", 1);

    const node = svg.append("g")
      .selectAll("circle")
      .data(nodes)
      .join("circle")
      .attr("r", (d: any) => 5 + (d as GraphNode).val * 2)
      .attr("fill", (d: any) => {
        if ((d as GraphNode).id.toLowerCase().includes("inc") || (d as GraphNode).id.toLowerCase().includes("corp")) return "#3b82f6"; // ORG
        return "#94a3b8";
      })
      .attr("stroke", "#fff")
      .attr("stroke-width", 1.5)
      .call(d3.drag<SVGCircleElement, any>()
        .on("start", dragstarted)
        .on("drag", dragged)
        .on("end", dragended));

    const label = svg.append("g")
      .selectAll("text")
      .data(nodes)
      .join("text")
      .attr("font-size", "9px")
      .attr("dx", 10)
      .attr("dy", 4)
      .text((d: any) => (d as GraphNode).id)
      .attr("fill", "#64748b");

    simulation.on("tick", () => {
      link
        .attr("x1", (d: any) => (d.source as GraphNode).x!)
        .attr("y1", (d: any) => (d.source as GraphNode).y!)
        .attr("x2", (d: any) => (d.target as GraphNode).x!)
        .attr("y2", (d: any) => (d.target as GraphNode).y!);

      node
        .attr("cx", (d: any) => (d as GraphNode).x!)
        .attr("cy", (d: any) => (d as GraphNode).y!);
      
      label
        .attr("x", (d: any) => (d as GraphNode).x!)
        .attr("y", (d: any) => (d as GraphNode).y!);
    });

    function dragstarted(event: d3.D3DragEvent<SVGCircleElement, any, any>) {
      if (!event.active) simulation.alphaTarget(0.3).restart();
      event.subject.fx = event.subject.x;
      event.subject.fy = event.subject.y;
    }

    function dragged(event: d3.D3DragEvent<SVGCircleElement, any, any>) {
      event.subject.fx = event.x;
      event.subject.fy = event.y;
    }

    function dragended(event: d3.D3DragEvent<SVGCircleElement, any, any>) {
      if (!event.active) simulation.alphaTarget(0);
      event.subject.fx = null;
      event.subject.fy = null;
    }

    return () => simulation.stop();
  }, [steps]);

  return (
    <div ref={containerRef} className="w-full bg-background/50 rounded-xl border border-border/50 overflow-hidden">
      <div className="px-3 py-1.5 border-b border-border/50 flex items-center justify-between">
        <span className="text-[10px] font-bold uppercase tracking-wider text-muted-foreground flex items-center gap-1">
          <Activity className="w-3 h-3" /> Graph Explorer Mini-map
        </span>
      </div>
      <svg ref={svgRef} className="w-full h-[200px]" />
    </div>
  );
}
