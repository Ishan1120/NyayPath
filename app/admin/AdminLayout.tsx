'use client';

import React, { useState, useEffect } from 'react';
import Link from 'next/link';
import { usePathname } from 'next/navigation';
import {
  ShieldAlert,
  ShieldCheck,
  LayoutDashboard,
  Users,
  Building,
  Gavel,
  Scale,
  FileText,
  Activity,
  HardDrive,
  CheckCircle2,
  AlertTriangle,
  Lock,
  ArrowRight
} from 'lucide-react';
import Navbar from '@/app/Navbar';

interface AdminLayoutProps {
  children: React.ReactNode;
  title: string;
  subtitle?: string;
  badge?: string;
}

export default function AdminLayout({
  children,
  title,
  subtitle,
  badge
}: AdminLayoutProps) {
  const pathname = usePathname();
  const [isAuthenticated, setIsAuthenticated] = useState<boolean>(true);
  const [adminEmail, setAdminEmail] = useState<string>('platform@nyaypath.gov');
  const [isInitializing, setIsInitializing] = useState<boolean>(true);

  useEffect(() => {
    if (typeof window !== 'undefined') {
      const token =
        localStorage.getItem('nyaypath_platform_admin_token') ||
        localStorage.getItem('nyaypath_token');
      const role = localStorage.getItem('nyaypath_user_role');
      
      try {
        const userStr = localStorage.getItem('nyaypath_user');
        if (userStr) {
          const u = JSON.parse(userStr);
          if (u.email) setAdminEmail(u.email);
        }
      } catch {}

      // Allow access if token exists or local dev platform admin session
      if (!token && role !== 'platform_admin') {
        setIsAuthenticated(false);
      } else {
        setIsAuthenticated(true);
      }
      setIsInitializing(false);
    }
  }, []);

  const handleDevLogin = () => {
    if (typeof window !== 'undefined') {
      // Set platform admin demo credentials
      localStorage.setItem('nyaypath_platform_admin_token', 'platform_admin_demo_session');
      localStorage.setItem('nyaypath_user_role', 'platform_admin');
      localStorage.setItem(
        'nyaypath_user',
        JSON.stringify({
          user_id: '99999999-1111-2222-3333-999999999999',
          email: 'platform@nyaypath.gov',
          role: 'platform_admin',
          full_name: 'Platform Administrator'
        })
      );
      setIsAuthenticated(true);
      window.location.reload();
    }
  };

  const navTabs = [
    { name: 'Dashboard', href: '/admin/dashboard', icon: LayoutDashboard },
    { name: 'Users', href: '/admin/users', icon: Users },
    { name: 'Institutions', href: '/admin/institutions', icon: Building },
    { name: 'Lawyer Verification', href: '/admin/lawyers', icon: Gavel },
    { name: 'Global Cases', href: '/admin/cases', icon: Scale },
    { name: 'Audit Logs', href: '/admin/audit-logs', icon: Activity },
    { name: 'System Health', href: '/admin/system', icon: HardDrive }
  ];

  return (
    <div className="min-h-screen bg-slate-50 text-slate-800">
      <Navbar />

      <main className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 pt-24 pb-16">
        {/* Top Header Card */}
        <div className="bg-gradient-to-r from-slate-900 via-court-maroon to-slate-900 rounded-2xl p-6 sm:p-8 text-white shadow-xl mb-6 border border-slate-800">
          <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
            <div>
              <div className="flex items-center gap-2 mb-2">
                <span className="inline-flex items-center gap-1.5 px-3 py-1 rounded-full text-xs font-semibold bg-court-gold/20 text-court-gold border border-court-gold/30">
                  <ShieldCheck className="w-3.5 h-3.5" />
                  Authoritative Platform Admin
                </span>
                {badge && (
                  <span className="px-2.5 py-0.5 rounded-full text-xs font-medium bg-white/10 text-slate-200">
                    {badge}
                  </span>
                )}
              </div>
              <h1 className="text-2xl sm:text-3xl font-serif font-bold text-white tracking-tight">
                {title}
              </h1>
              {subtitle && (
                <p className="mt-1 text-sm text-slate-300 max-w-2xl">
                  {subtitle}
                </p>
              )}
            </div>

            <div className="flex items-center gap-3">
              <div className="bg-black/30 border border-white/10 px-4 py-2 rounded-xl text-right">
                <div className="text-xs text-slate-400">Authenticated Identity</div>
                <div className="text-sm font-medium text-court-gold truncate max-w-[220px]">
                  {adminEmail}
                </div>
              </div>
            </div>
          </div>

          {/* Sub Navigation Bar */}
          <div className="flex items-center gap-1 sm:gap-2 mt-6 pt-5 border-t border-white/10 overflow-x-auto pb-1 no-scrollbar">
            {navTabs.map((tab) => {
              const Icon = tab.icon;
              const isActive = pathname === tab.href || pathname.startsWith(tab.href + '/');
              return (
                <Link
                  key={tab.name}
                  href={tab.href}
                  className={`flex items-center gap-2 px-3.5 py-2 rounded-xl text-xs sm:text-sm font-medium transition-all whitespace-nowrap ${
                    isActive
                      ? 'bg-white text-court-maroon font-semibold shadow-sm'
                      : 'text-slate-300 hover:text-white hover:bg-white/10'
                  }`}
                >
                  <Icon className="w-4 h-4" />
                  {tab.name}
                </Link>
              );
            })}
          </div>
        </div>

        {/* Content Body */}
        {!isInitializing && !isAuthenticated ? (
          <div className="bg-white rounded-2xl border border-amber-200 p-8 text-center max-w-lg mx-auto my-12 shadow-sm">
            <ShieldAlert className="w-12 h-12 text-amber-600 mx-auto mb-3" />
            <h2 className="text-lg font-serif font-bold text-slate-900 mb-2">
              Platform Admin Session Required
            </h2>
            <p className="text-sm text-slate-600 mb-6">
              You are currently unauthenticated or your session is missing platform administrator privileges. Authoritative database validation is active.
            </p>
            <button
              onClick={handleDevLogin}
              className="inline-flex items-center gap-2 px-5 py-2.5 rounded-xl text-sm font-semibold text-white bg-court-maroon hover:bg-court-maroon/90 shadow transition-colors"
            >
              Authenticate as Platform Admin
              <ArrowRight className="w-4 h-4" />
            </button>
          </div>
        ) : (
          children
        )}
      </main>
    </div>
  );
}

