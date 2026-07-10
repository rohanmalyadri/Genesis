"use client";

import { useState, useEffect } from "react";
import { Card, CardHeader, CardTitle, CardContent, CardDescription } from "@/components/ui/card";
import { Slider } from "@/components/ui/slider";
import { Switch } from "@/components/ui/switch";
import { Button } from "@/components/ui/button";
import { Tabs, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Label } from "@/components/ui/label";
import { Separator } from "@/components/ui/separator";
import { Shield, Brain, Database, Save } from "lucide-react";
import { toast } from "sonner";

export default function SettingsPage() {
  const [chunkSize, setChunkSize] = useState([512]);
  const [topK, setTopK] = useState([5]);
  const [model, setModel] = useState("gemini-3-flash");
  
  const [inputGuard, setInputGuard] = useState(true);
  const [contentFilter, setContentFilter] = useState(true);
  const [outputGuard, setOutputGuard] = useState(true);
  const [showTrace, setShowTrace] = useState(true);
  
  const [isMounted, setIsMounted] = useState(false);

  useEffect(() => {
    setTimeout(() => {
      setIsMounted(true);
      const saved = localStorage.getItem("rag_settings");
      if (saved) {
        try {
          const parsed = JSON.parse(saved);
          if (parsed.chunkSize) setChunkSize(parsed.chunkSize);
          if (parsed.topK) setTopK(parsed.topK);
          if (parsed.model) setModel(parsed.model);
          if (typeof parsed.inputGuard === 'boolean') setInputGuard(parsed.inputGuard);
          if (typeof parsed.contentFilter === 'boolean') setContentFilter(parsed.contentFilter);
          if (typeof parsed.outputGuard === 'boolean') setOutputGuard(parsed.outputGuard);
          if (typeof parsed.showTrace === 'boolean') setShowTrace(parsed.showTrace);
        } catch (e) {
          console.error("Failed to parse settings", e);
        }
      }
    }, 0);
  }, []);

  const handleSave = () => {
    const settings = {
      chunkSize,
      topK,
      model,
      inputGuard,
      contentFilter,
      outputGuard,
      showTrace
    };
    localStorage.setItem("rag_settings", JSON.stringify(settings));
    toast.success("Settings saved successfully");
  };

  if (!isMounted) return null;

  return (
    <div className="max-w-4xl mx-auto p-8 space-y-8">
      <div className="flex justify-between items-end">
        <div className="space-y-2">
          <h1 className="text-3xl font-bold">System Settings</h1>
          <p className="text-muted-foreground">Configure global RAG parameters and security guards.</p>
        </div>
        <Button onClick={handleSave} className="gap-2">
          <Save className="w-4 h-4" /> Save Changes
        </Button>
      </div>

      <div className="grid gap-6 md:grid-cols-2">
        <Card className="border-border/50 shadow-sm">
          <CardHeader>
            <div className="flex items-center gap-2 mb-1">
              <Brain className="w-5 h-5 text-primary" />
              <CardTitle>Model Configuration</CardTitle>
            </div>
            <CardDescription>Select the LLM and generation parameters.</CardDescription>
          </CardHeader>
          <CardContent className="space-y-6">
             <div className="space-y-4">
               <Label>Primary Model</Label>
               <Tabs value={model} onValueChange={setModel} className="w-full">
                 <TabsList className="grid w-full grid-cols-2">
                   <TabsTrigger value="gemini-3-flash">Gemini 3 Flash</TabsTrigger>
                   <TabsTrigger value="gemini-3-pro">Gemini 3 Pro</TabsTrigger>
                 </TabsList>
               </Tabs>
             </div>

             <div className="space-y-4">
               <div className="flex justify-between items-center">
                 <Label>Top K Results</Label>
                 <span className="text-sm font-mono text-primary font-bold">{topK}</span>
               </div>
               <Slider 
                 value={topK} 
                 onValueChange={setTopK} 
                 min={3} 
                 max={20} 
                 step={1} 
               />
               <p className="text-[11px] text-muted-foreground italic">
                 Number of documents retrieved for each query.
               </p>
             </div>
          </CardContent>
        </Card>

        <Card className="border-border/50 shadow-sm">
          <CardHeader>
            <div className="flex items-center gap-2 mb-1">
              <Shield className="w-5 h-5 text-red-500" />
              <CardTitle>Security Guards</CardTitle>
            </div>
            <CardDescription>Toggle active security monitors.</CardDescription>
          </CardHeader>
          <CardContent className="space-y-6">
             <div className="flex items-center justify-between">
                <div className="space-y-0.5">
                  <Label>Input Guard</Label>
                  <p className="text-[10px] text-muted-foreground">Prompt injection & SQLi detection.</p>
                </div>
                <Switch checked={inputGuard} onCheckedChange={setInputGuard} />
             </div>
             <Separator />
             <div className="flex items-center justify-between">
                <div className="space-y-0.5">
                  <Label>Content Filter</Label>
                  <p className="text-[10px] text-muted-foreground">Validate retrieved document domain & relevance.</p>
                </div>
                <Switch checked={contentFilter} onCheckedChange={setContentFilter} />
             </div>
             <Separator />
             <div className="flex items-center justify-between">
                <div className="space-y-0.5">
                  <Label>Output Guard</Label>
                  <p className="text-[10px] text-muted-foreground">PII redaction using Presidio.</p>
                </div>
                <Switch checked={outputGuard} onCheckedChange={setOutputGuard} />
             </div>
             <Separator />
             <div className="flex items-center justify-between">
                <div className="space-y-0.5">
                  <Label>Show Reasoning Trace</Label>
                  <p className="text-[10px] text-muted-foreground">Display agent&apos;s multi-hop thinking process.</p>
                </div>
                <Switch checked={showTrace} onCheckedChange={setShowTrace} />
             </div>
          </CardContent>
        </Card>

        <Card className="border-border/50 shadow-sm md:col-span-2">
          <CardHeader>
            <div className="flex items-center gap-2 mb-1">
              <Database className="w-5 h-5 text-blue-500" />
              <CardTitle>Ingestion & Cache</CardTitle>
            </div>
          </CardHeader>
          <CardContent className="grid md:grid-cols-2 gap-8">
            <div className="space-y-4">
               <div className="flex justify-between items-center">
                 <Label>Semantic Chunk Size</Label>
                 <span className="text-sm font-mono text-primary font-bold">{chunkSize} tokens</span>
               </div>
               <Slider 
                 value={chunkSize} 
                 onValueChange={setChunkSize} 
                 min={128} 
                 max={1024} 
                 step={64} 
               />
            </div>
            <div className="space-y-4">
               <div className="flex justify-between items-center">
                 <Label>Cache TTL</Label>
                 <span className="text-sm font-mono text-primary font-bold">3600s</span>
               </div>
               <Slider defaultValue={[3600]} min={60} max={86400} step={60} />
            </div>
          </CardContent>
        </Card>
      </div>
    </div>
  );
}
