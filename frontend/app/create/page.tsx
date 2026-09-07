"use client";

import { useState, useRef, useEffect } from "react";
import Script from "next/script";
import { useRouter } from "next/navigation";
import { motion } from "framer-motion";
import { Upload, X, Layers, Smartphone, ArrowRight, Loader2 } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import {
  gridDimsFor,
  loadImageFromDataUrl,
  makeSourceThumbDataUrl,
  quantizeImageDithered,
  renderMosaic,
  type DetailLevel,
} from "@/lib/mosaic";
import { savePendingJob } from "@/lib/builds";
import { dataUrlToFile, submitJob } from "@/lib/api";

const DETAIL_LEVELS: DetailLevel[] = ["Low", "Medium", "High"];
const DETAIL_TO_PERCENT: Record<DetailLevel, string> = {
  Low: "33%",
  Medium: "66%",
  High: "100%",
};

export default function BrickLabStudio() {
  const router = useRouter();
  const [images, setImages] = useState<(string | null)[]>(Array(5).fill(null));
  const [activeIndex, setActiveIndex] = useState<number>(0);
  const [detailLevel, setDetailLevel] = useState<DetailLevel>("Medium");
  const [buildName, setBuildName] = useState("");
  const [isGenerating, setIsGenerating] = useState(false);
  const fileInputRefs = useRef<(HTMLInputElement | null)[]>([]);
  const previewCanvasRef = useRef<HTMLCanvasElement | null>(null);
  const animFrameRef = useRef<number | null>(null);

  const hasAnyImage = images.some((img) => img !== null);
  const activeImage = images[activeIndex] ?? null;

  useEffect(() => {
    if (!activeImage || isGenerating) return;
    let cancelled = false;

    if (animFrameRef.current !== null) {
      cancelAnimationFrame(animFrameRef.current);
      animFrameRef.current = null;
    }

    loadImageFromDataUrl(activeImage).then((img) => {
      if (cancelled || !previewCanvasRef.current) return;
      const { gridW, gridH } = gridDimsFor(detailLevel, img.naturalWidth, img.naturalHeight);
      const indices = quantizeImageDithered(img, gridW, gridH);
      startScanAnimation(previewCanvasRef.current, img, indices, gridW, gridH);
    });

    return () => {
      cancelled = true;
      if (animFrameRef.current !== null) {
        cancelAnimationFrame(animFrameRef.current);
        animFrameRef.current = null;
      }
    };
  }, [activeImage, detailLevel]); // eslint-disable-line react-hooks/exhaustive-deps

  function startScanAnimation(
    canvas: HTMLCanvasElement,
    img: HTMLImageElement,
    indices: Uint8Array,
    gridW: number,
    gridH: number
  ) {
    const W = 1280, H = 720;
    canvas.width = W;
    canvas.height = H;
    const ctx = canvas.getContext("2d")!;

    const brickPx = Math.max(4, Math.floor(Math.min(W / gridW, H / gridH)));
    const mosaicOff = document.createElement("canvas");
    renderMosaic(mosaicOff, indices, gridW, gridH, { brickPx });

    const duration = 1300;
    const startTime = performance.now();

    function frame(now: number) {
      const t = Math.min((now - startTime) / duration, 1);
      // ease-in-out cubic
      const eased = t < 0.5 ? 4 * t * t * t : 1 - Math.pow(-2 * t + 2, 3) / 2;
      const revealX = Math.floor(eased * W);

      ctx.drawImage(img, 0, 0, W, H);

      if (revealX > 0) {
        const srcRevealX = Math.floor((revealX / W) * mosaicOff.width);
        ctx.drawImage(mosaicOff, 0, 0, srcRevealX, mosaicOff.height, 0, 0, revealX, H);
      }

      if (t < 1) {
        const grd = ctx.createLinearGradient(revealX - 48, 0, revealX + 48, 0);
        grd.addColorStop(0, "rgba(245,124,0,0)");
        grd.addColorStop(0.4, "rgba(245,124,0,0.5)");
        grd.addColorStop(0.5, "rgba(255,215,100,0.95)");
        grd.addColorStop(0.6, "rgba(245,124,0,0.5)");
        grd.addColorStop(1, "rgba(245,124,0,0)");
        ctx.fillStyle = grd;
        ctx.fillRect(revealX - 48, 0, 96, H);

        ctx.strokeStyle = "rgba(255,240,180,0.7)";
        ctx.lineWidth = 1.5;
        ctx.beginPath();
        ctx.moveTo(revealX, 0);
        ctx.lineTo(revealX, H);
        ctx.stroke();
      }

      animFrameRef.current = t < 1 ? requestAnimationFrame(frame) : null;
    }

    animFrameRef.current = requestAnimationFrame(frame);
  }

  const handleUpload = (index: number, file: File | null) => {
    if (!file) return;
    const reader = new FileReader();
    reader.onloadend = () => {
      const updated = [...images];
      updated[index] = reader.result as string;
      setImages(updated);
      setActiveIndex(index);
    };
    reader.readAsDataURL(file);
  };

  const removeImage = (e: React.MouseEvent, index: number) => {
    e.stopPropagation();
    const updated = [...images];
    updated[index] = null;
    setImages(updated);
    if (animFrameRef.current !== null) {
      cancelAnimationFrame(animFrameRef.current);
      animFrameRef.current = null;
    }
    if (previewCanvasRef.current) {
      const ctx = previewCanvasRef.current.getContext("2d");
      ctx?.clearRect(0, 0, previewCanvasRef.current.width, previewCanvasRef.current.height);
    }
    if (index === activeIndex && index > 0) setActiveIndex(index - 1);
  };

  const triggerUpload = (index: number) => fileInputRefs.current[index]?.click();

  const clearAll = () => {
    if (!hasAnyImage) return;
    setImages(Array(5).fill(null));
    setActiveIndex(0);
    fileInputRefs.current.forEach((el) => { if (el) el.value = ""; });
    if (animFrameRef.current !== null) {
      cancelAnimationFrame(animFrameRef.current);
      animFrameRef.current = null;
    }
    if (previewCanvasRef.current) {
      const ctx = previewCanvasRef.current.getContext("2d");
      ctx?.clearRect(0, 0, previewCanvasRef.current.width, previewCanvasRef.current.height);
    }
  };

  const generateLayout = async () => {
    if (!hasAnyImage || isGenerating) return;
    setIsGenerating(true);
    try {
      const sources = images.filter((src): src is string => src !== null);
      const base = buildName.trim() || `Build ${new Date().toLocaleDateString()}`;
      const submittedAt = new Date().toISOString();
      const jobIds: string[] = [];

      for (let i = 0; i < sources.length; i++) {
        const title = sources.length > 1 ? `${base} #${i + 1}` : base;
        const file = dataUrlToFile(sources[i], `image_${i}.jpg`);

        // Generate source thumbnail client-side so the build page can show
        // the original photo alongside the mosaic after polling completes.
        const img = await loadImageFromDataUrl(sources[i]);
        const sourceThumbDataUrl = makeSourceThumbDataUrl(img);

        const { job_id } = await submitJob(file, detailLevel, title);

        // Store metadata so the build page can reconstruct the StoredBuild
        // without a round-trip to the server for fields the server doesn't keep.
        savePendingJob({
          jobId: job_id,
          title,
          detail: detailLevel,
          sourceThumbDataUrl,
          submittedAt,
        });

        jobIds.push(job_id);
      }

      if (jobIds.length === 1) {
        // Single image: go straight to the polling build page.
        router.push(`/build/${jobIds[0]}?polling=true`);
      } else {
        // Multiple images: all jobs are queued; my-builds will show them
        // as they complete (each build page saves to localStorage on visit).
        router.push("/my-builds");
      }
    } finally {
      setIsGenerating(false);
    }
  };

  return (
    <div className="min-h-screen bg-slate-50 text-slate-900 p-6 flex flex-col items-center justify-center relative overflow-hidden font-sans">
      <div className="absolute top-0 left-0 w-full h-full overflow-hidden pointer-events-none">
        <div className="absolute top-[-10%] right-[-5%] w-[500px] h-[500px] bg-[#f57c00]/5 rounded-full blur-[100px]" />
        <div className="absolute bottom-[-10%] left-[-5%] w-[600px] h-[600px] bg-[#004b87]/5 rounded-full blur-[120px]" />
      </div>

      <div className="absolute top-6 left-8 z-50 flex flex-col items-start">
        <img src="/logobackgroundremoved.png" alt="BrickLab Studio" className="h-30" />
      </div>

      <div className="max-w-6xl w-full z-10 grid grid-cols-1 lg:grid-cols-12 gap-8 mt-16">
        <div className="lg:col-span-8 flex flex-col gap-6">
          <motion.div
            initial={{ opacity: 0, y: 10 }}
            animate={{ opacity: 1, y: 0 }}
            className="flex items-center justify-between"
          >
            <div>
              <h1 className="text-2xl font-bold text-slate-800 tracking-tight flex items-center gap-3">
                <Layers className="text-[#004b87]" /> Brick Lab Studio
              </h1>
              <p className="text-slate-500 text-sm mt-1">
                {images.filter(Boolean).length} / 5 Assets Ready
              </p>
            </div>
            <Button
              variant="outline"
              onClick={clearAll}
              disabled={!hasAnyImage || isGenerating}
              className="border-slate-300 hover:bg-slate-100 text-slate-600"
            >
              Clear All
            </Button>
          </motion.div>

          {/* Main Stage */}
          <div className="relative aspect-video bg-white rounded-3xl border border-slate-200 overflow-hidden shadow-xl shadow-slate-200/50">
            {activeImage ? (
              <>
                <canvas
                  ref={previewCanvasRef}
                  className="w-full h-full"
                  style={{ display: "block" }}
                />
                <div className="absolute bottom-4 left-4 bg-white/90 backdrop-blur-md px-3 py-1 rounded-full text-xs font-mono text-[#004b87] border border-slate-200 shadow-sm">
                  IMG_SOURCE_0{activeIndex + 1}.RAW
                </div>
              </>
            ) : (
              <div className="w-full h-full flex flex-col items-center justify-center text-slate-400 gap-4">
                <div
                  id="container3D"
                  className="w-full max-w-2xl h-[400px] mx-auto rounded-xl border border-slate-800 bg-black/20"
                />
                <Script src="/viewer.js" type="module" strategy="afterInteractive" />
              </div>
            )}
          </div>

          {/* Filmstrip */}
          <div className="grid grid-cols-5 gap-4">
            {images.map((img, i) => (
              <motion.div
                key={i}
                whileHover={{ y: -4 }}
                whileTap={{ scale: 0.95 }}
                onClick={() => (img ? setActiveIndex(i) : triggerUpload(i))}
                className={`relative aspect-square rounded-xl cursor-pointer overflow-hidden border-2 transition-all duration-300 bg-white ${
                  activeIndex === i
                    ? "border-[#f57c00] shadow-[0_0_15px_rgba(245,124,0,0.2)]"
                    : "border-slate-200 hover:border-slate-400"
                }`}
              >
                <input
                  type="file"
                  className="hidden"
                  accept="image/*"
                  ref={(el) => { fileInputRefs.current[i] = el; }}
                  onChange={(e) => handleUpload(i, e.target.files?.[0] || null)}
                />
                {img ? (
                  <>
                    <img src={img} alt={`Upload ${i + 1}`} className="w-full h-full object-cover" />
                    <button
                      onClick={(e) => removeImage(e, i)}
                      className="absolute top-1 right-1 bg-white/80 hover:bg-red-50 text-red-600 p-1 rounded-md transition-colors shadow-sm"
                    >
                      <X className="w-3 h-3" />
                    </button>
                    {activeIndex === i && (
                      <div className="absolute inset-0 ring-4 ring-inset ring-[#f57c00]/20 rounded-xl pointer-events-none" />
                    )}
                  </>
                ) : (
                  <div className="w-full h-full flex flex-col items-center justify-center gap-1 group">
                    <Upload className="w-5 h-5 text-slate-400 group-hover:text-[#004b87] transition-colors" />
                    <span className="text-[10px] uppercase font-bold text-slate-400 group-hover:text-slate-600">Add</span>
                  </div>
                )}
              </motion.div>
            ))}
          </div>
        </div>

        {/* Right Column */}
        <div className="lg:col-span-4 flex flex-col gap-6">
          <Card className="bg-white border-slate-200 shadow-xl shadow-slate-200/50 p-6 flex-1 flex flex-col">
            <h3 className="text-lg font-bold text-slate-800 mb-6 border-b border-slate-100 pb-4">Configuration</h3>

            <div className="space-y-6 flex-1">
              <div className="space-y-2">
                <label className="text-sm text-slate-600 font-medium">Build Name</label>
                <input
                  type="text"
                  value={buildName}
                  onChange={(e) => setBuildName(e.target.value)}
                  disabled={isGenerating}
                  placeholder={`Build ${new Date().toLocaleDateString()}`}
                  maxLength={60}
                  className="w-full px-3 py-2 rounded-lg border border-slate-200 bg-slate-50 text-slate-800 text-sm placeholder:text-slate-400 focus:outline-none focus:ring-2 focus:ring-[#004b87]/30 focus:border-[#004b87] disabled:opacity-50"
                />
              </div>

              <div className="space-y-2">
                <div className="flex justify-between text-sm text-slate-600 font-medium">
                  <span>Rendering Detail</span>
                  <span className="text-[#004b87]">{detailLevel}</span>
                </div>
                <div className="h-2 bg-slate-100 rounded-full overflow-hidden">
                  <motion.div
                    animate={{ width: DETAIL_TO_PERCENT[detailLevel] }}
                    transition={{ duration: 0.4 }}
                    className="h-full bg-gradient-to-r from-[#f57c00] to-orange-400"
                  />
                </div>
              </div>

              <div className="space-y-2">
                <label className="text-sm text-slate-600 font-medium">Detail Level</label>
                <div className="grid grid-cols-3 gap-2">
                  {DETAIL_LEVELS.map((level) => {
                    const isActive = detailLevel === level;
                    return (
                      <button
                        key={level}
                        type="button"
                        onClick={() => setDetailLevel(level)}
                        disabled={isGenerating}
                        className={`py-2 rounded-lg text-sm font-medium transition ${
                          isActive
                            ? "bg-[#004b87] text-white shadow-md"
                            : "bg-slate-50 text-slate-600 hover:bg-slate-100 border border-slate-200"
                        } disabled:opacity-50 disabled:cursor-not-allowed`}
                      >
                        {level}
                      </button>
                    );
                  })}
                </div>
              </div>

              <div className="p-4 bg-blue-50 border border-blue-100 rounded-xl">
                <div className="flex items-start gap-3">
                  <Smartphone className="w-5 h-5 text-[#004b87] mt-0.5" />
                  <div className="space-y-1">
                    <p className="text-sm font-bold text-[#004b87]">Mobile Ready Output</p>
                    <p className="text-xs text-blue-800/70 leading-relaxed">
                      Your generated brick layout will include a digital guide optimized for mobile viewing during assembly.
                    </p>
                  </div>
                </div>
              </div>
            </div>

            <Button
              onClick={generateLayout}
              disabled={!hasAnyImage || isGenerating}
              className="w-full py-7 text-lg bg-[#f57c00] hover:bg-orange-600 text-white shadow-lg shadow-orange-500/20 mt-6 group font-bold"
            >
              {isGenerating ? (
                <>
                  <Loader2 className="mr-2 w-5 h-5 animate-spin" />
                  Generating…
                </>
              ) : (
                <>
                  Generate Layout
                  <ArrowRight className="ml-2 w-5 h-5 group-hover:translate-x-1 transition-transform" />
                </>
              )}
            </Button>
          </Card>
        </div>
      </div>
    </div>
  );
}
