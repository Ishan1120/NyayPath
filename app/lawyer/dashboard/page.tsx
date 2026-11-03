'use client';

import React, { useState, useEffect } from 'react';
import Link from 'next/link';
import { useRouter } from 'next/navigation';
import {
  Scale,
  ShieldCheck,
  AlertTriangle,
  Clock,
  CheckCircle2,
  XCircle,
  FileText,
  User,
  Users,
  Briefcase,
  FolderOpen,
  MessageSquare,
  ExternalLink,
  ChevronRight,
  Filter,
  RefreshCw,
  Edit3,
  Calendar,
  Lock,
  Download,
  AlertCircle,
  ArrowRight,
  LogIn,
  LogOut
} from 'lucide-react';
import {
  getLawyerDashboardStats,
  getLawyerConsultations,
  updateConsultationStatus,
  getLawyerSharedCases,
  updateLawyerProfile,
  LawyerDashboardStats,
  ConsultationRequest,
  LawyerProfile,
  loginCitizen
} from '@/lib/api';

export default function LawyerDashboardPage() {
  const router = useRouter();

  // Active Tab: 'overview' | 'requests' | 'cases' | 'profile'
  const [activeTab, setActiveTab] = useState<'overview' | 'requests' | 'cases' | 'profile'>('overview');

  // Data states
  const [stats, setStats] = useState<LawyerDashboardStats | null>(null);
  const [consultations, setConsultations] = useState<ConsultationRequest[]>([]);
  const [sharedCases, setSharedCases] = useState<any[]>([]);
  const [profile, setProfile] = useState<LawyerProfile | null>(null);

  // Filter state for requests
  const [statusFilter, setStatusFilter] = useState<string>('ALL');

  // Loading & error states
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [successMsg, setSuccessMsg] = useState<string | null>(null);

  // Response modal state
  const [actionModal, setActionModal] = useState<{
    isOpen: boolean;
    request: ConsultationRequest | null;
    action: 'ACCEPTED' | 'DECLINED' | 'COMPLETED' | null;
    responseMsg: string;
    submitting: boolean;
  }>({
    isOpen: false,
    request: null,
    action: null,
    responseMsg: '',
    submitting: false
  });

  // Profile Edit state
  const [editingProfile, setEditingProfile] = useState(false);
  const [profileForm, setProfileForm] = useState({
    bio: '',
    years_of_practice: 0,
    specializations: [] as string[],
    courts: [] as string[],
    languages: [] as string[]
  });
  const [profileSaving, setProfileSaving] = useState(false);

  // Advocate Quick Auth modal state
  const [showAuthModal, setShowAuthModal] = useState(false);
  const [authEmail, setAuthEmail] = useState('');
  const [authPassword, setAuthPassword] = useState('');
  const [authLoading, setAuthLoading] = useState(false);
  const [authError, setAuthError] = useState<string | null>(null);

  const handleQuickLogin = async (email: string, pass: string) => {
    setAuthLoading(true);
    setAuthError(null);
    try {
      const res = await loginCitizen({ email, password: pass });
      if (res?.token && res?.user) {
        localStorage.setItem('nyaypath_lawyer_token', res.token);
        localStorage.setItem('nyaypath_token', res.token);
        localStorage.setItem('nyaypath_user', JSON.stringify(res.user));
        setShowAuthModal(false);
        setError(null);
        fetchData();
      } else {
        setAuthError('Authentication failed: Invalid advocate credentials.');
      }
    } catch (err: any) {
      setAuthError(err?.response?.data?.detail || 'Login failed. Please check advocate credentials.');
    } finally {
      setAuthLoading(false);
    }
  };

  const handleSignOut = () => {
    localStorage.removeItem('nyaypath_lawyer_token');
    localStorage.removeItem('nyaypath_token');
    localStorage.removeItem('nyaypath_user');
    setStats(null);
    setConsultations([]);
    setSharedCases([]);
    setError('UNAUTHENTICATED');
  };

  const fetchData = async () => {
    setLoading(true);
    setError(null);
    try {
      const [statsRes, requestsRes, casesRes] = await Promise.allSettled([
        getLawyerDashboardStats(),
        getLawyerConsultations(),
        getLawyerSharedCases()
      ]);

      if (statsRes.status === 'fulfilled') {
        setStats(statsRes.value.stats);
      } else if ((statsRes.reason as any)?.response?.status === 401) {
        setError('UNAUTHENTICATED');
        setLoading(false);
        return;
      }

      if (requestsRes.status === 'fulfilled') {
        setConsultations(requestsRes.value.consultations || []);
      }

      if (casesRes.status === 'fulfilled') {
        setSharedCases(casesRes.value.cases || []);
      }
    } catch (err: any) {
      if (err?.response?.status === 401) {
        setError('UNAUTHENTICATED');
      } else {
        setError(err?.response?.data?.detail || 'Failed to load lawyer workspace.');
      }
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchData();
  }, []);

  const handleOpenActionModal = (req: ConsultationRequest, action: 'ACCEPTED' | 'DECLINED' | 'COMPLETED') => {
    setActionModal({
      isOpen: true,
      request: req,
      action: action,
      responseMsg: action === 'ACCEPTED'
        ? 'Thank you for reaching out. I have reviewed your preliminary issue and am available to consult. Let us schedule an initial discussion.'
        : action === 'DECLINED'
        ? 'I am currently unable to take on new matters in this domain or have a scheduling conflict.'
        : 'Consultation concluded.',
      submitting: false
    });
  };

  const handleConfirmAction = async () => {
    if (!actionModal.request || !actionModal.action) return;
    setActionModal(prev => ({ ...prev, submitting: true }));
    try {
      await updateConsultationStatus(actionModal.request.id, {
        status: actionModal.action,
        lawyer_response: actionModal.responseMsg.trim() || undefined
      });
      setSuccessMsg(`Consultation request successfully marked as ${actionModal.action}.`);
      setActionModal({
        isOpen: false,
        request: null,
        action: null,
        responseMsg: '',
        submitting: false
      });
      fetchData();
      setTimeout(() => setSuccessMsg(null), 4000);
    } catch (err: any) {
      alert(err?.response?.data?.detail || 'Failed to update consultation status.');
      setActionModal(prev => ({ ...prev, submitting: false }));
    }
  };

  const filteredConsultations = consultations.filter(c => {
    if (statusFilter === 'ALL') return true;
    return c.status === statusFilter;
  });

  const getStatusBadge = (status: string) => {
    switch (status) {
      case 'ACCEPTED':
        return (
          <span className="inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full text-[11px] font-bold bg-emerald-50 text-emerald-700 border border-emerald-200">
            <CheckCircle2 className="w-3 h-3" />
            <span>ACCEPTED</span>
          </span>
        );
      case 'PENDING':
        return (
          <span className="inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full text-[11px] font-bold bg-amber-50 text-amber-700 border border-amber-200">
            <Clock className="w-3 h-3" />
            <span>PENDING REVIEW</span>
          </span>
        );
      case 'DECLINED':
        return (
          <span className="inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full text-[11px] font-bold bg-rose-50 text-rose-700 border border-rose-200">
            <XCircle className="w-3 h-3" />
            <span>DECLINED</span>
          </span>
        );
      case 'COMPLETED':
        return (
          <span className="inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full text-[11px] font-bold bg-blue-50 text-blue-700 border border-blue-200">
            <CheckCircle2 className="w-3 h-3" />
            <span>COMPLETED</span>
          </span>
        );
      case 'WITHDRAWN':
        return (
          <span className="inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full text-[11px] font-bold bg-slate-100 text-slate-600 border border-slate-200">
            <span>WITHDRAWN</span>
          </span>
        );
      default:
        return (
          <span className="inline-flex items-center px-2.5 py-0.5 rounded-full text-[11px] font-bold bg-slate-100 text-slate-700">
            {status}
          </span>
        );
    }
  };

  return (
    <div className="min-h-screen bg-slate-50 pt-24 pb-16 font-sans">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
        {/* Top Header & Context */}
        <div className="mb-6 flex flex-col md:flex-row md:items-center md:justify-between gap-4">
          <div>
            <div className="flex items-center gap-2 mb-1">
              <span className="inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full text-[11px] font-bold bg-slate-900 text-amber-300">
                <Scale className="w-3 h-3 text-amber-300" />
                <span>Advocate Workspace</span>
              </span>
              <span className="text-xs text-slate-400 font-mono">
                Bar Council Connect
              </span>
            </div>
            <h1 className="text-2xl sm:text-3xl font-serif font-bold text-slate-900">
              Lawyer Practice Desk
            </h1>
            <p className="text-xs sm:text-sm text-slate-500 mt-0.5">
              Manage citizen consultations, privileged case shares, and client representation.
            </p>
          </div>

          <div className="flex items-center gap-2.5">
            <button
              onClick={fetchData}
              disabled={loading}
              className="p-2 bg-white border border-slate-200 text-slate-600 hover:text-slate-900 rounded-xl hover:bg-slate-50 transition-colors shadow-sm cursor-pointer"
              title="Refresh Workspace"
            >
              <RefreshCw className={`w-4 h-4 ${loading ? 'animate-spin' : ''}`} />
            </button>
            <Link
              href="/lawyers"
              className="px-4 py-2 bg-white border border-slate-200 text-slate-700 hover:text-court-maroon rounded-xl text-xs font-bold transition-all shadow-sm flex items-center gap-1.5"
            >
              <ExternalLink size={13} />
              <span>Public Directory</span>
            </Link>
            <Link
              href="/lawyer/register"
              className="px-4 py-2 bg-court-maroon hover:bg-rose-700 text-white rounded-xl text-xs font-bold uppercase tracking-wider transition-all shadow-md flex items-center gap-1.5"
            >
              <Scale size={13} />
              <span>Register / Onboard</span>
            </Link>
            {error !== 'UNAUTHENTICATED' && (
              <button
                type="button"
                onClick={handleSignOut}
                className="px-3 py-2 bg-rose-50 border border-rose-200 text-rose-700 hover:bg-rose-100 rounded-xl text-xs font-bold transition-all shadow-sm flex items-center gap-1.5 cursor-pointer"
                title="Sign Out"
              >
                <LogOut size={13} />
                <span>Sign Out</span>
              </button>
            )}
          </div>
        </div>

        {/* Global Alerts */}
        {error === 'UNAUTHENTICATED' && (
          <div className="mb-6 bg-amber-50 border border-amber-200 rounded-2xl p-6 text-amber-900 flex flex-col sm:flex-row items-center justify-between gap-4">
            <div className="flex items-start gap-3">
              <AlertCircle className="w-6 h-6 text-amber-700 shrink-0 mt-0.5" />
              <div>
                <h4 className="font-bold text-sm">Lawyer Session Required</h4>
                <p className="text-xs text-amber-700 mt-1">
                  You are currently browsing the lawyer workspace without an active advocate session. Please log in or register your Bar Council profile.
                </p>
              </div>
            </div>
            <div className="flex items-center gap-2 shrink-0">
              <button
                type="button"
                onClick={() => setShowAuthModal(true)}
                className="px-4 py-2 bg-court-maroon text-white rounded-xl text-xs font-bold uppercase tracking-wider hover:bg-rose-700 shadow flex items-center gap-1.5 cursor-pointer"
              >
                <LogIn className="w-3.5 h-3.5" />
                <span>Sign In Advocate</span>
              </button>
              <Link
                href="/lawyer/register"
                className="px-4 py-2 bg-white border border-amber-300 text-amber-900 rounded-xl text-xs font-bold uppercase tracking-wider hover:bg-amber-100 shadow"
              >
                Onboard Advocate
              </Link>
            </div>
          </div>
        )}

        {successMsg && (
          <div className="mb-6 p-4 bg-emerald-50 border border-emerald-200 rounded-xl text-xs text-emerald-800 flex items-center gap-2 animate-in fade-in">
            <CheckCircle2 className="w-4 h-4 text-emerald-600 shrink-0" />
            <span>{successMsg}</span>
          </div>
        )}

        {/* 6 Real DB Metrics Cards */}
        <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-6 gap-3.5 mb-8">
          <div className="bg-white p-4 rounded-2xl border border-slate-200/80 shadow-sm">
            <div className="flex items-center justify-between text-slate-500 mb-2">
              <span className="text-[11px] font-bold uppercase tracking-wider">Total Inquiries</span>
              <MessageSquare className="w-4 h-4 text-slate-400" />
            </div>
            <p className="text-2xl font-bold font-serif text-slate-900">
              {stats?.total_requests ?? 0}
            </p>
            <p className="text-[10px] text-slate-400 mt-1">All consultation requests</p>
          </div>

          <div className="bg-white p-4 rounded-2xl border border-amber-200/80 bg-amber-50/20 shadow-sm">
            <div className="flex items-center justify-between text-amber-700 mb-2">
              <span className="text-[11px] font-bold uppercase tracking-wider">Pending Action</span>
              <Clock className="w-4 h-4 text-amber-600" />
            </div>
            <p className="text-2xl font-bold font-serif text-amber-900">
              {stats?.pending_requests ?? 0}
            </p>
            <p className="text-[10px] text-amber-600 mt-1">Awaiting triage</p>
          </div>

          <div className="bg-white p-4 rounded-2xl border border-emerald-200/80 bg-emerald-50/20 shadow-sm">
            <div className="flex items-center justify-between text-emerald-700 mb-2">
              <span className="text-[11px] font-bold uppercase tracking-wider">Accepted</span>
              <CheckCircle2 className="w-4 h-4 text-emerald-600" />
            </div>
            <p className="text-2xl font-bold font-serif text-emerald-900">
              {stats?.accepted_consultations ?? 0}
            </p>
            <p className="text-[10px] text-emerald-600 mt-1">Active matters</p>
          </div>

          <div className="bg-white p-4 rounded-2xl border border-blue-200/80 bg-blue-50/20 shadow-sm">
            <div className="flex items-center justify-between text-blue-700 mb-2">
              <span className="text-[11px] font-bold uppercase tracking-wider">Completed</span>
              <CheckCircle2 className="w-4 h-4 text-blue-600" />
            </div>
            <p className="text-2xl font-bold font-serif text-blue-900">
              {stats?.completed_consultations ?? 0}
            </p>
            <p className="text-[10px] text-blue-600 mt-1">Concluded consultations</p>
          </div>

          <div className="bg-white p-4 rounded-2xl border border-indigo-200/80 bg-indigo-50/20 shadow-sm">
            <div className="flex items-center justify-between text-indigo-700 mb-2">
              <span className="text-[11px] font-bold uppercase tracking-wider">Active Clients</span>
              <Users className="w-4 h-4 text-indigo-600" />
            </div>
            <p className="text-2xl font-bold font-serif text-indigo-900">
              {stats?.active_clients ?? 0}
            </p>
            <p className="text-[10px] text-indigo-600 mt-1">Represented citizens</p>
          </div>

          <div className="bg-white p-4 rounded-2xl border border-purple-200/80 bg-purple-50/20 shadow-sm">
            <div className="flex items-center justify-between text-purple-700 mb-2">
              <span className="text-[11px] font-bold uppercase tracking-wider">Shared Cases</span>
              <FolderOpen className="w-4 h-4 text-purple-600" />
            </div>
            <p className="text-2xl font-bold font-serif text-purple-900">
              {stats?.shared_cases ?? 0}
            </p>
            <p className="text-[10px] text-purple-600 mt-1">Authorized dossiers</p>
          </div>
        </div>

        {/* Tab Navigation */}
        <div className="border-b border-slate-200 mb-6 flex gap-6 text-xs font-bold uppercase tracking-wider">
          <button
            onClick={() => setActiveTab('overview')}
            className={`pb-3 border-b-2 transition-all cursor-pointer ${
              activeTab === 'overview'
                ? 'border-court-maroon text-court-maroon'
                : 'border-transparent text-slate-500 hover:text-slate-800'
            }`}
          >
            Overview & Triage
          </button>
          <button
            onClick={() => setActiveTab('requests')}
            className={`pb-3 border-b-2 transition-all cursor-pointer flex items-center gap-1.5 ${
              activeTab === 'requests'
                ? 'border-court-maroon text-court-maroon'
                : 'border-transparent text-slate-500 hover:text-slate-800'
            }`}
          >
            <span>Consultation Inquiries</span>
            {stats && stats.pending_requests > 0 && (
              <span className="bg-amber-500 text-white text-[10px] px-1.5 py-0.2 rounded-full">
                {stats.pending_requests}
              </span>
            )}
          </button>
          <button
            onClick={() => setActiveTab('cases')}
            className={`pb-3 border-b-2 transition-all cursor-pointer flex items-center gap-1.5 ${
              activeTab === 'cases'
                ? 'border-court-maroon text-court-maroon'
                : 'border-transparent text-slate-500 hover:text-slate-800'
            }`}
          >
            <span>Shared Client Cases</span>
            {sharedCases.length > 0 && (
              <span className="bg-slate-200 text-slate-700 text-[10px] px-1.5 py-0.2 rounded-full">
                {sharedCases.length}
              </span>
            )}
          </button>
        </div>

        {/* TAB 1: OVERVIEW */}
        {activeTab === 'overview' && (
          <div className="space-y-6">
            {/* Quick Pending Inquiries Card */}
            <div className="bg-white rounded-2xl shadow-sm border border-slate-200/80 p-6">
              <div className="flex items-center justify-between mb-4">
                <div className="flex items-center gap-2">
                  <Clock className="w-5 h-5 text-amber-600" />
                  <h3 className="font-serif font-bold text-lg text-slate-900">
                    Priority Inquiries Awaiting Your Review
                  </h3>
                </div>
                <button
                  onClick={() => {
                    setStatusFilter('PENDING');
                    setActiveTab('requests');
                  }}
                  className="text-xs font-bold text-court-maroon hover:underline flex items-center gap-1"
                >
                  View All Requests <ChevronRight size={13} />
                </button>
              </div>

              {consultations.filter(c => c.status === 'PENDING').length === 0 ? (
                <div className="text-center py-8 bg-slate-50 rounded-xl border border-dashed border-slate-200">
                  <CheckCircle2 className="w-8 h-8 text-emerald-500 mx-auto mb-2" />
                  <p className="text-xs font-bold text-slate-700">Inbox Clean</p>
                  <p className="text-[11px] text-slate-400 mt-0.5">
                    No consultation inquiries currently require triage.
                  </p>
                </div>
              ) : (
                <div className="space-y-3">
                  {consultations
                    .filter(c => c.status === 'PENDING')
                    .slice(0, 3)
                    .map(req => (
                      <div
                        key={req.id}
                        className="p-4 rounded-xl border border-slate-200 hover:border-slate-300 bg-white transition-all flex flex-col sm:flex-row sm:items-center justify-between gap-4"
                      >
                        <div className="flex-1">
                          <div className="flex items-center gap-2 mb-1">
                            <span className="text-xs font-bold text-slate-900">
                              {req.client?.full_name || 'Citizen Client'}
                            </span>
                            <span className="text-[10px] text-slate-400">
                              ({req.client?.email || 'Confidential'})
                            </span>
                            <span className="text-[10px] font-bold text-indigo-700 bg-indigo-50 border border-indigo-200 px-2 py-0.2 rounded-full">
                              {req.preferred_mode}
                            </span>
                          </div>
                          <p className="text-xs font-semibold text-slate-800">{req.legal_issue}</p>
                          <p className="text-xs text-slate-500 line-clamp-1 mt-0.5">{req.description}</p>
                          {req.case_id && (
                            <span className="inline-block mt-2 font-mono text-[10px] text-court-maroon bg-rose-50 border border-rose-200 px-2 py-0.5 rounded">
                              Linked Case: {req.case_id}
                            </span>
                          )}
                        </div>

                        <div className="flex items-center gap-2 shrink-0">
                          <button
                            onClick={() => handleOpenActionModal(req, 'ACCEPTED')}
                            className="px-3.5 py-1.5 bg-emerald-600 hover:bg-emerald-700 text-white rounded-lg text-xs font-bold uppercase transition-all shadow-sm"
                          >
                            Accept
                          </button>
                          <button
                            onClick={() => handleOpenActionModal(req, 'DECLINED')}
                            className="px-3.5 py-1.5 bg-slate-100 hover:bg-rose-50 hover:text-rose-700 text-slate-700 rounded-lg text-xs font-bold uppercase transition-all"
                          >
                            Decline
                          </button>
                        </div>
                      </div>
                    ))}
                </div>
              )}
            </div>

            {/* Quick Shared Cases Preview */}
            <div className="bg-white rounded-2xl shadow-sm border border-slate-200/80 p-6">
              <div className="flex items-center justify-between mb-4">
                <div className="flex items-center gap-2">
                  <FolderOpen className="w-5 h-5 text-purple-600" />
                  <h3 className="font-serif font-bold text-lg text-slate-900">
                    Active Client Dossiers & Evidence
                  </h3>
                </div>
                <button
                  onClick={() => setActiveTab('cases')}
                  className="text-xs font-bold text-court-maroon hover:underline flex items-center gap-1"
                >
                  View All Dossiers <ChevronRight size={13} />
                </button>
              </div>

              {sharedCases.length === 0 ? (
                <div className="text-center py-8 bg-slate-50 rounded-xl border border-dashed border-slate-200">
                  <FolderOpen className="w-8 h-8 text-slate-400 mx-auto mb-2" />
                  <p className="text-xs font-bold text-slate-700">No Cases Shared Yet</p>
                  <p className="text-[11px] text-slate-400 mt-0.5 max-w-md mx-auto">
                    When citizens accept your consultation and explicitly authorize access, their case facts and uploaded documents will appear here.
                  </p>
                </div>
              ) : (
                <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                  {sharedCases.slice(0, 4).map((c) => (
                    <div
                      key={c.case_id}
                      className="p-4 rounded-xl border border-slate-200 bg-slate-50/50 hover:bg-slate-50 transition-all"
                    >
                      <div className="flex items-center justify-between mb-1.5">
                        <span className="font-mono text-xs font-bold text-court-maroon">
                          {c.case_id}
                        </span>
                        <span className="text-[10px] font-bold uppercase px-2 py-0.5 rounded-full bg-slate-200 text-slate-700">
                          {c.category}
                        </span>
                      </div>
                      <h4 className="text-xs font-bold text-slate-900 line-clamp-1">{c.title}</h4>
                      <p className="text-[11px] text-slate-500 line-clamp-2 mt-1">{c.facts_summary}</p>

                      <div className="mt-3 pt-2 border-t border-slate-200/80 flex items-center justify-between text-[11px]">
                        <span className="text-slate-500">
                          Client: <strong className="text-slate-700">{c.citizen_user_id ? 'Verified Citizen' : 'Citizen'}</strong>
                        </span>
                        <Link
                          href={`/dashboard/my-cases?case_id=${encodeURIComponent(c.case_id)}`}
                          className="text-court-maroon font-bold hover:underline flex items-center gap-1"
                        >
                          Review Dossier <ChevronRight size={12} />
                        </Link>
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </div>
          </div>
        )}

        {/* TAB 2: CONSULTATION INQUIRIES */}
        {activeTab === 'requests' && (
          <div className="bg-white rounded-2xl shadow-sm border border-slate-200/80 overflow-hidden">
            {/* Header & Filter Bar */}
            <div className="p-4 sm:p-6 border-b border-slate-100 flex flex-col sm:flex-row sm:items-center justify-between gap-4">
              <div>
                <h3 className="font-serif font-bold text-lg text-slate-900">
                  Citizen Consultation Requests
                </h3>
                <p className="text-xs text-slate-500 mt-0.5">
                  Review legal inquiries, propose engagement terms, or accept matters.
                </p>
              </div>

              {/* Status Filter */}
              <div className="flex items-center gap-1.5 overflow-x-auto pb-1 sm:pb-0">
                {['ALL', 'PENDING', 'ACCEPTED', 'DECLINED', 'COMPLETED', 'WITHDRAWN'].map((st) => (
                  <button
                    key={st}
                    onClick={() => setStatusFilter(st)}
                    className={`px-3 py-1.5 rounded-lg text-xs font-bold uppercase tracking-wider transition-all cursor-pointer whitespace-nowrap ${
                      statusFilter === st
                        ? 'bg-slate-900 text-white shadow-sm'
                        : 'bg-slate-100 text-slate-600 hover:bg-slate-200'
                    }`}
                  >
                    {st}
                  </button>
                ))}
              </div>
            </div>

            {/* List */}
            {filteredConsultations.length === 0 ? (
              <div className="py-16 text-center text-slate-400">
                <MessageSquare className="w-10 h-10 mx-auto mb-2 text-slate-300" />
                <p className="text-xs font-bold text-slate-600">No consultation requests match this filter.</p>
                <p className="text-[11px] text-slate-400 mt-1">
                  Change the filter above or share your advocate profile link.
                </p>
              </div>
            ) : (
              <div className="divide-y divide-slate-100">
                {filteredConsultations.map((req) => (
                  <div key={req.id} className="p-5 sm:p-6 hover:bg-slate-50/70 transition-colors">
                    <div className="flex flex-col lg:flex-row lg:items-start justify-between gap-4">
                      <div className="flex-1">
                        <div className="flex flex-wrap items-center gap-2 mb-2">
                          {getStatusBadge(req.status)}
                          <span className="text-xs font-bold text-slate-900">
                            {req.client?.full_name || 'Citizen Client'}
                          </span>
                          <span className="text-[11px] text-slate-400">
                            {req.client?.email ? `• ${req.client.email}` : ''}
                          </span>
                          <span className="text-[11px] font-bold text-indigo-700 bg-indigo-50 border border-indigo-200/60 px-2 py-0.5 rounded-full">
                            Mode: {req.preferred_mode}
                          </span>
                          <span className="text-[11px] text-slate-400 ml-auto">
                            Received {new Date(req.created_at).toLocaleDateString()}
                          </span>
                        </div>

                        <h4 className="text-sm font-bold text-slate-900 mb-1">
                          {req.legal_issue}
                        </h4>
                        <p className="text-xs text-slate-600 leading-relaxed mb-3 whitespace-pre-line">
                          {req.description}
                        </p>

                        {/* Linked Case if any */}
                        {req.case_id && (
                          <div className="mb-3 p-2.5 bg-rose-50/60 border border-rose-200/60 rounded-xl inline-flex items-center gap-2 text-xs">
                            <span className="text-slate-500">Linked NyayPath Case:</span>
                            <span className="font-mono font-bold text-court-maroon">{req.case_id}</span>
                            <Link
                              href={`/dashboard/my-cases?case_id=${encodeURIComponent(req.case_id)}`}
                              className="text-court-maroon hover:underline font-bold text-[11px] flex items-center gap-0.5 ml-2"
                            >
                              Inspect Dossier <ExternalLink size={11} />
                            </Link>
                          </div>
                        )}

                        {/* Lawyer Response if already recorded */}
                        {req.lawyer_response && (
                          <div className="p-3 bg-slate-50 border border-slate-200 rounded-xl text-xs text-slate-700 mt-2">
                            <p className="font-bold text-slate-800 text-[11px] uppercase tracking-wider mb-0.5">
                              Your Recorded Response ({req.response_date ? new Date(req.response_date).toLocaleDateString() : 'Recorded'}):
                            </p>
                            <p className="italic text-slate-600">&ldquo;{req.lawyer_response}&rdquo;</p>
                          </div>
                        )}
                      </div>

                      {/* Action Buttons for Lawyer */}
                      <div className="flex sm:flex-col gap-2 shrink-0 pt-2 lg:pt-0">
                        {req.status === 'PENDING' && (
                          <>
                            <button
                              onClick={() => handleOpenActionModal(req, 'ACCEPTED')}
                              className="px-4 py-2 bg-emerald-600 hover:bg-emerald-700 text-white rounded-xl text-xs font-bold uppercase tracking-wider transition-all shadow-sm cursor-pointer"
                            >
                              Accept Consultation
                            </button>
                            <button
                              onClick={() => handleOpenActionModal(req, 'DECLINED')}
                              className="px-4 py-2 bg-slate-100 hover:bg-rose-50 hover:text-rose-700 text-slate-700 rounded-xl text-xs font-bold uppercase tracking-wider transition-all cursor-pointer"
                            >
                              Decline
                            </button>
                          </>
                        )}

                        {req.status === 'ACCEPTED' && (
                          <button
                            onClick={() => handleOpenActionModal(req, 'COMPLETED')}
                            className="px-4 py-2 bg-blue-600 hover:bg-blue-700 text-white rounded-xl text-xs font-bold uppercase tracking-wider transition-all shadow-sm cursor-pointer"
                          >
                            Mark as Concluded
                          </button>
                        )}
                      </div>
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>
        )}

        {/* TAB 3: SHARED CASES & EVIDENCE */}
        {activeTab === 'cases' && (
          <div className="space-y-6">
            <div className="p-4 bg-purple-50 border border-purple-200 rounded-2xl flex items-start gap-3 text-xs text-purple-900">
              <Lock className="w-5 h-5 text-purple-700 shrink-0 mt-0.5" />
              <div>
                <p className="font-bold">Privileged & Revocable Client Access</p>
                <p className="mt-0.5 leading-relaxed text-purple-800">
                  Citizens explicitly grant and may revoke access to their case records at any time. When granted, you can inspect case facts and generate secure temporary signed URLs (300 seconds TTL) for uploaded evidence. Institutional proctor internal notes are strictly redacted from attorney scope.
                </p>
              </div>
            </div>

            <div className="bg-white rounded-2xl shadow-sm border border-slate-200/80 overflow-hidden">
              <div className="p-4 sm:p-6 border-b border-slate-100">
                <h3 className="font-serif font-bold text-lg text-slate-900">
                  Shared Client Matters ({sharedCases.length})
                </h3>
              </div>

              {sharedCases.length === 0 ? (
                <div className="py-16 text-center text-slate-400">
                  <FolderOpen className="w-10 h-10 mx-auto mb-2 text-slate-300" />
                  <p className="text-xs font-bold text-slate-600">No cases currently shared.</p>
                  <p className="text-[11px] text-slate-400 mt-1 max-w-sm mx-auto">
                    Clients can link their existing NyayPath cases when requesting consultations and grant document access.
                  </p>
                </div>
              ) : (
                <div className="divide-y divide-slate-100">
                  {sharedCases.map((c) => (
                    <div key={c.case_id} className="p-5 sm:p-6 hover:bg-slate-50/70 transition-colors">
                      <div className="flex flex-col sm:flex-row sm:items-start justify-between gap-4">
                        <div className="flex-1">
                          <div className="flex items-center gap-2 mb-1.5">
                            <span className="font-mono text-xs font-bold text-court-maroon bg-rose-50 border border-rose-200 px-2 py-0.5 rounded">
                              {c.case_id}
                            </span>
                            <span className="text-[10px] font-bold uppercase px-2 py-0.5 rounded-full bg-slate-200 text-slate-700">
                              {c.category}
                            </span>
                            <span className="text-[10px] text-slate-400">
                              Filed: {c.filing_date ? new Date(c.filing_date).toLocaleDateString() : 'N/A'}
                            </span>
                          </div>

                          <h4 className="text-sm font-bold text-slate-900 mb-1">{c.title}</h4>
                          <p className="text-xs text-slate-600 leading-relaxed mb-3">
                            {c.facts_summary}
                          </p>

                          <div className="flex items-center gap-4 text-xs text-slate-500">
                            <span>Status: <strong className="text-slate-800">{c.status}</strong></span>
                            {c.prayer && (
                              <span className="line-clamp-1">Prayer: {c.prayer}</span>
                            )}
                          </div>
                        </div>

                        <div className="shrink-0 flex items-center gap-2">
                          <Link
                            href={`/lawyer/cases/${encodeURIComponent(c.case_id)}`}
                            className="px-4 py-2 bg-court-maroon hover:bg-rose-700 text-white rounded-xl text-xs font-bold uppercase tracking-wider transition-all shadow-sm flex items-center gap-1.5"
                          >
                            <FileText size={13} />
                            <span>View Case Dossier & Timeline</span>
                          </Link>
                        </div>
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </div>
          </div>
        )}

        {/* Action Confirmation Modal */}
        {actionModal.isOpen && actionModal.request && (
          <div className="fixed inset-0 z-50 bg-slate-900/60 backdrop-blur-sm flex items-center justify-center p-4">
            <div className="bg-white rounded-2xl max-w-lg w-full p-6 shadow-2xl border border-slate-200 animate-in fade-in zoom-in-95">
              <h3 className="font-serif font-bold text-lg text-slate-900 mb-1">
                {actionModal.action === 'ACCEPTED'
                  ? 'Accept Consultation Request'
                  : actionModal.action === 'DECLINED'
                  ? 'Decline Consultation Request'
                  : 'Conclude Consultation'}
              </h3>
              <p className="text-xs text-slate-500 mb-4">
                Client: <strong className="text-slate-700">{actionModal.request.client?.full_name || 'Citizen'}</strong> • Issue: &ldquo;{actionModal.request.legal_issue}&rdquo;
              </p>

              <div className="mb-4">
                <label className="block text-xs font-semibold text-slate-700 mb-1">
                  Advocate Response / Instructions to Client
                </label>
                <textarea
                  rows={4}
                  value={actionModal.responseMsg}
                  onChange={(e) => setActionModal({ ...actionModal, responseMsg: e.target.value })}
                  placeholder="Provide consultation instructions, proposed timings, or reasons..."
                  className="w-full px-3 py-2 text-xs border border-slate-300 rounded-xl focus:ring-2 focus:ring-court-maroon/20 focus:border-court-maroon outline-none"
                />
              </div>

              <div className="flex items-center justify-end gap-2.5">
                <button
                  type="button"
                  onClick={() => setActionModal({ ...actionModal, isOpen: false })}
                  disabled={actionModal.submitting}
                  className="px-4 py-2 text-xs font-bold text-slate-600 hover:text-slate-900 cursor-pointer"
                >
                  Cancel
                </button>
                <button
                  type="button"
                  onClick={handleConfirmAction}
                  disabled={actionModal.submitting}
                  className={`px-5 py-2 text-white rounded-xl text-xs font-bold uppercase tracking-wider transition-all shadow-md cursor-pointer ${
                    actionModal.action === 'ACCEPTED'
                      ? 'bg-emerald-600 hover:bg-emerald-700'
                      : actionModal.action === 'DECLINED'
                      ? 'bg-rose-600 hover:bg-rose-700'
                      : 'bg-blue-600 hover:bg-blue-700'
                  }`}
                >
                  {actionModal.submitting ? 'Updating...' : `Confirm ${actionModal.action}`}
                </button>
              </div>
            </div>
          </div>
        )}

        {/* Quick Advocate Sign-In Modal */}
        {showAuthModal && (
          <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 backdrop-blur-sm p-4 font-sans">
            <div className="bg-white rounded-3xl max-w-md w-full p-6 shadow-2xl border border-slate-200 animate-in fade-in zoom-in duration-150">
              <div className="flex items-center justify-between pb-4 border-b border-slate-100">
                <div className="flex items-center gap-2">
                  <div className="w-8 h-8 rounded-full bg-rose-100 flex items-center justify-center text-court-maroon font-bold text-xs">
                    <Scale className="w-4 h-4" />
                  </div>
                  <div>
                    <h3 className="font-bold text-slate-900 text-sm">Advocate Portal Authentication</h3>
                    <p className="text-[11px] text-slate-500">Sign in with Bar Council credentials</p>
                  </div>
                </div>
                <button
                  type="button"
                  onClick={() => setShowAuthModal(false)}
                  className="text-slate-400 hover:text-slate-600 text-sm font-bold cursor-pointer"
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
                  <label className="block text-[11px] font-bold text-slate-700 uppercase mb-1">Advocate Email</label>
                  <input
                    type="email"
                    value={authEmail}
                    onChange={(e) => setAuthEmail(e.target.value)}
                    className="w-full px-3.5 py-2.5 rounded-xl border border-slate-300 text-xs focus:ring-2 focus:ring-court-maroon focus:outline-none"
                    placeholder="advocate.rajesh@bar.in"
                    required
                  />
                </div>
                <div>
                  <label className="block text-[11px] font-bold text-slate-700 uppercase mb-1">Password</label>
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

                {/* Quick-fill accounts for demo */}
                <div className="p-3 rounded-xl bg-slate-50 border border-slate-200">
                  <span className="text-[10px] font-bold text-slate-500 uppercase tracking-wider block mb-1.5">
                    Demo Verified Advocates (Click to fill):
                  </span>
                  <div className="flex flex-wrap gap-1.5">
                    <button
                      type="button"
                      onClick={() => {
                        setAuthEmail('advocate.rajesh@bar.in');
                        setAuthPassword('');
                      }}
                      className="px-2.5 py-1 rounded-lg bg-white border border-slate-200 text-slate-800 text-[11px] font-semibold hover:border-court-maroon cursor-pointer"
                    >
                      Adv. Rajesh Kumar
                    </button>
                    <button
                      type="button"
                      onClick={() => {
                        setAuthEmail('advocate.priya@bar.in');
                        setAuthPassword('');
                      }}
                      className="px-2.5 py-1 rounded-lg bg-white border border-slate-200 text-slate-800 text-[11px] font-semibold hover:border-court-maroon cursor-pointer"
                    >
                      Adv. Priya Sharma
                    </button>
                  </div>
                </div>

                <div className="flex justify-end gap-2 pt-2">
                  <button
                    type="button"
                    onClick={() => setShowAuthModal(false)}
                    className="px-4 py-2 rounded-xl text-slate-600 text-xs font-semibold hover:bg-slate-100 cursor-pointer"
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
    </div>
  );
}

