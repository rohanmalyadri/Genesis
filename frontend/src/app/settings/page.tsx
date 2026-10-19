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
import { AppSettings, DEFAULT_SETTINGS, loadSettings, saveSettings } from "@/lib/settings";

export default function SettingsPage() {
  const [settings, setSettings] = useState<AppSettings>(DEFAULT_SETTINGS);
  const [isMounted, setIsMounted] = useState(false);

  useEffect(() => {
    const t = setTimeout(() => {
      setSettings(loadSettings());
      setIsMounted(true);
    }, 0);
    return () => clearTimeout(t);
  }, []);

  const patch = (p: Partial<AppSettings>) => setSettings((prev) => ({ ...prev, ...p }));
  const asArray = (v: number | readonly number[]) => (Array.isArray(v) ? [...v] : [v as number]);

  const handleSave = () => {
    saveSettings(settings);
    toast.success("Settings saved. They apply to your next question or upload.");
  };

  const handleReset = () => {
    setSettings(DEFAULT_SETTINGS);
    saveSettings(DEFAULT_SETTINGS);
    toast.success("Settings reset to defaults");
  };

  const { chunkSize, topK, cacheTtl, model, inputGuard, contentFilter, outputGuard, showTrace } = settings;

  if (!isMounted) return null;

  return (
    <div className="max-w-4xl mx-auto p-8 space-y-8">
      <div className="flex justify-between items-end">
        <div className="space-y-2">
          <h1 className="text-3xl font-bold">System Settings</h1>
          <p className="text-muted-foreground">Configure global RAG parameters and security guards.</p>
        </div>
        <div className="flex gap-2">
          <Button variant="outline" onClick={handleReset}>Reset</Button>
          <Button onClick={handleSave} className="gap-2">
            <Save className="w-4 h-4" /> Save Changes
          </Button>
        </div>
      </div>

      <div className="grid gap-6 md:grid-cols-2">
        <Card className="border-border/50 shadow-sm">
          <CardHeader>
            <div className="flex items-center gap-2 mb-1">
              <Brain className="w-5 h-5 text-primary" />
              <CardTitle>Model Configuration</CardTitle>
            </div>
            <CardDescription>Choose the Gemini model and how many sources to use.</CardDescription>
          </CardHeader>
          <CardContent className="space-y-6">
             <div className="space-y-4">
               <Label>Primary Model</Label>
               <Tabs value={model} onValueChange={(v) => patch({ model: String(v) })} className="w-full">
                 <TabsList className="grid w-full grid-cols-2">
                   <TabsTrigger value="gemini-3-flash">Gemini 3 Flash</TabsTrigger>
                   <TabsTrigger value="gemini-3-pro">Gemini 3 Pro</TabsTrigger>
                 </TabsList>
               </Tabs>
             </div>

             <div className="space-y-4">
               <div className="flex justify-between items-center">
                 <Label>Top K Results</Label>
                 <span className="text-sm font-mono text-primary font-bold">{topK[0]}</span>
               </div>
               <Slider 
                 value={topK} 
                 onValueChange={(v) => patch({ topK: asArray(v) })} 
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
                  <p className="text-[10px] text-muted-foreground">Blocks prompt-injection, SQL-injection and path-traversal attempts.</p>
                </div>
                <Switch checked={inputGuard} onCheckedChange={(v) => patch({ inputGuard: v })} />
             </div>
             <Separator />
             <div className="flex items-center justify-between">
                <div className="space-y-0.5">
                  <Label>Content Filter</Label>
                  <p className="text-[10px] text-muted-foreground">Validate retrieved document domain & relevance.</p>
                </div>
                <Switch checked={contentFilter} onCheckedChange={(v) => patch({ contentFilter: v })} />
             </div>
             <Separator />
             <div className="flex items-center justify-between">
                <div className="space-y-0.5">
                  <Label>Output Guard</Label>
                  <p className="text-[10px] text-muted-foreground">PII redaction using Presidio.</p>
                </div>
                <Switch checked={outputGuard} onCheckedChange={(v) => patch({ outputGuard: v })} />
             </div>
             <Separator />
             <div className="flex items-center justify-between">
                <div className="space-y-0.5">
                  <Label>Show Reasoning Trace</Label>
                  <p className="text-[10px] text-muted-foreground">Display agent&apos;s multi-hop thinking process.</p>
                </div>
                <Switch checked={showTrace} onCheckedChange={(v) => patch({ showTrace: v })} />
             </div>
          </CardContent>
        </Card>

        <Card className="border-border/50 shadow-sm md:col-span-2">
          <CardHeader>
            <div className="flex items-center gap-2 mb-1">
              <Database className="w-5 h-5 text-blue-500" />
              <CardTitle>Ingestion & Cache</CardTitle>
            </div>
            <CardDescription>Chunk size applies to new uploads. Cache lifetime applies to new answers.</CardDescription>
          </CardHeader>
          <CardContent className="grid md:grid-cols-2 gap-8">
            <div className="space-y-4">
               <div className="flex justify-between items-center">
                 <Label>Semantic Chunk Size</Label>
                 <span className="text-sm font-mono text-primary font-bold">{chunkSize[0]} tokens</span>
               </div>
               <Slider 
                 value={chunkSize} 
                 onValueChange={(v) => patch({ chunkSize: asArray(v) })} 
                 min={128} 
                 max={1024} 
                 step={64} 
               />
            </div>
            <div className="space-y-4">
               <div className="flex justify-between items-center">
                 <Label>Cache TTL</Label>
                 <span className="text-sm font-mono text-primary font-bold">{cacheTtl[0]}s</span>
               </div>
               <Slider value={cacheTtl} onValueChange={(v) => patch({ cacheTtl: asArray(v) })} min={60} max={86400} step={60} />
            </div>
          </CardContent>
        </Card>
      </div>
    </div>
  );
}
