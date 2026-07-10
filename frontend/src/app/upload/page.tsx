"use client";

import { useState } from "react";
import { useDropzone } from "react-dropzone";
import { Card, CardContent } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Progress } from "@/components/ui/progress";
import { Upload, File, CheckCircle, Loader2, X, Search } from "lucide-react";
import { motion, AnimatePresence } from "framer-motion";
import { toast } from "sonner";
import { api } from "@/lib/api";
import { useRouter } from "next/navigation";

type UploadStatus = "idle" | "uploading" | "extracting" | "chunking" | "embedding" | "indexed";

interface UploadFile {
  file: File;
  status: UploadStatus;
  progress: number;
}

export default function UploadPage() {
  const router = useRouter();
  const [files, setFiles] = useState<UploadFile[]>([]);
  const [selectedSystem, setSelectedSystem] = useState<"enterprise" | "sharding">("enterprise");

  const onDrop = (acceptedFiles: File[]) => {
    const newFiles = acceptedFiles.map(file => ({
      file,
      status: "idle" as UploadStatus,
      progress: 0
    }));
    setFiles(prev => [...prev, ...newFiles]);
  };

  const { getRootProps, getInputProps, isDragActive } = useDropzone({
    onDrop,
    accept: {
      'application/pdf': ['.pdf'],
      'text/html': ['.html', '.htm'],
      'application/vnd.openxmlformats-officedocument.wordprocessingml.document': ['.docx'],
      'image/*': ['.jpg', '.jpeg', '.png']
    }
  });

  const startUpload = async (fileIdx: number) => {
    const fileObj = files[fileIdx];
    const updateStatus = (status: UploadStatus, progress: number) => {
      setFiles(prev => {
        const next = [...prev];
        next[fileIdx] = { ...next[fileIdx], status, progress };
        return next;
      });
    };

    try {
      updateStatus("uploading", 20);
      await new Promise(r => setTimeout(r, 1000)); // Simulate
      updateStatus("extracting", 40);
      await new Promise(r => setTimeout(r, 1000));
      updateStatus("chunking", 60);
      await new Promise(r => setTimeout(r, 1000));
      updateStatus("embedding", 80);
      
      await api.upload(fileObj.file, selectedSystem === "sharding");
      updateStatus("indexed", 100);
      toast.success(`${fileObj.file.name} indexed successfully`);
    } catch {
      toast.error(`Failed to upload ${fileObj.file.name}`);
      updateStatus("idle", 0);
    }
  };

  const removeFile = (idx: number) => {
    setFiles(prev => prev.filter((_, i) => i !== idx));
  };

  return (
    <div className="max-w-4xl mx-auto p-8 space-y-8">
      <div className="space-y-2">
        <h1 className="text-3xl font-bold tracking-tight">Ingest Documents</h1>
        <p className="text-muted-foreground">
          Upload PDF, DOCX, HTML, or Images to build your knowledge base.
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
      </div>

      <div 
        {...getRootProps()} 
        className={`border-2 border-dashed rounded-3xl p-12 transition-all cursor-pointer text-center space-y-4 ${
          isDragActive ? 'border-primary bg-primary/5' : 'border-muted-foreground/20'
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
          {files.map((file, i) => (
            <motion.div
              key={file.file.name + i}
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
                    <div className="flex justify-between items-center mb-1">
                      <p className="text-sm font-medium truncate">{file.file.name}</p>
                      <span className="text-[10px] font-mono text-muted-foreground capitalize">
                        {file.status}
                      </span>
                    </div>
                    <Progress value={file.progress} className="h-1.5" />
                  </div>
                  <div className="flex items-center gap-2">
                    {file.status === "idle" ? (
                      <>
                        <Button variant="ghost" size="icon" onClick={() => removeFile(i)}>
                          <X className="w-4 h-4" />
                        </Button>
                        <Button size="sm" onClick={() => startUpload(i)}>
                          Start
                        </Button>
                      </>
                    ) : file.status === "indexed" ? (
                      <div className="flex items-center gap-2">
                        <CheckCircle className="w-5 h-5 text-green-500" />
                        <Button size="sm" variant="outline" onClick={() => router.push(`/search?q=${encodeURIComponent(file.file.name)}`)}>
                          <Search className="w-4 h-4 mr-1" /> Debug
                        </Button>
                      </div>
                    ) : (
                      <Loader2 className="w-5 h-5 animate-spin text-primary" />
                    )}
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
