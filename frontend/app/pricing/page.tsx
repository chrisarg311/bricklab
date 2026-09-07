"use client";

import { motion } from "framer-motion";
import { Check, Zap, Crown, Rocket } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import Link from "next/link";

const PRICING_PLANS = [
  {
    name: "Hobbyist",
    price: "Free",
    description: "Perfect for testing out your first brick build.",
    features: ["Standard Resolution", "5 Upload Slots", "PNG Export", "Community Support"],
    icon: <Zap className="w-6 h-6 text-slate-400" />,
    cta: "Start Building",
    highlight: false,
  },
  {
    name: "Architect",
    price: "$12",
    description: "The most popular choice for high-quality custom art.",
    features: [
      "High Resolution (4K)",
      "Unlimited Uploads",
      "PDF Building Instructions",
      "Brick Parts List (CSV)",
      "Priority Rendering",
    ],
    icon: <Rocket className="w-6 h-6 text-indigo-400" />,
    cta: "Upgrade to Pro",
    highlight: true,
  },
  {
    name: "Master Builder",
    price: "$29",
    description: "For creators who want the ultimate brick experience.",
    features: [
      "Everything in Architect",
      "3D Model Export (Studio file)",
      "Commercial License",
      "Advanced Color Matching",
      "VIP Support",
    ],
    icon: <Crown className="w-6 h-6 text-amber-400" />,
    cta: "Contact Sales",
    highlight: false,
  },
];

export default function PricingPage() {
  return (
    <div className="max-w-7xl mx-auto px-6 py-16">
      {/* Header */}
      <div className="text-center mb-16 space-y-4">
        <h1 className="text-4xl md:text-5xl font-bold text-white tracking-tight">
          Simple, Transparent <span className="text-indigo-500">Pricing</span>
        </h1>
        <p className="text-slate-400 max-w-2xl mx-auto text-lg">
          Choose the plan that fits your creative needs. Transform your memories into bricks today.
        </p>
      </div>

      {/* Pricing Grid */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-8 mb-16">
        {PRICING_PLANS.map((plan, index) => (
          <motion.div
            key={plan.name}
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: index * 0.1 }}
          >
            <Card className={`relative h-full p-8 flex flex-col bg-slate-900/40 border-slate-800 hover:border-slate-700 transition-colors ${plan.highlight ? 'ring-2 ring-indigo-500 border-transparent shadow-[0_0_40px_rgba(99,102,241,0.15)]' : ''}`}>
              {plan.highlight && (
                <div className="absolute -top-4 left-1/2 -translate-x-1/2 bg-indigo-500 text-white text-xs font-bold px-3 py-1 rounded-full uppercase tracking-widest">
                  Most Popular
                </div>
              )}

              <div className="mb-8">
                <div className="mb-4">{plan.icon}</div>
                <h3 className="text-xl font-bold text-white mb-2">{plan.name}</h3>
                <div className="flex items-baseline gap-1 mb-4">
                  <span className="text-4xl font-bold text-white">{plan.price}</span>
                  {plan.price !== "Free" && <span className="text-slate-500 text-sm">/one-time</span>}
                </div>
                <p className="text-sm text-slate-400 leading-relaxed">
                  {plan.description}
                </p>
              </div>

              <ul className="space-y-4 mb-8 flex-1">
                {plan.features.map((feature) => (
                  <li key={feature} className="flex items-center gap-3 text-sm text-slate-300">
                    <Check className="w-4 h-4 text-indigo-500 flex-shrink-0" />
                    {feature}
                  </li>
                ))}
              </ul>

              <Link href="/create" className="w-full">
                <Button 
                  className={`w-full py-6 font-semibold transition-all ${
                    plan.highlight 
                      ? 'bg-indigo-600 hover:bg-indigo-500 text-white' 
                      : 'bg-slate-800 hover:bg-slate-700 text-slate-200'
                  }`}
                >
                  {plan.cta}
                </Button>
              </Link>
            </Card>
          </motion.div>
        ))}
      </div>

      {/* Trust Section */}
      <div className="text-center py-12 border-t border-slate-800/50">
        <p className="text-sm text-slate-500 uppercase tracking-[0.2em] mb-8">Trusted by 10,000+ Brick Artists</p>
        <div className="flex flex-wrap justify-center gap-12 grayscale opacity-40">
            {/* You can put placeholder brand names here if you want */}
            <span className="text-xl font-bold text-white italic">BRICKLAB</span>
            <span className="text-xl font-bold text-white italic">PIXELBLOCK</span>
            <span className="text-xl font-bold text-white italic">ARTGRID</span>
        </div>
      </div>
    </div>
  );
}