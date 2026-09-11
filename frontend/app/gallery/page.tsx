"use client";

import { motion } from "framer-motion";
import { Card } from "@/components/ui/card";
import { ExternalLink, Heart } from "lucide-react";
import Link from "next/link"; // Added for navigation
import { Button } from "@/components/ui/button";

// Placeholder data for the showcase
const SAMPLE_GALLERY = [
  { id: 1, title: "Sunset Skyline", creator: "Alex", size: "Large", color: "bg-orange-500/20" },
  { id: 2, title: "Cyberpunk Portrait", creator: "Jordan", size: "Medium", color: "bg-purple-500/20" },
  { id: 3, title: "Mountain Peak", creator: "Sam", size: "Small", color: "bg-blue-500/20" },
  { id: 4, title: "Classic Still Life", creator: "Taylor", size: "Large", color: "bg-emerald-500/20" },
  { id: 5, title: "Abstract Geometry", creator: "Casey", size: "Medium", color: "bg-pink-500/20" },
  { id: 6, title: "Golden Retriever", creator: "Riley", size: "Small", color: "bg-yellow-500/20" },
];

export default function GalleryPage() {
  return (
    <div className="max-w-7xl mx-auto px-6 py-12">
      {/* Header Section */}
      <div className="mb-12 space-y-4 text-center md:text-left">
        <h1 className="text-4xl font-bold text-white tracking-tight">Community Showcase</h1>
        <p className="text-slate-400 max-w-2xl">
          Explore the latest creations from the PictoBrick community. Every piece started as a 
          standard photograph and was transformed into a brick-build masterpiece.
        </p>
      </div>

      {/* Gallery Grid */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-8">
        {SAMPLE_GALLERY.map((item, index) => (
          <motion.div
            key={item.id}
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: index * 0.1 }}
          >
            <Card className="group relative bg-slate-900/40 border-slate-800 overflow-hidden hover:border-indigo-500/50 transition-all duration-300">
              {/* Image Placeholder */}
              <div className={`aspect-[4/5] w-full ${item.color} flex items-center justify-center relative overflow-hidden`}>
                <div className="absolute inset-0 opacity-20 group-hover:scale-110 transition-transform duration-700" 
                     style={{ backgroundImage: 'radial-gradient(circle, #fff 1px, transparent 1px)', backgroundSize: '20px 20px' }} />
                <span className="text-slate-500 font-mono text-xs z-10">PREVIEW_IMAGE_0{item.id}</span>
                
                {/* Hover Overlay */}
                <div className="absolute inset-0 bg-black/60 opacity-0 group-hover:opacity-100 transition-opacity flex items-center justify-center gap-4">
                   <button className="p-3 bg-white/10 rounded-full hover:bg-white/20 transition backdrop-blur-md">
                      <Heart className="w-5 h-5 text-white" />
                   </button>
                   <button className="p-3 bg-indigo-600 rounded-full hover:bg-indigo-500 transition shadow-xl">
                      <ExternalLink className="w-5 h-5 text-white" />
                   </button>
                </div>
              </div>

              {/* Info Section */}
              <div className="p-4 bg-slate-900/80 backdrop-blur-sm border-t border-slate-800">
                <div className="flex justify-between items-start mb-2">
                  <h3 className="text-white font-medium">{item.title}</h3>
                  {/* Custom Span instead of Shadcn Badge to avoid missing module errors */}
                  <span className="text-[10px] border border-slate-700 text-slate-400 px-2 py-0.5 rounded-full uppercase font-semibold">
                    {item.size}
                  </span>
                </div>
                <p className="text-sm text-slate-500 flex items-center gap-1">
                  by <span className="text-indigo-400 hover:underline cursor-pointer">@{item.creator.toLowerCase()}</span>
                </p>
              </div>
            </Card>
          </motion.div>
        ))}
      </div>

      {/* Empty State Call-to-Action */}
      <div className="mt-20 p-12 rounded-3xl border border-dashed border-slate-800 text-center space-y-6 bg-slate-900/20">
        <h2 className="text-2xl font-semibold text-white">Your masterpiece belongs here.</h2>
        <p className="text-slate-400 max-w-md mx-auto">
          Start building your own custom brick art and share it with the world.
        </p>
        
        <Link href="/create">
          <Button 
            className="px-8 py-6 bg-indigo-600 hover:bg-indigo-500 text-white rounded-full font-medium transition shadow-lg shadow-indigo-500/20"
          >
            Open Studio
          </Button>
        </Link>
      </div>
    </div>
  );
}