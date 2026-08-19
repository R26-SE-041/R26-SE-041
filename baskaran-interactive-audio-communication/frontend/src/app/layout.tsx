import type { Metadata } from 'next'
import './globals.css'

export const metadata: Metadata = {
  title: 'VoiceLearn AI — Voice-Powered Study Assistant',
  description: 'Ask questions about your study materials using your voice. Get answers in English, Tamil, or Sinhala.',
}

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en" className="h-full">
      <head />
      <body className="h-full antialiased">
        {children}
      </body>
    </html>
  )
}
