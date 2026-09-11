"use client";

import { motion } from "framer-motion";
import {
  Accordion,
  AccordionContent,
  AccordionItem,
  AccordionTrigger,
} from "@/components/ui/accordion";
import { MessageCircleQuestion, Mail, MessageSquare } from "lucide-react";
import { Button } from "@/components/ui/button";

const FAQ_DATA = [
  {
    question: "How does PictoBrick work?",
    answer: "Our algorithm analyzes the colors and shapes in your uploaded photo and maps them to standard brick dimensions and colors. It calculates exactly which bricks you need to recreate the image in real life."
  },
  {
    question: "Which brick brands are supported?",
    answer: "While we provide universal building instructions and color codes, our system is optimized for standard 1x1 and 1x2 plates compatible with major brands like LEGO®."
  },
  {
    question: "Can I download the instructions?",
    answer: "Yes! With our Architect and Master Builder plans, you can export a high-resolution PDF building guide that shows you layer-by-layer how to assemble your masterpiece."
  },
  {
    question: "What is the 'Complexity' setting?",
    answer: "Complexity determines the 'resolution' of your brick art. High complexity uses smaller plates (1x1) for more detail, while lower complexity uses larger blocks for a more stylized, pixelated look."
  },
  {
    question: "Do you sell the actual bricks?",
    answer: "Currently, we provide the digital blueprints and a 'Parts List' (CSV). You can use this list to order the exact pieces you need from third-party brick marketplaces."
  }
];

export default function FAQPage() {
  return (
    <div className="max-w-4xl mx-auto px-6 py-16">
      {/* Header */}
      <motion.div 
        initial={{ opacity: 0, y: -10 }}
        animate={{ opacity: 1, y: 0 }}
        className="text-center mb-16 space-y-4"
      >
        <div className="inline-flex p-3 rounded-2xl bg-indigo-500/10 border border-indigo-500/20 mb-4">
          <MessageCircleQuestion className="w-8 h-8 text-indigo-400" />
        </div>
        <h1 className="text-4xl font-bold text-white tracking-tight">Questions? Answers.</h1>
        <p className="text-slate-400 text-lg">
          Everything you need to know about the PictoBrick process.
        </p>
      </motion.div>

      {/* Accordion */}
      <motion.div
        initial={{ opacity: 0 }}
        animate={{ opacity: 1 }}
        transition={{ delay: 0.2 }}
        className="bg-slate-900/40 border border-slate-800 rounded-3xl p-4 md:p-8"
      >
        <Accordion type="single" collapsible className="w-full">
          {FAQ_DATA.map((faq, index) => (
            <AccordionItem key={index} value={`item-${index}`} className="border-slate-800">
              <AccordionTrigger className="text-slate-200 hover:text-indigo-400 hover:no-underline py-6">
                {faq.question}
              </AccordionTrigger>
              <AccordionContent className="text-slate-400 leading-relaxed pb-6">
                {faq.answer}
              </AccordionContent>
            </AccordionItem>
          ))}
        </Accordion>
      </motion.div>

      {/* Contact Section */}
      <div className="mt-20 grid grid-cols-1 md:grid-cols-2 gap-6">
        <div className="p-8 bg-indigo-600 rounded-3xl text-white space-y-4">
          <Mail className="w-6 h-6" />
          <h3 className="text-xl font-bold">Email Support</h3>
          <p className="text-indigo-100 text-sm">
            Can't find what you're looking for? Our team typically responds within 24 hours.
          </p>
          <Button variant="secondary" className="bg-white text-indigo-600 hover:bg-indigo-50">
            Contact Us
          </Button>
        </div>

        <div className="p-8 bg-slate-900 border border-slate-800 rounded-3xl text-white space-y-4">
          <MessageSquare className="w-6 h-6 text-indigo-400" />
          <h3 className="text-xl font-bold">Community Discord</h3>
          <p className="text-slate-400 text-sm">
            Join 2,000+ other builders, share your layouts, and get tips from the pros.
          </p>
          <Button variant="outline" className="border-slate-700 hover:bg-slate-800">
            Join Discord
          </Button>
        </div>
      </div>
    </div>
  );
}