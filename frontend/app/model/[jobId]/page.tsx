"use client";

import dynamic from "next/dynamic";
import Link from "next/link";
import { useParams } from "next/navigation";
import { ArrowLeft, Download, Box } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";

const GlbViewer = dynamic(() => import("@/components/GlbViewer"), { ssr: false });

export default function ModelPage() {
  const params = useParams<{ jobId: string }>();
  const jobId = params?.jobId ?? "";
  const glbUrl = `/api/ml/jobs/${jobId}/glb`;

  const handleDownload = () => {
    const a = document.createElement("a");
    a.href = glbUrl;
    a.download = `model_${jobId.slice(0, 8)}.glb`;
    a.click();
  };

  return (
    <div className="max-w-7xl mx-auto px-6 py-10">
      <div className="mb-8 flex flex-wrap items-center justify-between gap-4">
        <div className="space-y-1">
          <Link href="/create-3d" className="text-sm text-slate-400 hover:text-white inline-flex items-center gap-1">
            <ArrowLeft className="w-4 h-4" /> 3D Model Builder
          </Link>
          <h1 className="text-3xl font-bold text-white tracking-tight flex items-center gap-3">
            <Box className="w-7 h-7 text-indigo-400" /> 3D LEGO Model
          </h1>
          <p className="text-sm text-slate-400 font-mono">{jobId}</p>
        </div>
        <div className="flex gap-2">
          <Link href="/create-3d">
            <Button variant="outline" className="border-slate-700 text-slate-200">
              New Model
            </Button>
          </Link>
          <Button onClick={handleDownload} className="bg-[#f57c00] hover:bg-orange-600 text-white">
            <Download className="w-4 h-4 mr-2" /> Download GLB
          </Button>
        </div>
      </div>

      <Card className="bg-slate-900/40 border-slate-800 p-4">
        <div className="h-[620px]">
          <GlbViewer glbUrl={glbUrl} />
        </div>
      </Card>

      <p className="mt-4 text-xs text-slate-500 text-center">
        Open the downloaded GLB in Blender, Windows 3D Viewer, or any GLTF-compatible tool.
      </p>
    </div>
  );
}
