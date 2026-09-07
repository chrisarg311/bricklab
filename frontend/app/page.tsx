"use client";

import { motion, Variants } from "framer-motion";
import Link from "next/link";
import Image from "next/image";
import { ArrowRight, Image as ImageIcon, SlidersHorizontal, Box, Layers } from "lucide-react";
import { Card } from "@/components/ui/card";

const fadeUp: Variants = {
  hidden: { opacity: 0, y: 20 },
  visible: { opacity: 1, y: 0, transition: { duration: 0.6, ease: "easeOut" } }
};

export default function HomePage() {


  return (
    <div className="min-h-screen bg-slate-50 text-slate-900 font-sans relative overflow-hidden flex flex-col">
      
      {/* Background Decor - Matched to Studio Page */}
      <div className="absolute top-0 left-0 w-full h-full overflow-hidden pointer-events-none z-0">
        <div className="absolute top-[-10%] right-[-5%] w-[500px] h-[500px] bg-[#f57c00]/5 rounded-full blur-[100px]" />
        <div className="absolute bottom-[-10%] left-[-5%] w-[600px] h-[600px] bg-[#004b87]/5 rounded-full blur-[120px]" />
      </div>

      {/* Hero Section */}
      <main className="flex-1 flex flex-col items-center justify-center relative z-10 px-6 pt-12 pb-24">
        <div className="max-w-7xl w-full grid lg:grid-cols-2 gap-12 items-center">
          
          {/* Hero Text */}
          <motion.div 
            initial="hidden"
            animate="visible"
            variants={{
              hidden: { opacity: 0 },
              visible: { opacity: 1, transition: { staggerChildren: 0.1 } }
            }}
            className="space-y-8"
          >
            <motion.div variants={fadeUp} className="inline-flex items-center gap-2 px-3 py-1.5 rounded-full bg-blue-50 border border-blue-100 text-[#004b87] text-xs font-bold uppercase tracking-wider">
              <Layers className="w-4 h-4" /> Professional Grade
            </motion.div>
            
            <motion.h1 variants={fadeUp} className="text-5xl lg:text-7xl font-black tracking-tight text-slate-800 leading-[1.1]">
              Your memories. <br/>
              <span className="text-transparent bg-clip-text bg-gradient-to-r from-[#f57c00] to-orange-400">
                Built brick by brick.
              </span>
            </motion.h1>
            
            <motion.p variants={fadeUp} className="text-lg text-slate-500 font-medium max-w-lg leading-relaxed">
              Upload your favorite photos and our advanced rendering engine instantly generates a custom, buildable mosaic art kit.
            </motion.p>
            
            <motion.div variants={fadeUp} className="flex items-center gap-4 pt-4">
              <Link href="/create">
                <button className="flex items-center gap-2 bg-[#f57c00] hover:bg-orange-600 text-white px-8 py-4 rounded-xl text-lg font-bold transition-all shadow-lg shadow-orange-500/20 hover:-translate-y-1">
                  Open Studio <ArrowRight className="w-5 h-5" />
                </button>
              </Link>
            </motion.div>
          </motion.div>

          {/* Hero Mockup (Matches the Studio Card Style) */}
          <motion.div
            initial={{ opacity: 0, scale: 0.95, rotate: 1 }}
            animate={{ opacity: 1, scale: 1, rotate: 0 }}
            transition={{ duration: 0.8, delay: 0.2 }}
            className="relative"
          >
            <Card className="bg-white/80 backdrop-blur-xl border border-slate-200 shadow-2xl shadow-slate-200/60 p-4 rounded-3xl flex flex-col gap-3">
              {/* Fake App Header */}
              <div className="flex items-center gap-2 px-2">
                <div className="w-3 h-3 rounded-full bg-red-300" />
                <div className="w-3 h-3 rounded-full bg-yellow-300" />
                <div className="w-3 h-3 rounded-full bg-green-300" />
              </div>

              {/* Photo 1 — HouseToLego (16:9) */}
              <div className="flex flex-col gap-1.5">
                <div className="relative w-full aspect-video bg-slate-100 rounded-2xl overflow-hidden">
                  <Image
                    src="/HouseToLego.png"
                    alt="House converted to LEGO mosaic"
                    fill
                    sizes="(max-width: 1024px) 100vw, 50vw"
                    className="object-contain"
                    priority
                  />
                </div>
                <p className="text-center text-xs font-semibold text-slate-400 tracking-wide uppercase"></p>
              </div>

              {/* Photo 2 — HouseBrickSet (4:3) */}
              <div className="flex flex-col gap-1.5">
                <div className="relative w-full aspect-[4/3] bg-slate-100 rounded-2xl overflow-hidden">
                  <Image
                    src="/HouseBrickSet.png"
                    alt="House brick set"
                    fill
                    sizes="(max-width: 1024px) 100vw, 50vw"
                    className="object-contain"
                    priority
                  />
                </div>
                <p className="text-center text-xs font-semibold text-slate-400 tracking-wide uppercase"></p>
              </div>
            </Card>
          </motion.div>
        </div>
      </main>

      {/* Features Section - Using Studio Cards */}
      <section id="how-it-works" className="relative z-10 max-w-7xl mx-auto w-full px-6 pb-24">
        <div className="grid md:grid-cols-3 gap-6">
          
          {/* Step 1 */}
          <Card className="bg-white border-slate-200 shadow-xl shadow-slate-200/40 p-8 rounded-3xl hover:-translate-y-1 transition-transform duration-300">
            <div className="w-14 h-14 rounded-2xl bg-blue-50 border border-blue-100 flex items-center justify-center text-[#004b87] mb-6">
              <ImageIcon className="w-7 h-7" />
            </div>
            <h3 className="text-xl font-bold text-slate-800 mb-3">1. Upload Photo</h3>
            <p className="text-slate-500 text-sm leading-relaxed">
              Choose any high-quality photo from your device. Our engine supports ultra-high resolutions for maximum detail.
            </p>
          </Card>

          {/* Step 2 */}
          <Card className="bg-white border-slate-200 shadow-xl shadow-slate-200/40 p-8 rounded-3xl hover:-translate-y-1 transition-transform duration-300">
            <div className="w-14 h-14 rounded-2xl bg-orange-50 border border-orange-100 flex items-center justify-center text-[#f57c00] mb-6">
              <SlidersHorizontal className="w-7 h-7" />
            </div>
            <h3 className="text-xl font-bold text-slate-800 mb-3">2. Configure Details</h3>
            <p className="text-slate-500 text-sm leading-relaxed">
              Use the workspace to crop, adjust complexity, and select your ideal canvas dimensions and color palettes.
            </p>
          </Card>

          {/* Step 3 */}
          <Card className="bg-white border-slate-200 shadow-xl shadow-slate-200/40 p-8 rounded-3xl hover:-translate-y-1 transition-transform duration-300">
            <div className="w-14 h-14 rounded-2xl bg-blue-50 border border-blue-100 flex items-center justify-center text-[#004b87] mb-6">
              <Box className="w-7 h-7" />
            </div>
            <h3 className="text-xl font-bold text-slate-800 mb-3">3. Build Your Kit</h3>
            <p className="text-slate-500 text-sm leading-relaxed">
              We ship you a premium kit with perfectly color-matched bricks and a mobile-optimized instruction guide.
            </p>
          </Card>

        </div>
      </section>

    </div>
  );
}