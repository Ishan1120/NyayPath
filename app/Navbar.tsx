"use client";

import React, { useState, useEffect } from "react";
import Image from "next/image";
import { useRouter } from "next/navigation";
import {
  Gavel,
  Menu,
  X,
  Scale,
  Newspaper,
  BookOpen,
  GraduationCap,
  Clock,
  LayoutDashboard,
  Briefcase,
  UserCheck
} from "lucide-react";
import Link from "next/link";

export default function Navbar() {
  const router = useRouter();
  const [mobileMenuOpen, setMobileMenuOpen] = useState(false);
  const [isLoggedIn, setIsLoggedIn] = useState(false);

  useEffect(() => {
    if (typeof window !== "undefined") {
      const token =
        localStorage.getItem("nyaypath_citizen_token") ||
        localStorage.getItem("nyaypath_token") ||
        localStorage.getItem("nyaypath_proctor_token");
      setIsLoggedIn(!!token);
    }
  }, []);

  const navLinks = [
    { name: "Dashboard", href: "/dashboard", icon: LayoutDashboard },
    { name: "My Cases", href: "/dashboard/my-cases", icon: Briefcase },
    { name: "Case Search", href: "/case-search", icon: BookOpen },
    { name: "College Proctor", href: "/campus-proctor", icon: GraduationCap },
    { name: "Court News", href: "/court-news", icon: Newspaper },
    { name: "Track SLA", href: "/track", icon: Clock },
  ];

  const handleLaunch = () => {
    router.push("/dashboard?tab=assistant");
  };

  return (
    <header className="fixed top-0 left-0 right-0 z-50 px-4 pt-4 font-sans">
      <nav className="max-w-6xl mx-auto bg-white/95 backdrop-blur-md border border-slate-200/90 rounded-full shadow-lg shadow-slate-900/5 ring-1 ring-black/5">
        <div className="px-5 sm:px-7">
          <div className="flex items-center justify-between h-14">
            {/* Brand Logo */}
            <Link href="/" className="flex items-center shrink-0 py-1">
              <Image
                src="/nyaypath-logo.png"
                alt="NyayPath"
                width={200}
                height={160}
                className="object-contain h-9 sm:h-10 w-auto"
                priority
              />
            </Link>

            {/* Desktop Navigation Links */}
            <div className="hidden lg:flex items-center gap-5 text-xs font-bold tracking-tight text-slate-700 uppercase">
              {navLinks.map((link) => {
                const Icon = link.icon;
                return (
                  <Link
                    key={link.name}
                    href={link.href}
                    className="hover:text-court-maroon transition-colors flex items-center gap-1 py-1"
                  >
                    <Icon size={13} className="text-slate-400 group-hover:text-court-maroon" />
                    <span>{link.name}</span>
                  </Link>
                );
              })}
            </div>

            {/* Action CTA & Mobile Toggle */}
            <div className="flex items-center gap-2.5">
              <button
                onClick={handleLaunch}
                className="inline-flex items-center gap-1.5 px-4 py-2 rounded-full bg-gradient-to-r from-court-maroon via-rose-700 to-court-maroon hover:from-rose-700 hover:to-rose-800 text-white text-[11px] font-bold uppercase tracking-wider transition-all shrink-0 cursor-pointer shadow-md shadow-rose-950/20 active:scale-95"
              >
                <Gavel className="w-3.5 h-3.5 text-amber-300 shrink-0" />
                <span>Launch Engine</span>
              </button>

              <button
                onClick={() => setMobileMenuOpen(!mobileMenuOpen)}
                className="lg:hidden p-1.5 text-slate-700 hover:bg-slate-100 rounded-lg transition-colors cursor-pointer"
                aria-label="Toggle Navigation"
              >
                {mobileMenuOpen ? <X className="w-5 h-5" /> : <Menu className="w-5 h-5" />}
              </button>
            </div>
          </div>
        </div>

        {/* Mobile Navigation Drawer */}
        {mobileMenuOpen && (
          <div className="lg:hidden border-t border-slate-200 px-4 pt-3 pb-4 space-y-1 bg-white rounded-b-3xl mt-1 shadow-xl">
            {navLinks.map((link) => {
              const Icon = link.icon;
              return (
                <Link
                  key={link.name}
                  href={link.href}
                  onClick={() => setMobileMenuOpen(false)}
                  className="flex items-center gap-2 px-3 py-2.5 rounded-xl text-xs font-bold text-slate-800 hover:bg-rose-50 hover:text-court-maroon transition-colors"
                >
                  <Icon size={15} className="text-slate-400" />
                  <span>{link.name}</span>
                </Link>
              );
            })}
          </div>
        )}
      </nav>
    </header>
  );
}
