'use client';

import React, { useState, useEffect } from 'react';
import Link from 'next/link';
import { useRouter } from 'next/navigation';
import { motion } from 'framer-motion';
import {
  LayoutDashboard,
  Briefcase,
  FileText,
  CheckCircle2,
  Clock,
  AlertTriangle,
  ArrowRight,
  PlusCircle,
  GraduationCap,
  Newspaper,
  BookOpen,
  Scale,
  ShieldCheck,
  UserCheck,
  LogOut,
  LogIn,
  FolderOpen,
  Sparkles,
  RefreshCw,
  Search,
  ExternalLink,
  ChevronRight
} from 'lucide-react';
import GatewayView from '@/views/GatewayView';
import { getCitizenDashboardStats, loginCitizen } from '@/lib/api';

export default function DashboardPage() {
  const router = useRouter();
  const [activeTab, setActiveTab] = useState<'overview' | 'assistant'>('overview');
  const [statsLoading, setStatsLoading] = useState(true);
  const [statsError, setStatsError] = useState<string | null>(null);
  const [statsData, setStatsData] = useState<{
    stats: {
      total_cases: number;
      active_cases: number;
      resolved_cases: number;
      pending_actions: number;
    };
    recent_cases: Array<{
      id: string;
      case_id: string;
      category: string;
      subject: string;
      description: string;
      status: string;
      severity: string;
      created_at: string;
      updated_at: string;
      hearing_date?: string;
      action_taken?: string;
    }>;
    user_profile: {
      user_id: string;
      name: string;
      email: string;
      role: string;
      institution_id: string;
    };
  } | null>(null);

  // Auth modal state for signing in
  const [showAuthModal, setShowAuthModal] = useState(false);
  const [authEmail, setAuthEmail] = useState('');
  const [authPassword, setAuthPassword] = useState('');
  const [authLoading, setAuthLoading] = useState(false);
  const [authError, setAuthError] = useState<string | null>(null);

  const fetchStats = async () => {
    setStatsLoading(true);
    setStatsError(null);
    try {
      const res = await getCitizenDashboardStats();
      setStatsData(res);
    } catch (err: any) {
      if (err?.response?.status === 401) {
        setStatsError('UNAUTHENTICATED');
      } else {
        setStatsError(err?.response?.data?.detail || 'Failed to load case statistics.');
      }
    } finally {
      setStatsLoading(false);
    }
  };

  useEffect(() => {
    fetchStats();
  }, []);

  const handleQuickLogin = async (email: string, pass: string) => {
    setAuthLoading(true);
    setAuthError(null);
    try {
      const res = await loginCitizen({ email, password: pass });
      if (res?.token && res?.user) {
        localStorage.setItem('nyaypath_citizen_token', res.token);
        localStorage.setItem('nyaypath_token', res.token);
        if (res.user.role === 'lawyer') {
          localStorage.setItem('nyaypath_lawyer_token', res.token);
        }
        localStorage.setItem('nyaypath_user', JSON.stringify(res.user));
        setShowAuthModal(false);
        fetchStats();
      } else {
        setAuthError('Authentication failed: Invalid credentials.');
      }
    } catch (err: any) {
      setAuthError(err?.response?.data?.detail || 'Login failed. Please check credentials.');
    } finally {
      setAuthLoading(false);
    }
  };

  const handleSignOut = () => {
    localStorage.removeItem('nyaypath_citizen_token');
    localStorage.removeItem('nyaypath_user');
    setStatsData(null);
    setStatsError('UNAUTHENTICATED');
  };

  const getStatusColor = (status: string) => {
    switch (status?.toUpperCase()) {
      case 'RESOLVED':
      case 'CLOSED':
      case 'COMPLETED':
        return 'bg-emerald-50 text-emerald-700 border-emerald-200';
      case 'UNDER_INQUIRY':
      case 'IN_REVIEW':
      case 'IN_PROGRESS':
        return 'bg-blue-50 text-blue-700 border-blue-200';
      case 'HEARING_SCHEDULED':
        return 'bg-purple-50 text-purple-700 border-purple-200';
      case 'ACTION_TAKEN':
        return 'bg-teal-50 text-teal-700 border-teal-200';
      default:
        return 'bg-amber-50 text-amber-700 border-amber-200';
    }
  };

  return (
    <div className="min-h-screen bg-gradient-to-b from-slate-50 via-white to-slate-50 pt-20 pb-16 font-sans">
      <div className="max-w-6xl mx-auto px-4 sm:px-6 lg:px-8">
        
        {/* Top Header & Tab Navigation */}
        <div className="flex flex-col md:flex-row md:items-center justify-between pb-6 border-b border-slate-200 gap-4">
          <div>
            <div className="flex items-center gap-2 text-xs font-bold uppercase tracking-wider text-court-maroon mb-1">
              <ShieldCheck className="w-4 h-4 text-court-maroon" />
              <span>Unified Legal Citizen Portal</span>
            </div>
            <h1 className="text-2xl sm:text-3xl font-extrabold text-slate-900 tracking-tight">
              Citizen Dashboard
            </h1>
            <p className="text-sm text-slate-600 mt-0.5">
              Manage your legal filings, monitor SLA milestones, and access AI-powered legal services.
            </p>
          </div>

          {/* Tab Selector */}
          <div className="flex items-center gap-2 p-1.5 bg-slate-100 rounded-2xl border border-slate-200/80 self-start md:self-auto shadow-inner">
            <button
              onClick={() => setActiveTab('overview')}
              className={`flex items-center gap-2 px-4 py-2 rounded-xl text-xs font-bold transition-all cursor-pointer ${
                activeTab === 'overview'
                  ? 'bg-white text-court-maroon shadow-sm border border-slate-200'
                  : 'text-slate-600 hover:text-slate-900'
              }`}
            >
              <LayoutDashboard className="w-3.5 h-3.5" />
              <span>Overview</span>
            </button>
            <button
              onClick={() => setActiveTab('assistant')}
              className={`flex items-center gap-2 px-4 py-2 rounded-xl text-xs font-bold transition-all cursor-pointer ${
                activeTab === 'assistant'
                  ? 'bg-white text-court-maroon shadow-sm border border-slate-200'
                  : 'text-slate-600 hover:text-slate-900'
              }`}
            >
              <Sparkles className="w-3.5 h-3.5 text-amber-500" />
              <span>AI Legal Assistant</span>
            </button>
          </div>
        </div>

        {/* Tab Content */}
        {activeTab === 'assistant' ? (
          <div className="mt-6">
            <GatewayView />
          </div>
        ) : (
          <div className="mt-6 space-y-8">

            {/* Profile Greeting Card or Auth Prompt */}
            {statsError === 'UNAUTHENTICATED' ? (
              <div className="p-6 rounded-3xl bg-gradient-to-r from-rose-900 via-court-maroon to-slate-900 text-white shadow-xl flex flex-col md:flex-row items-start md:items-center justify-between gap-4">
                <div>
                  <div className="inline-flex items-center gap-1.5 px-3 py-1 rounded-full bg-white/10 text-rose-200 text-xs font-semibold mb-2">
                    <UserCheck className="w-3.5 h-3.5" />
                    <span>Citizen Session Required</span>
                  </div>
                  <h2 className="text-xl font-bold">Sign in to track your personal cases</h2>
                  <p className="text-xs text-rose-100/90 max-w-xl mt-1">
                    Sign in with your student or citizen credentials to view case progress, download verified records, and track departmental inquiry SLAs.
                  </p>
                </div>
                <div className="flex items-center gap-3 shrink-0">
                  <button
                    onClick={() => setShowAuthModal(true)}
                    className="px-5 py-2.5 rounded-xl bg-white text-court-maroon hover:bg-rose-50 font-bold text-xs shadow-md transition-all cursor-pointer flex items-center gap-2"
                  >
                    <LogIn className="w-4 h-4" />
                    <span>Sign In to Workspace</span>
                  </button>
                  <button
                    onClick={() => setActiveTab('assistant')}
                    className="px-4 py-2.5 rounded-xl bg-white/10 hover:bg-white/20 text-white font-semibold text-xs transition-all cursor-pointer"
                  >
                    Draft as Guest
                  </button>
                </div>
              </div>
            ) : (
              <div className="p-6 rounded-3xl bg-white border border-slate-200/90 shadow-sm flex flex-col md:flex-row items-start md:items-center justify-between gap-4">
                <div className="flex items-center gap-4">
                  <div className="w-12 h-12 rounded-2xl bg-rose-100 text-court-maroon flex items-center justify-center font-bold text-lg border border-rose-200">
                    {statsData?.user_profile?.name ? statsData.user_profile.name[0].toUpperCase() : 'C'}
                  </div>
                  <div>
                    <div className="flex items-center gap-2">
                      <h2 className="text-lg font-bold text-slate-900">
                        Welcome back, {statsData?.user_profile?.name || 'Citizen'}
                      </h2>
                      <span className="px-2.5 py-0.5 rounded-full text-[10px] font-bold uppercase tracking-wider bg-emerald-100 text-emerald-800 border border-emerald-200">
                        {statsData?.user_profile?.role || 'Citizen'}
                      </span>
                    </div>
                    <p className="text-xs text-slate-500 mt-0.5">
                      {statsData?.user_profile?.email} • Institution: {statsData?.user_profile?.institution_id || 'General Portal'}
                    </p>
                  </div>
                </div>

                <div className="flex items-center gap-2 shrink-0 self-end md:self-auto">
                  <button
                    onClick={fetchStats}
                    disabled={statsLoading}
                    className="p-2 rounded-xl text-slate-500 hover:text-slate-800 hover:bg-slate-100 transition-colors cursor-pointer"
                    title="Refresh Data"
                  >
                    <RefreshCw className={`w-4 h-4 ${statsLoading ? 'animate-spin' : ''}`} />
                  </button>
                  <Link
                    href="/dashboard/my-cases"
                    className="px-4 py-2 rounded-xl bg-slate-900 hover:bg-slate-800 text-white text-xs font-bold transition-all shadow-sm flex items-center gap-1.5"
                  >
                    <Briefcase className="w-3.5 h-3.5" />
                    <span>My Cases</span>
                  </Link>
                  <Link
                    href="/dashboard/consultations"
                    className="px-4 py-2 rounded-xl bg-court-maroon hover:bg-rose-700 text-white text-xs font-bold transition-all shadow-sm flex items-center gap-1.5"
                  >
                    <Scale className="w-3.5 h-3.5" />
                    <span>Consultations</span>
                  </Link>
                  <button
                    onClick={handleSignOut}
                    className="p-2 rounded-xl text-rose-600 hover:bg-rose-50 transition-colors cursor-pointer"
                    title="Sign Out"
                  >
                    <LogOut className="w-4 h-4" />
                  </button>
                </div>
              </div>
            )}

            {/* Case Statistics Cards (Task 2) */}
            <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
              <div className="p-5 rounded-3xl bg-white border border-slate-200 shadow-sm relative overflow-hidden">
                <div className="flex items-center justify-between text-slate-500 mb-2">
                  <span className="text-xs font-bold uppercase tracking-wider">Total Cases</span>
                  <div className="p-2 rounded-xl bg-slate-100 text-slate-700">
                    <FolderOpen className="w-4 h-4" />
                  </div>
                </div>
                <div className="text-2xl sm:text-3xl font-extrabold text-slate-900">
                  {statsLoading ? '—' : statsData?.stats?.total_cases ?? 0}
                </div>
                <p className="text-[11px] text-slate-500 mt-1">Total filed petitions & grievances</p>
              </div>

              <div className="p-5 rounded-3xl bg-white border border-slate-200 shadow-sm relative overflow-hidden">
                <div className="flex items-center justify-between text-blue-600 mb-2">
                  <span className="text-xs font-bold uppercase tracking-wider text-slate-500">Active / In Progress</span>
                  <div className="p-2 rounded-xl bg-blue-50 text-blue-600">
                    <Clock className="w-4 h-4" />
                  </div>
                </div>
                <div className="text-2xl sm:text-3xl font-extrabold text-blue-700">
                  {statsLoading ? '—' : statsData?.stats?.active_cases ?? 0}
                </div>
                <p className="text-[11px] text-slate-500 mt-1">Under inquiry or review</p>
              </div>

              <div className="p-5 rounded-3xl bg-white border border-slate-200 shadow-sm relative overflow-hidden">
                <div className="flex items-center justify-between text-emerald-600 mb-2">
                  <span className="text-xs font-bold uppercase tracking-wider text-slate-500">Resolved / Closed</span>
                  <div className="p-2 rounded-xl bg-emerald-50 text-emerald-600">
                    <CheckCircle2 className="w-4 h-4" />
                  </div>
                </div>
                <div className="text-2xl sm:text-3xl font-extrabold text-emerald-700">
                  {statsLoading ? '—' : statsData?.stats?.resolved_cases ?? 0}
                </div>
                <p className="text-[11px] text-slate-500 mt-1">Resolved with action taken</p>
              </div>

              <div className="p-5 rounded-3xl bg-white border border-slate-200 shadow-sm relative overflow-hidden">
                <div className="flex items-center justify-between text-purple-600 mb-2">
                  <span className="text-xs font-bold uppercase tracking-wider text-slate-500">Pending Actions</span>
                  <div className="p-2 rounded-xl bg-purple-50 text-purple-600">
                    <AlertTriangle className="w-4 h-4" />
                  </div>
                </div>
                <div className="text-2xl sm:text-3xl font-extrabold text-purple-700">
                  {statsLoading ? '—' : statsData?.stats?.pending_actions ?? 0}
                </div>
                <p className="text-[11px] text-slate-500 mt-1">Hearings & urgent attention</p>
              </div>
            </div>

            {/* Quick Actions Grid (Task 2) */}
            <div>
              <div className="flex items-center justify-between mb-4">
                <h3 className="text-sm font-bold uppercase tracking-wider text-slate-900">
                  Quick Actions & Legal Services
                </h3>
              </div>

              <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
                {/* 1. File New Grievance */}
                <Link
                  href="/dashboard/file-case"
                  className="p-5 rounded-3xl bg-white border border-slate-200 hover:border-court-maroon/50 shadow-sm hover:shadow-md transition-all text-left flex items-start gap-4 group cursor-pointer"
                >
                  <div className="p-3 rounded-2xl bg-rose-50 text-court-maroon group-hover:bg-court-maroon group-hover:text-white transition-colors shrink-0">
                    <PlusCircle className="w-5 h-5" />
                  </div>
                  <div>
                    <h4 className="text-sm font-bold text-slate-900 group-hover:text-court-maroon transition-colors">
                      File New Case / Grievance
                    </h4>
                    <p className="text-xs text-slate-500 mt-1 leading-relaxed">
                      Unified 6-step guided filing wizard across Campus Grievance, RTI, Consumer, and Appeals.
                    </p>
                  </div>
                </Link>

                {/* 2. My Cases Workspace */}
                <Link
                  href="/dashboard/my-cases"
                  className="p-5 rounded-3xl bg-white border border-slate-200 hover:border-slate-800 shadow-sm hover:shadow-md transition-all text-left flex items-start gap-4 group"
                >
                  <div className="p-3 rounded-2xl bg-slate-100 text-slate-800 group-hover:bg-slate-900 group-hover:text-white transition-colors shrink-0">
                    <Briefcase className="w-5 h-5" />
                  </div>
                  <div>
                    <h4 className="text-sm font-bold text-slate-900 group-hover:text-slate-800 transition-colors">
                      My Cases Workspace
                    </h4>
                    <p className="text-xs text-slate-500 mt-1 leading-relaxed">
                      View all your filed cases, inspect live progress timelines, and download official notices.
                    </p>
                  </div>
                </Link>

                {/* 3. Search Precedents */}
                <Link
                  href="/case-search"
                  className="p-5 rounded-3xl bg-white border border-slate-200 hover:border-blue-500 shadow-sm hover:shadow-md transition-all text-left flex items-start gap-4 group"
                >
                  <div className="p-3 rounded-2xl bg-blue-50 text-blue-600 group-hover:bg-blue-600 group-hover:text-white transition-colors shrink-0">
                    <BookOpen className="w-5 h-5" />
                  </div>
                  <div>
                    <h4 className="text-sm font-bold text-slate-900 group-hover:text-blue-600 transition-colors">
                      Case Search & Precedents
                    </h4>
                    <p className="text-xs text-slate-500 mt-1 leading-relaxed">
                      Explore landmark High Court and Supreme Court judgments with AI-powered case summarization.
                    </p>
                  </div>
                </Link>

                {/* 4. College Proctor Grievance Cell */}
                <Link
                  href="/campus-proctor"
                  className="p-5 rounded-3xl bg-white border border-slate-200 hover:border-emerald-500 shadow-sm hover:shadow-md transition-all text-left flex items-start gap-4 group"
                >
                  <div className="p-3 rounded-2xl bg-emerald-50 text-emerald-700 group-hover:bg-emerald-600 group-hover:text-white transition-colors shrink-0">
                    <GraduationCap className="w-5 h-5" />
                  </div>
                  <div>
                    <h4 className="text-sm font-bold text-slate-900 group-hover:text-emerald-700 transition-colors">
                      College Proctor Cell
                    </h4>
                    <p className="text-xs text-slate-500 mt-1 leading-relaxed">
                      Submit confidential campus grievances or track institutional disciplinary and inquiry proceedings.
                    </p>
                  </div>
                </Link>

                {/* 5. Live Court News */}
                <Link
                  href="/court-news"
                  className="p-5 rounded-3xl bg-white border border-slate-200 hover:border-amber-500 shadow-sm hover:shadow-md transition-all text-left flex items-start gap-4 group"
                >
                  <div className="p-3 rounded-2xl bg-amber-50 text-amber-600 group-hover:bg-amber-600 group-hover:text-white transition-colors shrink-0">
                    <Newspaper className="w-5 h-5" />
                  </div>
                  <div>
                    <h4 className="text-sm font-bold text-slate-900 group-hover:text-amber-600 transition-colors">
                      Live Court News
                    </h4>
                    <p className="text-xs text-slate-500 mt-1 leading-relaxed">
                      Real-time legal updates, judicial orders, and statutory compliance news from Indian courts.
                    </p>
                  </div>
                </Link>

                {/* 6. Track Statutory SLA */}
                <Link
                  href="/track"
                  className="p-5 rounded-3xl bg-white border border-slate-200 hover:border-purple-500 shadow-sm hover:shadow-md transition-all text-left flex items-start gap-4 group"
                >
                  <div className="p-3 rounded-2xl bg-purple-50 text-purple-600 group-hover:bg-purple-600 group-hover:text-white transition-colors shrink-0">
                    <Clock className="w-5 h-5" />
                  </div>
                  <div>
                    <h4 className="text-sm font-bold text-slate-900 group-hover:text-purple-600 transition-colors">
                      Track SLA Watchdog
                    </h4>
                    <p className="text-xs text-slate-500 mt-1 leading-relaxed">
                      Track statutory 30-day response deadlines and calculate automatic Section 20 RTI penalties.
                    </p>
                  </div>
                </Link>
              </div>
            </div>

            {/* Recent Cases Section (Task 2) */}
            <div className="p-6 rounded-3xl bg-white border border-slate-200 shadow-sm">
              <div className="flex items-center justify-between mb-4">
                <div>
                  <h3 className="text-base font-bold text-slate-900">Recent Cases & Filings</h3>
                  <p className="text-xs text-slate-500 mt-0.5">Your latest legal proceedings and grievances</p>
                </div>
                <Link
                  href="/dashboard/my-cases"
                  className="text-xs font-bold text-court-maroon hover:underline flex items-center gap-1"
                >
                  <span>View All</span>
                  <ChevronRight className="w-3.5 h-3.5" />
                </Link>
              </div>

              {statsLoading ? (
                <div className="py-12 flex flex-col items-center justify-center text-slate-400">
                  <RefreshCw className="w-6 h-6 animate-spin text-court-maroon mb-2" />
                  <span className="text-xs font-medium">Loading your legal workspace...</span>
                </div>
              ) : statsData?.recent_cases && statsData.recent_cases.length > 0 ? (
                <div className="space-y-3">
                  {statsData.recent_cases.map((c) => (
                    <div
                      key={c.case_id}
                      className="p-4 rounded-2xl border border-slate-200/80 hover:border-slate-300 bg-slate-50/50 hover:bg-slate-50 transition-all flex flex-col sm:flex-row sm:items-center justify-between gap-3"
                    >
                      <div className="flex items-start gap-3">
                        <div className="p-2.5 rounded-xl bg-white border border-slate-200 text-slate-700 shrink-0 mt-0.5 sm:mt-0">
                          <FileText className="w-4 h-4 text-court-maroon" />
                        </div>
                        <div>
                          <div className="flex items-center gap-2 flex-wrap">
                            <span className="font-mono text-xs font-bold text-slate-900">{c.case_id}</span>
                            <span className={`px-2 py-0.5 rounded-full text-[10px] font-bold border ${getStatusColor(c.status)}`}>
                              {c.status}
                            </span>
                            <span className="px-2 py-0.5 rounded-full text-[10px] font-medium bg-slate-200 text-slate-700">
                              {c.category}
                            </span>
                          </div>
                          <h4 className="text-xs font-bold text-slate-800 mt-1 line-clamp-1">
                            {c.subject}
                          </h4>
                          <p className="text-[11px] text-slate-500 line-clamp-1 mt-0.5">
                            {c.description}
                          </p>
                        </div>
                      </div>

                      <div className="flex items-center gap-3 shrink-0 self-end sm:self-auto">
                        <span className="text-[11px] text-slate-400">
                          {c.created_at ? new Date(c.created_at).toLocaleDateString() : 'Recent'}
                        </span>
                        <Link
                          href={`/dashboard/my-cases/${encodeURIComponent(c.case_id)}`}
                          className="px-3 py-1.5 rounded-xl bg-white hover:bg-slate-100 text-slate-700 hover:text-slate-900 text-xs font-bold border border-slate-200 transition-colors flex items-center gap-1"
                        >
                          <span>Details</span>
                          <ArrowRight className="w-3 h-3" />
                        </Link>
                      </div>
                    </div>
                  ))}
                </div>
              ) : (
                <div className="py-12 px-4 rounded-2xl border border-dashed border-slate-200 text-center">
                  <div className="w-12 h-12 rounded-full bg-slate-100 text-slate-400 mx-auto flex items-center justify-center mb-3">
                    <FolderOpen className="w-6 h-6" />
                  </div>
                  <h4 className="text-sm font-bold text-slate-800">No cases on record yet</h4>
                  <p className="text-xs text-slate-500 max-w-sm mx-auto mt-1">
                    Start by generating a formal grievance, filing an RTI inquiry, or reporting a consumer issue with our legal engine.
                  </p>
                  <button
                    onClick={() => setActiveTab('assistant')}
                    className="mt-4 px-4 py-2 rounded-xl bg-gradient-to-r from-court-maroon to-rose-700 text-white text-xs font-bold shadow-md hover:from-rose-700 hover:to-rose-800 transition-all cursor-pointer"
                  >
                    Launch AI Legal Intake
                  </button>
                </div>
              )}
            </div>

          </div>
        )}

      </div>

      {/* Quick Sign-In Modal */}
      {showAuthModal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 backdrop-blur-sm p-4 font-sans">
          <div className="bg-white rounded-3xl max-w-md w-full p-6 shadow-2xl border border-slate-200">
            <div className="flex items-center justify-between pb-4 border-b border-slate-100">
              <div className="flex items-center gap-2">
                <ShieldCheck className="w-5 h-5 text-court-maroon" />
                <h3 className="font-bold text-slate-900 text-base">Sign In to Citizen Workspace</h3>
              </div>
              <button
                onClick={() => setShowAuthModal(false)}
                className="text-slate-400 hover:text-slate-600 text-sm font-bold"
              >
                ✕
              </button>
            </div>

            <form
              onSubmit={(e) => {
                e.preventDefault();
                handleQuickLogin(authEmail, authPassword);
              }}
              className="mt-4 space-y-4"
            >
              <div>
                <label className="block text-xs font-bold text-slate-700 mb-1">Email Address</label>
                <input
                  type="email"
                  value={authEmail}
                  onChange={(e) => setAuthEmail(e.target.value)}
                  className="w-full px-3.5 py-2.5 rounded-xl border border-slate-300 text-xs focus:ring-2 focus:ring-court-maroon focus:outline-none"
                  placeholder="student@nit.edu or citizen@nyaypath.in"
                  required
                />
              </div>

              <div>
                <label className="block text-xs font-bold text-slate-700 mb-1">Password</label>
                <input
                  type="password"
                  value={authPassword}
                  onChange={(e) => setAuthPassword(e.target.value)}
                  className="w-full px-3.5 py-2.5 rounded-xl border border-slate-300 text-xs focus:ring-2 focus:ring-court-maroon focus:outline-none"
                  placeholder="Enter password"
                  required
                />
              </div>

              {authError && (
                <div className="p-3 rounded-xl bg-rose-50 border border-rose-200 text-rose-700 text-xs">
                  {authError}
                </div>
              )}

              {/* Development Account Identifier Helpers (Email Only - No Passwords Embedded) */}
              {process.env.NODE_ENV !== 'production' && (
                <div className="p-3 rounded-2xl bg-slate-50 border border-slate-200 text-xs space-y-1.5">
                  <span className="font-bold text-slate-700 block text-[11px] uppercase tracking-wider">
                    Dev Quick Fill (Email Only)
                  </span>
                  <div className="flex gap-2">
                    <button
                      type="button"
                      onClick={() => {
                        setAuthEmail('student@nit.edu');
                        setAuthPassword('');
                      }}
                      className="px-2.5 py-1 rounded-lg bg-white border border-slate-200 text-slate-800 text-[11px] font-semibold hover:border-court-maroon"
                    >
                      Student (Aarav)
                    </button>
                    <button
                      type="button"
                      onClick={() => {
                        setAuthEmail('citizen@nyaypath.in');
                        setAuthPassword('');
                      }}
                      className="px-2.5 py-1 rounded-lg bg-white border border-slate-200 text-slate-800 text-[11px] font-semibold hover:border-court-maroon"
                    >
                      Citizen (Priya)
                    </button>
                  </div>
                </div>
              )}

              <div className="flex items-center justify-end gap-2 pt-2">
                <button
                  type="button"
                  onClick={() => setShowAuthModal(false)}
                  className="px-4 py-2 rounded-xl text-slate-600 text-xs font-semibold hover:bg-slate-100"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  disabled={authLoading}
                  className="px-5 py-2 rounded-xl bg-gradient-to-r from-court-maroon to-rose-700 text-white text-xs font-bold hover:from-rose-700 hover:to-rose-800 transition-all flex items-center gap-1.5 cursor-pointer shadow-md"
                >
                  {authLoading && <RefreshCw className="w-3.5 h-3.5 animate-spin" />}
                  <span>Sign In</span>
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
}
