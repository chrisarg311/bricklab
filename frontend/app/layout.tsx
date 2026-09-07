import type { Metadata } from "next";
import { Geist, Geist_Mono } from "next/font/google";
import { ClerkProvider } from "@clerk/nextjs";
import "./globals.css";
import Navbar from "@/components/Navbar"; // Make sure you created this file in your components folder!

const geistSans = Geist({
  variable: "--font-geist-sans",
  subsets: ["latin"],
});

const geistMono = Geist_Mono({
  variable: "--font-geist-mono",
  subsets: ["latin"],
});

export const metadata: Metadata = {
  title: "PictoBrick | Brick Art Studio",
  description: "Transform your favorite photos into custom brick-style masterpieces.",
  icons: {
    icon: "/logobackgroundremoved.png",
  },
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <ClerkProvider
      afterSignOutUrl="/"
      appearance={{ variables: { colorPrimary: "#4f46e5" } }}
    >
      <html lang="en" className="dark">
        <body
          className={`${geistSans.variable} ${geistMono.variable} antialiased bg-[#0f172a] text-slate-200 min-h-screen flex flex-col`}
        >
          {/* The Navbar stays at the top of every page */}
          <Navbar />

          {/* Main content wrapper.
              pt-20 provides space so the fixed Navbar doesn't cover your content.
          */}
          <main className="flex-grow pt-20">
            {children}
          </main>

          {/* Simple Footer to make the site feel finished */}
          <footer className="border-t border-slate-800 bg-[#0f172a] py-8 mt-auto">
            <div className="max-w-7xl mx-auto px-6 flex flex-col md:flex-row justify-between items-center gap-4">
              <p className="text-sm text-slate-500">
                © {new Date().getFullYear()} PictoBrick Studio. All rights reserved.
              </p>
              <div className="flex gap-6 text-sm text-slate-400">
                <a href="#" className="hover:text-white transition">Terms</a>
                <a href="#" className="hover:text-white transition">Privacy</a>
                <a href="#" className="hover:text-white transition">Support</a>
              </div>
            </div>
          </footer>
        </body>
      </html>
    </ClerkProvider>
  );
}