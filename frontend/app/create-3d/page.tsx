"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { useRouter } from "next/navigation";
import { motion } from "framer-motion";
import { Box, Upload, Video, ImageIcon, Loader2 } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";

type UploadState = "idle" | "uploading" | "processing" | "done" | "error";

export default function Create3DPage() {
  const router = useRouter();
  const inputRef = useRef<HTMLInputElement>(null);
  const [file, setFile] = useState<File | null>(null);
  const [state, setState] = useState<UploadState>("idle");
  const [progress, setProgress] = useState("");
  const [error, setError] = useState("");
  const [elapsed, setElapsed] = useState(0);
  const jobIdRef = useRef<string | null>(null);
  const pollRef = useRef<ReturnType<typeof setInterval> | null>(null);
  const timerRef = useRef<ReturnType<typeof setInterval> | null>(null);

  const stopTimers = () => {
    if (pollRef.current) clearInterval(pollRef.current);
    if (timerRef.current) clearInterval(timerRef.current);
  };

  useEffect(() => () => stopTimers(), []);

  const startPolling = (jobId: string) => {
    setElapsed(0);
    timerRef.current = setInterval(() => setElapsed(s => s + 1), 1000);
    pollRef.current = setInterval(async () => {
      try {
        const res = await fetch(`/api/ml/jobs/${jobId}`);
        if (!res.ok) return;
        const data = await res.json();
        setProgress(data.progress ?? "");
        if (data.status === "done") {
          stopTimers();
          setState("done");
          router.push(`/model/${jobId}`);
        } else if (data.status === "failed") {
          stopTimers();
          setState("error");
          setError(data.error ?? "Pipeline failed");
        }
      } catch { /* network hiccup — keep polling */ }
    }, 3000);
  };

  const handleFile = useCallback((f: File) => {
    setFile(f);
    setError("");
    setState("idle");
  }, []);

  const handleDrop = useCallback((e: React.DragEvent) => {
    e.preventDefault();
    const f = e.dataTransfer.files[0];
    if (f) handleFile(f);
  }, [handleFile]);

  const handleSubmit = async () => {
    if (!file) return;
    setState("uploading");
    setError("");
    try {
      const form = new FormData();
      form.append("file", file);
      const res = await fetch("/api/ml/jobs", { method: "POST", body: form });
      if (!res.ok) throw new Error("Upload failed");
      const { job_id } = await res.json();
      jobIdRef.current = job_id;
      setState("processing");
      setProgress("Queued");
      startPolling(job_id);
    } catch (e) {
      setState("error");
      setError(e instanceof Error ? e.message : "Upload failed");
    }
  };

  const fmtTime = (s: number) =>
    s < 60 ? `${s}s` : `${Math.floor(s / 60)}m ${s % 60}s`;

  const isActive = state === "uploading" || state === "processing";

  return (
    <div className="max-w-2xl mx-auto px-6 py-12">
      <motion.div initial={{ opacity: 0, y: 12 }} animate={{ opacity: 1, y: 0 }} className="mb-10 space-y-2">
        <div className="flex items-center gap-3">
          <Box className="w-7 h-7 text-indigo-400" />
          <h1 className="text-3xl font-bold text-white tracking-tight">3D Model Builder</h1>
        </div>
        <p className="text-slate-400 max-w-lg">
          Upload a short video walking around your subject, or a set of photos from all angles.
          The pipeline reconstructs a full 3D LEGO sculpture with an accurate parts list.
        </p>
      </motion.div>

      <Card className="bg-slate-900/40 border-slate-800 p-6 space-y-6">
        {/* Tips */}
        <div className="grid grid-cols-2 gap-3">
          {[
            { icon: Video, tip: "10–30 sec orbit video works best" },
            { icon: ImageIcon, tip: "30–60 photos from all angles" },
          ].map(({ icon: Icon, tip }) => (
            <div key={tip} className="flex items-start gap-2 p-3 rounded-xl bg-slate-800/50 border border-slate-700">
              <Icon className="w-4 h-4 text-indigo-400 mt-0.5 shrink-0" />
              <p className="text-xs text-slate-300">{tip}</p>
            </div>
          ))}
        </div>

        {/* Drop zone */}
        <div
          onDrop={handleDrop}
          onDragOver={e => e.preventDefault()}
          onClick={() => !isActive && inputRef.current?.click()}
          className={`relative border-2 border-dashed rounded-2xl p-10 text-center transition-colors cursor-pointer
            ${isActive ? "border-slate-700 cursor-default" : "border-slate-700 hover:border-indigo-500/60"}
            ${file && !isActive ? "border-indigo-500/40 bg-indigo-500/5" : ""}`}
        >
          <input
            ref={inputRef}
            type="file"
            className="hidden"
            accept="video/*,image/*,.zip"
            onChange={e => e.target.files?.[0] && handleFile(e.target.files[0])}
          />

          {isActive ? (
            <div className="space-y-3">
              <Loader2 className="w-10 h-10 mx-auto text-indigo-400 animate-spin" />
              <p className="text-white font-medium">
                {state === "uploading" ? "Uploading…" : progress || "Processing…"}
              </p>
              <p className="text-xs text-slate-500">Elapsed: {fmtTime(elapsed)}</p>
              <p className="text-xs text-slate-500">
                Full reconstruction takes 5–15 minutes depending on input length.
              </p>
            </div>
          ) : file ? (
            <div className="space-y-2">
              <Upload className="w-8 h-8 mx-auto text-indigo-400" />
              <p className="text-white font-medium truncate">{file.name}</p>
              <p className="text-xs text-slate-400">
                {(file.size / 1024 / 1024).toFixed(1)} MB · Click to change
              </p>
            </div>
          ) : (
            <div className="space-y-2">
              <Upload className="w-10 h-10 mx-auto text-slate-500" />
              <p className="text-slate-300 font-medium">Drop video or images here</p>
              <p className="text-xs text-slate-500">MP4, MOV, JPG, PNG, or ZIP of images</p>
            </div>
          )}
        </div>

        {error && (
          <p className="text-sm text-red-400 bg-red-500/10 border border-red-500/20 rounded-xl px-4 py-3">
            {error}
          </p>
        )}

        <Button
          onClick={handleSubmit}
          disabled={!file || isActive}
          className="w-full py-6 text-base bg-indigo-600 hover:bg-indigo-500 text-white font-semibold disabled:opacity-40"
        >
          {isActive ? (
            <><Loader2 className="w-4 h-4 mr-2 animate-spin" /> Processing…</>
          ) : (
            <><Box className="w-4 h-4 mr-2" /> Start 3D Reconstruction</>
          )}
        </Button>
      </Card>
    </div>
  );
}
