import type { Metadata } from "next";
import { Inter } from "next/font/google";
import "./globals.css";

const inter = Inter({
  subsets: ["latin"],
  variable: "--font-inter",
  display: "swap",
});

export const metadata: Metadata = {
  title: "AdaptiveIQ — AI-Powered Quiz Generator",
  description:
    "Upload your study materials and get an adaptive quiz powered by Qwen2.5-7B AI. Questions adapt to your performance in real-time.",
  keywords: ["adaptive quiz", "AI quiz", "study tool", "RAG", "LangGraph"],
  openGraph: {
    title: "AdaptiveIQ — AI-Powered Quiz Generator",
    description: "Upload docs. Get smart questions. Ace your exams.",
    type: "website",
  },
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en" className={inter.variable}>
      <body className="bg-[#03050f] text-white antialiased min-h-screen">
        {/* Ambient background orbs */}
        <div className="fixed inset-0 overflow-hidden pointer-events-none z-0" aria-hidden="true">
          <div className="absolute -top-40 -left-40 w-96 h-96 rounded-full blur-[120px]" style={{ background: "rgba(124,58,237,0.2)" }} />
          <div className="absolute top-1/2 -right-40 w-80 h-80 rounded-full blur-[100px]" style={{ background: "rgba(34,211,238,0.12)" }} />
          <div className="absolute bottom-0 left-1/3 w-72 h-72 rounded-full blur-[90px]" style={{ background: "rgba(139,92,246,0.1)" }} />
        </div>
        <div className="relative z-10">{children}</div>
      </body>
    </html>
  );
}
