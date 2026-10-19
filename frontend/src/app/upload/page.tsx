"use client";

import { useState } from "react";
import { useDropzone } from "react-dropzone";
import { Card, CardContent } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Progress } from "@/components/ui/progress";
import { Upload, File, CheckCircle, Loader2, X, Search, AlertCircle, Copy } from "lucide-react";
import { motion, AnimatePresence } from "framer-motion";
import { toast } from "sonner";
import { api } from "@/lib/api";
import { loadSettings } from "@/lib/settings";
import { useRouter } from "next/navigation";

type UploadStatus = "idle" | "uploading" | "indexed" | "duplicate" | "error";

interface UploadFile {
  id: string;
  file: File;
  status: UploadStatus;
  detail?: string;
}

const STATUS_LABEL: Record<UploadStatus, string> = {
  idle: "ready",
  uploading: "indexing...",
  indexed: "indexed",
  duplicate: "already indexed",
  error: "failed",
};

export default function UploadPage() {
  const router = useRouter();
  const [files, setFiles] = useState<UploadFile[]>([]);
  const [selectedSystem, setSelectedSystem] = useState<"enterprise" | "sharding">("enterprise");

  const onDrop = (acceptedFiles: File[]) => {
    setFiles((prev) => [
      ...prev,
      ...acceptedFiles.map((file) => ({ id: crypto.randomUUID(), file, status: "idle" as UploadStatus })),
    ]);
  };

  const { getRootProps, getInputProps, isDragActive } = useDropzone({
    onDrop,
    onDropRejected: (rejections) =>
      toast.error(`Unsupported file: ${rejections.map((r) => r.file.name).join(", ")}`),
    accept: {
      "application/pdf": [".pdf"],
      "text/html": [".html", ".htm"],
      "text/plain": [".txt", ".py"],
      "text/markdown": [".md"],
      "application/vnd.openxmlformats-officedocument.wordprocessingml.document": [".docx"],
      "image/*": [".jpg", ".jpeg", ".png"],
    },
  });

  const update = (id: string, patch: Partial<UploadFile>) =>
    setFiles((prev) => prev.map((f) => (f.id === id ? { ...f, ...patch } : f)));

  const startUpload = async (item: UploadFile) => {
    update(item.id, { status: "uploading", detail: undefined });
    try {
      const result = await api.upload(item.file, selectedSystem === "sharding", loadSettings().chunkSize[0]);
      if (result.status === "duplicate") {
        update(item.id, { status: "duplicate", detail: "A document with the same content is already indexed." });
        toast.info(`${item.file.name} is already indexed`);
      } else {
        update(item.id, { status: "indexed", detail: `${result.chunks} chunk${result.chunks === 1 ? "" : "s"}` });
        toast.success(`${item.file.name} indexed (${result.chunks} chunks)`);
      }
    } catch (e) {
      const msg = e instanceof Error ? e.message : "Upload failed";
      update(item.id, { status: "error", detail: msg });
      toast.error(`${item.file.name}: ${msg}`);
    }
  };

  const removeFile = (id: string) => setFiles((prev) => prev.filter((f) => f.id !== id));

  const progressFor = (s: UploadStatus) => (s === "idle" ? 0 : s === "uploading" ? 60 : s === "error" ? 0 : 100);

  return (
    <div className="max-w-4xl mx-auto p-8 space-y-8">
      <div className="space-y-2">
        <h1 className="text-3xl font-bold tracking-tight">Ingest Documents</h1>
        <p className="text-muted-foreground">
          Upload PDF, DOCX, HTML, text, Markdown or images (OCR) to build your knowledge base.
        </p>
      </div>

      <div className="space-y-4">
        <div className="flex gap-4">
          <Button
            variant={selectedSystem === "enterprise" ? "default" : "outline"}
            className="flex-1 h-16 rounded-2xl flex flex-col items-center justify-center gap-1"
            onClick={() => setSelectedSystem("enterprise")}
          >
            <span className="font-bold">Enterprise RAG</span>
            <span className="text-[10px] opacity-70">Single Collection</span>
          </Button>
          <Button
            variant={selectedSystem === "sharding" ? "default" : "outline"}
            className="flex-1 h-16 rounded-2xl flex flex-col items-center justify-center gap-1"
            onClick={() => setSelectedSystem("sharding")}
          >
            <span className="font-bold">Multi-Tenant Sharding</span>
            <span className="text-[10px] opacity-70">16x Chroma Shards</span>
          </Button>
        </div>
        <p className="text-xs text-muted-foreground">
          Tip: upload a file to each system if you want to compare them on the Debugger page.
        </p>
      </div>

      <div
        {...getRootProps()}
        className={`border-2 border-dashed rounded-3xl p-12 transition-all cursor-pointer text-center space-y-4 ${
          isDragActive ? "border-primary bg-primary/5" : "border-muted-foreground/20"
        }`}
      >
        <input {...getInputProps()} />
        <div className="w-16 h-16 bg-primary/10 rounded-full flex items-center justify-center mx-auto">
          <Upload className="w-8 h-8 text-primary" />
        </div>
        <div className="space-y-1">
          <p className="text-lg font-medium">Drag & drop files here</p>
          <p className="text-sm text-muted-foreground">or click to browse your computer</p>
        </div>
      </div>

      <div className="grid gap-4">
        <AnimatePresence>
          {files.map((item) => (
            <motion.div
              key={item.id}
              initial={{ opacity: 0, y: 10 }}
              animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0, scale: 0.95 }}
            >
              <Card className="border-border/50">
                <CardContent className="p-4 flex items-center gap-4">
                  <div className="w-10 h-10 rounded-xl bg-muted flex items-center justify-center">
                    <File className="w-5 h-5 text-muted-foreground" />
                  </div>
                  <div className="flex-1 min-w-0">
                    <div className="flex justify-between items-center mb-1 gap-3">
                      <p className="text-sm font-medium truncate">{item.file.name}</p>
                      <span className="text-[10px] font-mono text-muted-foreground whitespace-nowrap">
                        {STATUS_LABEL[item.status]}
                        {item.status === "indexed" && item.detail ? ` • ${item.detail}` : ""}
                      </span>
                    </div>
                    <Progress value={progressFor(item.status)} className="h-1.5" />
                    {(item.status === "error" || item.status === "duplicate") && item.detail && (
                      <p className="mt-1 text-[11px] text-muted-foreground">{item.detail}</p>
                    )}
                  </div>
                  <div className="flex items-center gap-2">
                    {item.status === "idle" || item.status === "error" ? (
                      <>
                        <Button variant="ghost" size="icon" onClick={() => removeFile(item.id)}>
                          <X className="w-4 h-4" />
                        </Button>
                        <Button size="sm" onClick={() => startUpload(item)}>
                          {item.status === "error" ? "Retry" : "Start"}
                        </Button>
                      </>
                    ) : item.status === "uploading" ? (
                      <Loader2 className="w-5 h-5 animate-spin text-primary" />
                    ) : (
                      <div className="flex items-center gap-2">
                        {item.status === "indexed" ? (
                          <CheckCircle className="w-5 h-5 text-green-500" />
                        ) : (
                          <Copy className="w-5 h-5 text-amber-500" />
                        )}
                        <Button
                          size="sm"
                          variant="outline"
                          onClick={() => router.push(`/search?q=${encodeURIComponent(item.file.name)}`)}
                        >
                          <Search className="w-4 h-4 mr-1" /> Debug
                        </Button>
                      </div>
                    )}
                    {item.status === "error" && <AlertCircle className="w-5 h-5 text-red-500" />}
                  </div>
                </CardContent>
              </Card>
            </motion.div>
          ))}
        </AnimatePresence>
      </div>
    </div>
  );
}
