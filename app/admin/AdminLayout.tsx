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
import { loginPlatformAdmin } from '@/lib/api';

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
  const [isAuthenticated, setIsAuthenticated] = useState<boolean>(false);
  const [adminEmail, setAdminEmail] = useState<string>('');
  const [isInitializing, setIsInitializing] = useState<boolean>(true);

  // Interactive admin login state
  const [loginEmail, setLoginEmail] = useState<string>('');
  const [loginPassword, setLoginPassword] = useState<string>('');
  const [isLoggingIn, setIsLoggingIn] = useState<boolean>(false);
  const [loginError, setLoginError] = useState<string | null>(null);

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

      // Authoritative verification requires both token and platform_admin role
      if (!token || role !== 'platform_admin') {
        setIsAuthenticated(false);
      } else {
        setIsAuthenticated(true);
      }
      setIsInitializing(false);
    }
  }, []);

  const handleAdminLogin = async (e: React.FormEvent) => {
    e.preventDefault();
    setLoginError(null);
    if (!loginEmail.trim() || !loginPassword) {
      setLoginError('Please enter both administrative email and password.');
      return;
    }
    setIsLoggingIn(true);
    try {
      const res = await loginPlatformAdmin({
        email: loginEmail.trim(),
        password: loginPassword
      });
      if (res && res.token) {
        localStorage.setItem('nyaypath_platform_admin_token', res.token);
        localStorage.setItem('nyaypath_user_role', 'platform_admin');
        localStorage.setItem('nyaypath_user', JSON.stringify(res.user));
        setAdminEmail(res.user?.email || loginEmail.trim());
        setLoginPassword('');
        setIsAuthenticated(true);
      } else {
        setLoginError('Authentication succeeded but no administrative token returned.');
      }
    } catch (err: any) {
      console.error('Platform admin authentication failed:', err);
      const detail =
        err?.response?.data?.detail ||
        'Invalid administrative credentials or insufficient privileges.';
      setLoginError(detail);
    } finally {
      setIsLoggingIn(false);
    }
  };

  const handleLogout = () => {
    if (typeof window !== 'undefined') {
      localStorage.removeItem('nyaypath_platform_admin_token');
      localStorage.removeItem('nyaypath_token');
      localStorage.removeItem('nyaypath_user_role');
      localStorage.removeItem('nyaypath_user');
      setIsAuthenticated(false);
      setAdminEmail('');
      setLoginPassword('');
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
              {isAuthenticated && (
                <>
                  <div className="bg-black/30 border border-white/10 px-4 py-2 rounded-xl text-right">
                    <div className="text-xs text-slate-400">Authenticated Identity</div>
                    <div className="text-sm font-medium text-court-gold truncate max-w-[220px]">
                      {adminEmail || 'Platform Admin'}
                    </div>
                  </div>
                  <button
                    onClick={handleLogout}
                    className="inline-flex items-center gap-1.5 px-3 py-2 rounded-xl text-xs font-semibold bg-white/10 hover:bg-white/20 text-white border border-white/20 transition-all"
                    title="End Administrator Session"
                  >
                    <Lock className="w-3.5 h-3.5" />
                    Sign Out
                  </button>
                </>
              )}
            </div>
          </div>

          {/* Sub Navigation Bar (visible when authenticated) */}
          {isAuthenticated && (
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
          )}
        </div>

        {/* Content Body */}
        {!isInitializing && !isAuthenticated ? (
          <div className="bg-white rounded-2xl border border-slate-200 p-8 max-w-md mx-auto my-12 shadow-lg">
            <div className="flex items-center justify-center w-12 h-12 rounded-full bg-court-maroon/10 text-court-maroon mx-auto mb-4">
              <Lock className="w-6 h-6" />
            </div>
            <h2 className="text-xl font-serif font-bold text-slate-900 text-center mb-1">
              Platform Admin Authentication
            </h2>
            <p className="text-xs text-slate-500 text-center mb-6">
              Enter authoritative platform administrator credentials to access system management.
            </p>

            {loginError && (
              <div className="mb-4 p-3 rounded-xl bg-red-50 border border-red-200 flex items-start gap-2 text-xs text-red-700">
                <AlertTriangle className="w-4 h-4 shrink-0 mt-0.5" />
                <span>{loginError}</span>
              </div>
            )}

            <form onSubmit={handleAdminLogin} className="space-y-4">
              <div>
                <label className="block text-xs font-semibold text-slate-700 mb-1">
                  Administrator Email
                </label>
                <input
                  type="email"
                  required
                  autoComplete="username"
                  value={loginEmail}
                  onChange={(e) => setLoginEmail(e.target.value)}
                  placeholder="admin@nyaypath.gov"
                  className="w-full px-3.5 py-2.5 rounded-xl border border-slate-300 text-sm focus:outline-none focus:ring-2 focus:ring-court-maroon focus:border-transparent text-slate-900"
                />
              </div>

              <div>
                <label className="block text-xs font-semibold text-slate-700 mb-1">
                  Password
                </label>
                <input
                  type="password"
                  required
                  autoComplete="current-password"
                  value={loginPassword}
                  onChange={(e) => setLoginPassword(e.target.value)}
                  placeholder="••••••••••••"
                  className="w-full px-3.5 py-2.5 rounded-xl border border-slate-300 text-sm focus:outline-none focus:ring-2 focus:ring-court-maroon focus:border-transparent text-slate-900"
                />
              </div>

              <button
                type="submit"
                disabled={isLoggingIn || !loginEmail || !loginPassword}
                className="w-full inline-flex items-center justify-center gap-2 px-5 py-2.5 rounded-xl text-sm font-semibold text-white bg-court-maroon hover:bg-court-maroon/90 shadow transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
              >
                {isLoggingIn ? 'Authenticating...' : 'Sign In as Platform Admin'}
                <ArrowRight className="w-4 h-4" />
              </button>
            </form>
          </div>
        ) : (
          children
        )}
      </main>
    </div>
  );
}
