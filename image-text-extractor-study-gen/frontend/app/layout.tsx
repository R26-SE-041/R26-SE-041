import type { Metadata } from "next";
import { Inter, Noto_Sans_Sinhala } from "next/font/google";
import "./globals.css";

const inter = Inter({
  subsets: ["latin"],
  variable: "--font-inter",
  display: "swap",
});

const sinhala = Noto_Sans_Sinhala({
  subsets: ["sinhala"],
  variable: "--font-sinhala",
  display: "swap",
});

export const metadata: Metadata = {
  title: "Sinhala Handwritten OCR — SRCNN + TrOCR",
  description:
    "Upload a low-quality Sinhala handwritten image to enhance it 4x with SRCNN super-resolution and extract Sinhala text with a fine-tuned TrOCR model — powered by Modal serverless GPU inference.",
  keywords: ["SRCNN", "TrOCR", "OCR", "Sinhala OCR", "image enhancement", "super resolution", "handwritten"],
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="si" className={`${inter.variable} ${sinhala.variable}`}>
      <body className="antialiased">{children}</body>
    </html>
  );
}
