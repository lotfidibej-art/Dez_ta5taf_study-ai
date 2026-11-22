"use client";

import React from "react";
import Link from "next/link";
import Image from "next/image";
import { usePathname } from "next/navigation";
import { Sparkles, BarChart3, BookOpen, Sun, Moon, Cpu, GraduationCap } from "lucide-react";
import { useTheme } from "./ThemeProvider";

interface NavbarProps {
  activeSessionTopic?: string | null;
  comprehensionRating?: number | null;
}

export default function Navbar({ activeSessionTopic, comprehensionRating }: NavbarProps) {
  const pathname = usePathname();
  const { theme, toggleTheme } = useTheme();

  const navItems = [
    { label: "Studio", href: "/", icon: Sparkles },
    { label: "Analytics & Mastery", href: "/analytics", icon: BarChart3 },
    { label: "Résumé Vault", href: "/resumes", icon: BookOpen },
  ];

  return (
    <header className="sticky top-0 z-50 w-full border-b border-slate-200/80 bg-white/80 backdrop-blur-md dark:border-zinc-800/80 dark:bg-zinc-950/80 transition-colors duration-200">
      <div className="mx-auto flex h-14 max-w-7xl items-center justify-between px-4 sm:px-6">
        {/* Brand / Logo */}
        <div className="flex items-center gap-6">
          <Link href="/" className="flex items-center gap-2.5 group">
            <div className="relative flex h-8 w-8 items-center justify-center rounded-lg bg-gradient-to-br from-indigo-500 via-purple-500 to-emerald-400 p-0.5 shadow-sm transition-transform group-hover:scale-105">
              <div className="flex h-full w-full items-center justify-center rounded-[7px] bg-white dark:bg-zinc-900 overflow-hidden">
                <Image
                  src="/icon.png"
                  alt="headRook"
                  width={24}
                  height={24}
                  className="rounded object-contain"
                  priority
                />
              </div>
            </div>
            <div className="flex flex-col">
              <div className="flex items-center gap-1.5">
                <span className="text-base font-extrabold tracking-tight text-slate-900 dark:text-zinc-100">
                  head<span className="text-indigo-600 dark:text-indigo-400">Rook</span>
                </span>
              </div>
            </div>
          </Link>

          {/* Nav Items */}
          <nav className="hidden md:flex items-center gap-1">
            {navItems.map((item) => {
              const Icon = item.icon;
              const isActive = pathname === item.href;
              return (
                <Link
                  key={item.href}
                  href={item.href}
                  className={`flex items-center gap-2 px-3 py-1.5 rounded-lg text-xs font-medium transition-all ${
                    isActive
                      ? "bg-slate-100 text-slate-900 dark:bg-zinc-800 dark:text-zinc-100 shadow-xs"
                      : "text-slate-600 hover:bg-slate-50 hover:text-slate-900 dark:text-zinc-400 dark:hover:bg-zinc-800/50 dark:hover:text-zinc-200"
                  }`}
                >
                  <Icon className={`h-3.5 w-3.5 ${isActive ? "text-indigo-500 dark:text-indigo-400" : ""}`} />
                  <span>{item.label}</span>
                </Link>
              );
            })}
          </nav>
        </div>

        {/* Right Controls */}
        <div className="flex items-center gap-3">
          {activeSessionTopic && (
            <div className="hidden lg:flex items-center gap-2 px-2.5 py-1 rounded-full bg-slate-100 dark:bg-zinc-800/80 border border-slate-200 dark:border-zinc-700/60 text-xs">
              <span className="h-1.5 w-1.5 rounded-full bg-emerald-500 animate-pulse" />
              <span className="max-w-[180px] truncate font-medium text-slate-700 dark:text-zinc-300">
                {activeSessionTopic}
              </span>
              {typeof comprehensionRating === "number" && (
                <span className="font-mono text-[11px] font-semibold text-emerald-600 dark:text-emerald-400">
                  {Math.round(comprehensionRating * 100)}%
                </span>
              )}
            </div>
          )}

          <div className="flex items-center gap-1.5 px-2.5 py-1 rounded-lg bg-slate-100 dark:bg-zinc-800/60 text-xs text-slate-700 dark:text-zinc-300 border border-slate-200/60 dark:border-zinc-700/50">
            <GraduationCap className="h-3.5 w-3.5 text-indigo-500" />
            <span className="font-mono text-[11px]">student_dev_01</span>
          </div>

          {/* Theme Toggle */}
          <button
            onClick={toggleTheme}
            aria-label="Toggle theme"
            className="flex h-8 w-8 items-center justify-center rounded-lg border border-slate-200 bg-white text-slate-600 shadow-2xs hover:bg-slate-50 dark:border-zinc-800 dark:bg-zinc-900 dark:text-zinc-300 dark:hover:bg-zinc-800 transition-colors"
          >
            {theme === "dark" ? (
              <Sun className="h-4 w-4 text-amber-400" />
            ) : (
              <Moon className="h-4 w-4 text-slate-700" />
            )}
          </button>
        </div>
      </div>
    </header>
  );
}
