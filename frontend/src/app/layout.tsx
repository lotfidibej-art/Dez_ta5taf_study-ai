import type { Metadata } from "next";
import { Plus_Jakarta_Sans, JetBrains_Mono } from "next/font/google";
import "./globals.css";
import { ThemeProvider } from "@/components/ThemeProvider";

const plusJakartaSans = Plus_Jakarta_Sans({
  variable: "--font-sans",
  subsets: ["latin"],
  weight: ["400", "500", "600", "700", "800"],
  display: "swap",
});

const jetbrainsMono = JetBrains_Mono({
  variable: "--font-mono",
  subsets: ["latin"],
  weight: ["400", "500", "600"],
  display: "swap",
});

export const metadata: Metadata = {
  title: "headRook",
  description: "Adaptive AI Learning Platform with multi-modal scaffolding, real-time prosody analysis, and mistake remediation.",
  icons: {
    icon: "/icon.png",
  },
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html
      lang="en"
      className={`${plusJakartaSans.variable} ${jetbrainsMono.variable} h-full dark`}
      suppressHydrationWarning
    >
      <body className="min-h-full flex flex-col font-sans antialiased bg-slate-50 text-slate-900 dark:bg-zinc-950 dark:text-zinc-100 transition-colors duration-150 relative overflow-x-hidden">
        {/* Left Banner: Icon covering the left side of the screen with gradient transparency towards the middle */}
        <div
          aria-hidden="true"
          className="fixed inset-y-0 left-0 w-full sm:w-[48vw] lg:w-[40vw] pointer-events-none z-0 overflow-hidden select-none"
        >
          <div
            className="absolute inset-0 bg-cover bg-left sm:bg-center bg-no-repeat opacity-50 dark:opacity-40 scale-100 origin-left"
            style={{ backgroundImage: `url('/icon.png')` }}
          />
          {/* Horizontal gradient transparency towards the middle */}
          <div className="absolute inset-0 bg-gradient-to-r from-transparent via-slate-50/60 to-slate-50 dark:via-zinc-950/70 dark:to-zinc-950" />
          {/* Vertical subtle edge blend */}
          <div className="absolute inset-0 bg-gradient-to-b from-slate-50/30 via-transparent to-slate-50/80 dark:from-zinc-950/30 dark:via-transparent dark:to-zinc-950/80" />
        </div>

        <ThemeProvider>
          <div className="relative z-10 flex-1 flex flex-col min-h-screen">
            {children}
          </div>
        </ThemeProvider>
      </body>
    </html>
  );
}
