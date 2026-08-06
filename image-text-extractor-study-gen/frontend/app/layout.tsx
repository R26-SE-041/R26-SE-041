import type { Metadata } from "next";
import { Inter } from "next/font/google";
import "./globals.css";

const inter = Inter({
  subsets: ["latin"],
  variable: "--font-inter",
  display: "swap",
});

export const metadata: Metadata = {
  title: "Image Enhancement & OCR — SRCNN + TrOCR",
  description:
    "Upload a low-quality image to enhance it 4× with SRCNN super-resolution and extract text with Microsoft TrOCR — powered by Modal serverless GPU inference.",
  keywords: ["SRCNN", "TrOCR", "OCR", "image enhancement", "super resolution"],
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en" className={inter.variable}>
      <body className="antialiased">{children}</body>
    </html>
  );
}
