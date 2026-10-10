import type { Metadata } from "next";
import "./globals.css";
import ThemeToggle from "@/components/ui/ThemeToggle";

export const metadata: Metadata = {
  title: "AdaptiveIQ | AI-Powered Quiz Generator",
  description:
    "Upload your study materials and get an adaptive quiz powered by Qwen2.5-7B AI. Questions adapt to your performance in real-time.",
  keywords: ["adaptive quiz", "AI quiz", "study tool", "RAG", "LangGraph"],
  openGraph: {
    title: "AdaptiveIQ | AI-Powered Quiz Generator",
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
    <html lang="en">
      <body className="antialiased min-h-screen">
        <div className="paper-background fixed inset-0 pointer-events-none z-0" aria-hidden="true" />
        <div className="ambient-blob ambient-top-right" aria-hidden="true" />
        <div className="ambient-blob ambient-bottom-left" aria-hidden="true" />
        <ThemeToggle />
        <div className="relative z-10">{children}</div>
      </body>
    </html>
  );
}
