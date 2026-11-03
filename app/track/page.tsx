'use client';

import React, { useState, useEffect, useMemo, Suspense } from 'react';
import { useSearchParams, useRouter } from 'next/navigation';
import Link from 'next/link';
import {
  Clock,
  AlertTriangle,
  CheckCircle2,
  FileText,
  Scale,
  RefreshCw,
  Search,
  ArrowRight,
  Sparkles,
  Send,
  History,
  AlertCircle,
  Copy,
  Check,
  ArrowLeft,
  ShieldCheck,
  ShieldAlert,
  Lock,
  Eye,
  X,
  Building2,
  Calendar
} from 'lucide-react';
import {
  getWatchdogState,
  recordWatchdogResponse,
  simulateWatchdog,
  getCitizenCase
} from '@/lib/api';

function formatCountdown(totalSeconds: number) {
  if (totalSeconds <= 0) {
    return { days: 0, hours: 0, minutes: 0, seconds: 0 };
  }
  const days = Math.floor(totalSeconds / 86400);
  const hours = Math.floor((totalSeconds % 86400) / 3600);
  const minutes = Math.floor((totalSeconds % 3600) / 60);
  const seconds = totalSeconds % 60;
  return { days, hours, minutes, seconds };
}

interface WatchdogEvent {
  type: string;
  timestamp: string;
  metadata?: any;
}

interface CaseWatchdogData {
  case_id: string;
  category?: string;
  case_type?: string;
  has_statutory_deadline?: boolean;
  statutory_rule_name?: string;
  statutory_source?: string;
  statutory_verification_date?: string;
  statutory_deadline_display?: string;
  statutory_deadline_message?: string;
  time_elapsed_since_submission_seconds?: number;
  time_elapsed_since_submission_formatted?: string;
  time_in_current_stage_seconds?: number;
  time_in_current_stage_formatted?: string;
  current_responsible_authority?: string;
  next_expected_action?: string;
  watchdog_enabled?: boolean;
  watchdog_status?: string;
  computed_status?: string;
  filing_date?: string;
  response_due_date?: string;
  first_appeal_due_date?: string;
  response_received_at?: string;
  is_overdue?: boolean;
  days_remaining?: number;
  days_overdue?: number;
  time_remaining_seconds?: number;
  section_20_penalty_inr?: number;
  appeal_eligible?: boolean;
  last_watchdog_check_at?: string;
  last_watchdog_event?: string;
  watchdog_events?: WatchdogEvent[];
  notification_state?: any;
  pio_response_text?: string;
  exemption_cited?: string;
  legal_counter?: string;
  precedent_title?: string;
  third_party_notice_due_date?: string;
  third_party_notice_source?: string;
  third_party_representation_source?: string;
  third_party_decision_source?: string;
  fee_exclusion_applied?: boolean;
  fee_exclusion_days?: number;
  first_appeal_draft?: string;
  department_info?: any;
  form_data?: any;
  user_problem?: string;
  data?: any;
}

function TrackPageContent() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const caseIdParam = searchParams.get('case_id');

  const [inputCaseId, setInputCaseId] = useState(caseIdParam || '');
  const [caseData, setCaseData] = useState<CaseWatchdogData | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // Live ticking countdown state for statutory RTI matters
  const [secondsRemaining, setSecondsRemaining] = useState<number>(0);

  // PIO Response & Counter State
  const [pioInputText, setPioInputText] = useState('');
  const [responseDate, setResponseDate] = useState(new Date().toISOString().split('T')[0]);
  const [analyzing, setAnalyzing] = useState(false);
  const [simulating, setSimulating] = useState(false);
  const [copiedPasskey, setCopiedPasskey] = useState(false);

  // Owner Full Complaint Details Modal
  const [isOwnerModalOpen, setIsOwnerModalOpen] = useState(false);
  const [loadingOwnerDossier, setLoadingOwnerDossier] = useState(false);
  const [ownerDossier, setOwnerDossier] = useState<any>(null);
  const [ownerAuthError, setOwnerAuthError] = useState<string | null>(null);

  const fetchCaseDetails = async (id: string) => {
    const cleanId = id.trim().toUpperCase();
    if (!cleanId) return;

    setLoading(true);
    setError(null);
    try {
      const data = await getWatchdogState(cleanId);
      setCaseData(data);
      if (data.has_statutory_deadline && data.time_remaining_seconds !== undefined) {
        setSecondsRemaining(data.time_remaining_seconds);
      }
    } catch (err: any) {
      console.error('Watchdog query error:', err);
      setCaseData(null);
      setError(err?.response?.data?.detail || err?.message || 'Case ID not found or error loading progress.');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    if (caseIdParam) {
      setInputCaseId(caseIdParam);
      fetchCaseDetails(caseIdParam);
    }
  }, [caseIdParam]);

  // Live countdown timer for cases with statutory deadlines
  useEffect(() => {
    if (!caseData?.has_statutory_deadline || secondsRemaining <= 0) return;
    const interval = setInterval(() => {
      setSecondsRemaining((prev) => {
        if (prev <= 1) {
          clearInterval(interval);
          if (caseData?.case_id) fetchCaseDetails(caseData.case_id);
          return 0;
        }
        return prev - 1;
      });
    }, 1000);
    return () => clearInterval(interval);
  }, [caseData?.has_statutory_deadline, secondsRemaining]);

  const handleSearchSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (!inputCaseId.trim()) return;
    router.push(`/track?case_id=${encodeURIComponent(inputCaseId.trim().toUpperCase())}`);
    fetchCaseDetails(inputCaseId);
  };

  const handleCopyPasskey = () => {
    if (!caseData?.case_id) return;
    navigator.clipboard.writeText(caseData.case_id);
    setCopiedPasskey(true);
    setTimeout(() => setCopiedPasskey(false), 2000);
  };

  const handleRecordResponse = async (e?: React.FormEvent) => {
    if (e) e.preventDefault();
    if (!caseData?.case_id) return;

    setAnalyzing(true);
    try {
      await recordWatchdogResponse(
        caseData.case_id,
        pioInputText.trim() || '',
        responseDate ? `${responseDate}T12:00:00Z` : undefined
      );
      await fetchCaseDetails(caseData.case_id);
    } catch (err: any) {
      console.error('Failed to record PIO response:', err);
      alert(err?.response?.data?.detail || 'Failed to analyze response.');
    } finally {
      setAnalyzing(false);
    }
  };

  const handleSimulate = async (scenario: string, daysAgo?: number) => {
    if (!caseData?.case_id) return;
    setSimulating(true);
    try {
      await simulateWatchdog(caseData.case_id, scenario, daysAgo);
      await fetchCaseDetails(caseData.case_id);
    } catch (err) {
      console.error('Simulation error:', err);
    } finally {
      setSimulating(false);
    }
  };

  // Open Full Complaint Details with Owner Authentication check
  const handleOpenOwnerDossier = async () => {
    if (!caseData?.case_id) return;
    setIsOwnerModalOpen(true);
    setLoadingOwnerDossier(true);
    setOwnerAuthError(null);
    setOwnerDossier(null);

    try {
      const res = await getCitizenCase(caseData.case_id);
      setOwnerDossier(res.case || res);
    } catch (err: any) {
      console.error('Owner authentication failed for full dossier:', err);
      setOwnerAuthError(
        'Owner Authentication Required: Possession of a tracking key grants access to sanitized progress only. Full complaint text, sensitive statements, and attached documents are protected and require logging in as the verified case owner.'
      );
    } finally {
      setLoadingOwnerDossier(false);
    }
  };

  const countdown = useMemo(() => formatCountdown(secondsRemaining), [secondsRemaining]);

  return (
    <div 
      className="min-h-screen font-sans p-4 sm:p-6 lg:p-8 selection:bg-court-maroon selection:text-white pb-24 bg-cover bg-center bg-no-repeat relative text-slate-100"
      style={{ backgroundImage: "url('/bg.image.png')" }}
    >
      <div className="max-w-6xl mx-auto space-y-8 pt-4 relative z-10">
        
        {/* TOP NAVIGATION & SEARCH */}
        <div className="flex flex-col md:flex-row md:items-center justify-between gap-6 border-b border-white/20 pb-6">
          <div className="flex items-start sm:items-center gap-4">
            <button 
              onClick={() => router.push('/')}
              className="p-2.5 rounded-xl bg-white border border-slate-300 text-slate-700 hover:text-ashoka-navy hover:bg-slate-100 transition shadow-sm cursor-pointer shrink-0 mt-1 sm:mt-0"
              title="Back to Landing Page"
            >
              <ArrowLeft size={18} />
            </button>
            <div>
              <div className="flex items-center gap-2">
                <span className="h-2.5 w-2.5 rounded-full bg-emerald-400 animate-pulse hidden sm:inline-block" />
                <span className="text-xs font-mono font-bold uppercase tracking-widest text-emerald-300 bg-emerald-950/80 px-2.5 py-0.5 rounded-full border border-emerald-500/30">
                  STATUTORY SLA & CASE PROGRESS ENGINE
                </span>
              </div>
              <h1 className="text-2xl md:text-3xl font-black tracking-tight text-white flex items-center gap-3 drop-shadow-md mt-1">
                NyayPath Case Tracker
              </h1>
              <p className="text-blue-100 text-xs sm:text-sm font-medium drop-shadow-sm">
                Verified statutory timelines, stage duration metrics, and sanitized complaint monitoring
              </p>
            </div>
          </div>

          <form onSubmit={handleSearchSubmit} className="flex gap-2 w-full md:w-auto pl-12 sm:pl-0">
            <input
              type="text"
              placeholder="Enter Case ID or Passkey"
              value={inputCaseId}
              onChange={(e) => setInputCaseId(e.target.value.toUpperCase())}
              className="bg-white border border-slate-300 rounded-xl px-4 py-2.5 text-sm text-ashoka-navy font-bold focus:outline-none focus:border-[#FF9933] focus:ring-1 focus:ring-[#FF9933] w-full sm:w-60 uppercase tracking-widest shadow-sm placeholder:text-slate-400 placeholder:font-medium placeholder:tracking-normal placeholder:normal-case"
            />
            <button
              type="submit"
              disabled={loading}
              className="bg-gradient-to-r from-court-maroon via-rose-700 to-court-maroon hover:from-rose-700 hover:to-rose-800 transition-colors text-white font-bold text-sm px-6 py-2.5 rounded-xl cursor-pointer disabled:opacity-50 shadow-md shrink-0 tracking-tight"
            >
              {loading ? <RefreshCw className="animate-spin" size={16} /> : 'Track'}
            </button>
          </form>
        </div>

        {error && (
          <div className="bg-red-50 border border-red-200 text-red-800 p-4 rounded-2xl text-sm font-medium shadow-sm backdrop-blur-sm flex items-center gap-3">
            <AlertCircle size={20} className="text-red-600 shrink-0" />
            <span>⚠️ {error}</span>
          </div>
        )}

        {/* EMPTY SEARCH STATE */}
        {!caseData && !loading && !error && (
          <div className="mt-12 flex flex-col items-center justify-center text-center animate-in fade-in slide-in-from-bottom-4 duration-500">
            <div className="w-20 h-20 bg-white/95 border border-slate-300 rounded-full flex items-center justify-center mb-6 shadow-md backdrop-blur-md">
              <Search className="w-10 h-10 text-slate-400" />
            </div>
            <h2 className="text-2xl sm:text-3xl font-extrabold text-white mb-3 tracking-tight drop-shadow-md">
              Track Your Legal Matter & SLA Compliance
            </h2>
            <p className="text-slate-200 max-w-lg mb-12 font-medium leading-relaxed text-sm sm:text-base drop-shadow-sm">
              Enter your Case Reference ID or Tracking Key above to inspect your verified case progress, track elapsed time and stage durations, and view statutory SLA milestones where legally applicable.
            </p>

            <div className="grid grid-cols-1 md:grid-cols-3 gap-6 max-w-5xl w-full text-left">
              <div className="bg-white/95 backdrop-blur-md border border-slate-300 p-6 sm:p-8 rounded-3xl shadow-xl">
                <div className="w-12 h-12 bg-amber-50 rounded-2xl flex items-center justify-center mb-5 border border-amber-200">
                  <Clock className="w-6 h-6 text-amber-600" />
                </div>
                <h3 className="font-extrabold text-ashoka-navy mb-2 text-base tracking-tight">Verified Statutory Timelines</h3>
                <p className="text-sm text-slate-600 leading-relaxed font-medium">
                  NyayPath enforces real statutory rules (e.g. Section 7(1) of the RTI Act, 2005) only when backed by authoritative law. For unconfigured matters, no arbitrary universal deadline is assumed.
                </p>
              </div>
              
              <div className="bg-white/95 backdrop-blur-md border border-slate-300 p-6 sm:p-8 rounded-3xl shadow-xl">
                <div className="w-12 h-12 bg-emerald-50 rounded-2xl flex items-center justify-center mb-5 border border-emerald-200">
                  <Building2 className="w-6 h-6 text-emerald-600" />
                </div>
                <h3 className="font-extrabold text-ashoka-navy mb-2 text-base tracking-tight">Stage Duration & Elapsed Time</h3>
                <p className="text-sm text-slate-600 leading-relaxed font-medium">
                  Deterministically measures elapsed time since filing and active duration in the current inquiry stage, clearly identifying the responsible public authority and next steps.
                </p>
              </div>
              
              <div className="bg-white/95 backdrop-blur-md border border-slate-300 p-6 sm:p-8 rounded-3xl shadow-xl">
                <div className="w-12 h-12 bg-rose-50 rounded-2xl flex items-center justify-center mb-5 border border-rose-200">
                  <Lock className="w-6 h-6 text-court-maroon" />
                </div>
                <h3 className="font-extrabold text-ashoka-navy mb-2 text-base tracking-tight">Owner-Guarded Full Details</h3>
                <p className="text-sm text-slate-600 leading-relaxed font-medium">
                  Public tracking keys display sanitized status metrics without PII. Complete complaint text, citizen statements, and evidence documents require verified owner authentication.
                </p>
              </div>
            </div>
          </div>
        )}

        {/* ACTIVE CASE TRACKING DASHBOARD */}
        {caseData && (
          <div className="space-y-8 animate-in fade-in zoom-in-95 duration-300">
            
            {/* 1. TOP HERO BANNER */}
            <div className="bg-white/95 backdrop-blur-md border border-slate-300 rounded-3xl p-6 sm:p-8 shadow-xl text-ashoka-navy">
              <div className="flex flex-col lg:flex-row lg:items-center justify-between gap-6 pb-6 border-b border-slate-200">
                
                <div className="space-y-2">
                  <div className="flex flex-wrap items-center gap-2">
                    <span className="text-xs font-mono font-bold uppercase tracking-widest text-emerald-800 bg-emerald-100 px-3 py-1 rounded-full border border-emerald-300">
                      STATUS: {caseData.watchdog_status?.replace(/_/g, ' ') || 'ACTIVE'}
                    </span>
                    <span className="text-xs font-bold uppercase px-2.5 py-1 rounded-full bg-slate-100 text-slate-700">
                      CATEGORY: {caseData.category || caseData.case_type || 'LEGAL COMPLAINT'}
                    </span>
                  </div>

                  <h2 className="text-2xl sm:text-3xl font-black text-ashoka-navy tracking-tight">
                    Case Reference #{caseData.case_id}
                  </h2>
                  <p className="text-xs sm:text-sm text-slate-600 font-medium max-w-2xl">
                    Filed: {caseData.filing_date ? new Date(caseData.filing_date).toLocaleDateString() : 'Recorded on File'} | Last Activity: {caseData.last_watchdog_event?.replace(/_/g, ' ') || 'Registered'}
                  </p>
                </div>

                {/* PASSKEY & VIEW FULL COMPLAINT BUTTON */}
                <div className="bg-[#F8FAFC] border border-slate-300 rounded-2xl p-4 sm:p-5 flex flex-col sm:flex-row lg:flex-col items-start sm:items-center lg:items-start justify-between gap-3 shrink-0 shadow-inner">
                  <div>
                    <span className="text-[10px] font-mono font-bold uppercase tracking-widest text-slate-500">
                      TRACKING IDENTIFIER
                    </span>
                    <div className="text-xl font-mono font-black text-ashoka-navy tracking-widest mt-0.5">
                      {caseData.case_id}
                    </div>
                  </div>

                  <div className="flex items-center gap-2 w-full">
                    <button
                      type="button"
                      onClick={handleCopyPasskey}
                      className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-xl bg-white border border-slate-300 hover:bg-slate-50 text-slate-700 font-bold text-xs shadow-sm transition cursor-pointer"
                    >
                      {copiedPasskey ? <Check size={13} className="text-emerald-600" /> : <Copy size={13} />}
                      <span>{copiedPasskey ? 'Copied' : 'Copy'}</span>
                    </button>

                    <button
                      type="button"
                      onClick={handleOpenOwnerDossier}
                      className="inline-flex items-center gap-1.5 px-3.5 py-1.5 rounded-xl bg-court-maroon hover:bg-rose-700 text-white font-bold text-xs shadow-sm transition cursor-pointer"
                      title="Inspect complete complaint text, submitted details, and documents (Owner Login Required)"
                    >
                      <Lock size={13} />
                      <span>View Full Details</span>
                    </button>
                  </div>
                </div>
              </div>

              {/* 2. STATUTORY DEADLINE STATUS SECTION */}
              <div className="pt-6">
                {caseData.has_statutory_deadline ? (
                  // Statutory RTI window exists
                  <div className="grid grid-cols-1 lg:grid-cols-12 gap-6 items-center">
                    <div className="lg:col-span-6 bg-slate-900 text-white rounded-2xl p-5 sm:p-6 shadow-md">
                      <div className="flex items-center justify-between mb-2">
                        <span className="text-[10px] font-mono font-bold uppercase tracking-widest text-amber-400">
                          {caseData.statutory_rule_name}
                        </span>
                        <span className="text-[10px] font-mono text-slate-400">
                          Verified: {caseData.statutory_verification_date}
                        </span>
                      </div>

                      {caseData.is_overdue ? (
                        <div className="mt-2 text-rose-400 font-black text-2xl sm:text-3xl tracking-tight">
                          OVERDUE BY {caseData.days_overdue} DAY(S)
                        </div>
                      ) : (
                        <div className="grid grid-cols-4 gap-2 mt-2 text-center">
                          <div className="bg-slate-800/80 p-2.5 rounded-xl border border-slate-700">
                            <div className="text-2xl sm:text-3xl font-mono font-black text-amber-400">
                              {String(countdown.days).padStart(2, '0')}
                            </div>
                            <div className="text-[9px] uppercase font-bold text-slate-400 tracking-wider">Days</div>
                          </div>
                          <div className="bg-slate-800/80 p-2.5 rounded-xl border border-slate-700">
                            <div className="text-2xl sm:text-3xl font-mono font-black text-white">
                              {String(countdown.hours).padStart(2, '0')}
                            </div>
                            <div className="text-[9px] uppercase font-bold text-slate-400 tracking-wider">Hours</div>
                          </div>
                          <div className="bg-slate-800/80 p-2.5 rounded-xl border border-slate-700">
                            <div className="text-2xl sm:text-3xl font-mono font-black text-white">
                              {String(countdown.minutes).padStart(2, '0')}
                            </div>
                            <div className="text-[9px] uppercase font-bold text-slate-400 tracking-wider">Mins</div>
                          </div>
                          <div className="bg-slate-800/80 p-2.5 rounded-xl border border-slate-700">
                            <div className="text-2xl sm:text-3xl font-mono font-black text-emerald-400">
                              {String(countdown.seconds).padStart(2, '0')}
                            </div>
                            <div className="text-[9px] uppercase font-bold text-slate-400 tracking-wider">Secs</div>
                          </div>
                        </div>
                      )}

                      <div className="mt-3 pt-3 border-t border-slate-800 text-[11px] text-slate-400 space-y-1.5">
                        <p className="font-medium text-slate-300">
                          Statutory Authority: <span className="text-amber-300">{caseData.statutory_source}</span>
                        </p>
                        {caseData.third_party_notice_due_date && (
                          <div className="p-2.5 rounded-xl bg-slate-800/80 border border-slate-700 space-y-1 text-[10px] text-slate-300">
                            <p className="text-amber-400 font-bold uppercase tracking-wider">Statutory Third-Party Process (Section 11):</p>
                            <p>• <strong>Section 11(1):</strong> Written notice to third party within 5 days of request receipt.</p>
                            <p>• <strong>Section 11(2):</strong> 10-day representation window allowed to third party.</p>
                            <p>• <strong>Section 11(3):</strong> PIO decision on disclosure within 40 days of request.</p>
                          </div>
                        )}
                        {caseData.fee_exclusion_applied && (
                          <p className="text-blue-300 text-[10px]">
                            • <strong>Section 7(3)(a) Proviso:</strong> {caseData.fee_exclusion_days} day(s) fee payment period excluded from countdown.
                          </p>
                        )}
                      </div>
                    </div>

                    <div className="lg:col-span-6 space-y-3">
                      {caseData.is_overdue ? (
                        <div className="bg-rose-50 border border-rose-200 p-5 rounded-2xl text-court-maroon space-y-2">
                          <div className="flex items-center gap-2 font-bold text-sm">
                            <AlertTriangle size={18} className="text-court-maroon shrink-0" />
                            <span>Statutory Response Window Expired (Deemed Refusal)</span>
                          </div>
                          <p className="text-xs text-slate-700 leading-relaxed font-medium">
                            Under <strong>Section 7(2)</strong> of the RTI Act, failure to respond within 30 days is legally treated as a deemed refusal. You are now entitled to file a <strong>Section 19(1) First Appeal</strong>.
                          </p>
                        </div>
                      ) : (
                        <div className="bg-emerald-50 border border-emerald-200 p-5 rounded-2xl text-emerald-900 space-y-2">
                          <div className="flex items-center gap-2 font-bold text-sm">
                            <ShieldCheck size={18} className="text-emerald-600 shrink-0" />
                            <span>Mandatory Statutory Window Active</span>
                          </div>
                          <p className="text-xs text-emerald-800 leading-relaxed font-medium">
                            The concerned Public Information Officer is legally obligated to provide certified records by {caseData.response_due_date ? new Date(caseData.response_due_date).toLocaleDateString() : 'N/A'}.
                          </p>
                        </div>
                      )}
                    </div>
                  </div>
                ) : (
                  // No verified statutory deadline configured
                  <div className="p-5 rounded-2xl bg-slate-50 border border-slate-200 text-slate-700 flex flex-col sm:flex-row sm:items-center justify-between gap-4">
                    <div className="space-y-1">
                      <div className="flex items-center gap-2 font-bold text-sm text-slate-900">
                        <Calendar size={18} className="text-court-maroon shrink-0" />
                        <span>No verified statutory deadline configured for this case.</span>
                      </div>
                      <p className="text-xs text-slate-600 leading-relaxed">
                        NyayPath does not fabricate deadlines. This matter is handled under administrative grievance procedures without a universal 30-day statutory expiry.
                      </p>
                    </div>
                    <span className="text-[11px] font-mono font-bold px-3 py-1 rounded-full bg-slate-200 text-slate-700 shrink-0">
                      Standard Administrative Flow
                    </span>
                  </div>
                )}
              </div>
            </div>

            {/* 3. METRIC CARDS (Timing, Authority, Next Step) */}
            <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-6">
              
              <div className="bg-white/95 backdrop-blur-md border border-slate-300 rounded-3xl p-6 shadow-xl space-y-2 text-ashoka-navy">
                <span className="text-xs font-bold uppercase text-slate-500 tracking-wider font-sans">
                  Time Elapsed Since Filing
                </span>
                <div className="text-2xl font-black text-ashoka-navy tracking-tight">
                  {caseData.time_elapsed_since_submission_formatted || '0d elapsed'}
                </div>
                <p className="text-xs text-slate-500 font-medium">
                  Continuous tracker from submission
                </p>
              </div>

              <div className="bg-white/95 backdrop-blur-md border border-slate-300 rounded-3xl p-6 shadow-xl space-y-2 text-ashoka-navy">
                <span className="text-xs font-bold uppercase text-slate-500 tracking-wider font-sans">
                  Time in Current Stage
                </span>
                <div className="text-2xl font-black text-amber-600 tracking-tight">
                  {caseData.time_in_current_stage_formatted || '0d in stage'}
                </div>
                <p className="text-xs text-slate-500 font-medium">
                  Active duration at current status
                </p>
              </div>

              <div className="bg-white/95 backdrop-blur-md border border-slate-300 rounded-3xl p-6 shadow-xl space-y-2 text-ashoka-navy">
                <span className="text-xs font-bold uppercase text-slate-500 tracking-wider font-sans">
                  Responsible Authority
                </span>
                <div className="text-sm font-bold text-slate-900 tracking-tight line-clamp-2">
                  {caseData.current_responsible_authority || 'Competent Authority'}
                </div>
                <p className="text-xs text-slate-500 font-medium">
                  Dealing administrative office
                </p>
              </div>

              <div className="bg-white/95 backdrop-blur-md border border-slate-300 rounded-3xl p-6 shadow-xl space-y-2 text-ashoka-navy">
                <span className="text-xs font-bold uppercase text-slate-500 tracking-wider font-sans">
                  Next Expected Step
                </span>
                <div className="text-sm font-bold text-emerald-700 tracking-tight line-clamp-2">
                  {caseData.next_expected_action || 'Administrative Review'}
                </div>
                <p className="text-xs text-slate-500 font-medium">
                  Expected procedural milestone
                </p>
              </div>
            </div>

            {/* 4. CHRONOLOGICAL EVENT TIMELINE */}
            <div className="bg-white/95 backdrop-blur-md border border-slate-300 rounded-3xl p-6 sm:p-8 shadow-xl text-ashoka-navy space-y-6">
              <div className="flex items-center justify-between border-b border-slate-200 pb-4">
                <div>
                  <h3 className="text-lg font-black text-ashoka-navy tracking-tight flex items-center gap-2">
                    <History size={20} className="text-court-maroon" />
                    <span>Case Milestone & Activity Chronology</span>
                  </h3>
                  <p className="text-xs text-slate-500 font-medium mt-0.5">
                    User-visible audit log showing verified filing dates, status updates, and milestone events.
                  </p>
                </div>
              </div>

              {caseData.watchdog_events && caseData.watchdog_events.length > 0 ? (
                <div className="relative pl-6 space-y-4 before:absolute before:left-2 before:top-2 before:bottom-2 before:w-0.5 before:bg-slate-200">
                  {caseData.watchdog_events.map((ev, i) => (
                    <div key={i} className="relative">
                      <div className="absolute -left-[21px] top-1.5 w-2.5 h-2.5 rounded-full bg-court-maroon ring-4 ring-white" />
                      <div className="p-3 bg-[#F8FAFC] rounded-xl border border-slate-200 text-xs">
                        <div className="flex items-center justify-between mb-1">
                          <span className="font-bold text-slate-900">{ev.type.replace(/_/g, ' ')}</span>
                          <span className="text-[10px] font-mono text-slate-400">
                            {ev.timestamp ? new Date(ev.timestamp).toLocaleString() : 'Recorded'}
                          </span>
                        </div>
                        {ev.metadata && Object.keys(ev.metadata).length > 0 && (
                          <div className="text-[11px] text-slate-600 font-mono">
                            {JSON.stringify(ev.metadata)}
                          </div>
                        )}
                      </div>
                    </div>
                  ))}
                </div>
              ) : (
                <div className="p-4 rounded-xl bg-slate-50 border border-slate-200 text-xs text-slate-500 text-center">
                  Case filed on {caseData.filing_date ? new Date(caseData.filing_date).toLocaleDateString() : 'Record'}. Subsequent milestones will appear here as proceedings advance.
                </div>
              )}
            </div>

            {/* 5. FIRST APPEAL & RESPONSE SUITE (If RTI matter) */}
            {caseData.has_statutory_deadline && (
              <div className="bg-white/95 backdrop-blur-md border border-slate-300 rounded-3xl p-6 sm:p-8 shadow-xl text-ashoka-navy space-y-6">
                <div className="flex flex-col sm:flex-row justify-between sm:items-center gap-4 border-b border-slate-200 pb-5">
                  <div>
                    <h3 className="text-xl font-extrabold text-ashoka-navy tracking-tight flex items-center gap-2">
                      <Send size={20} className="text-court-maroon" />
                      Public Information Officer (PIO) Response Suite
                    </h3>
                    <p className="text-xs sm:text-sm text-slate-600 font-medium mt-1">
                      Did you receive a reply letter or email from the authority? Log it here for automatic legal analysis.
                    </p>
                  </div>
                </div>

                <form onSubmit={handleRecordResponse} className="space-y-4">
                  <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
                    <div className="sm:col-span-1">
                      <label className="block text-xs font-bold uppercase tracking-wider text-slate-600 mb-1.5 font-sans">
                        Date Response Received
                      </label>
                      <input
                        type="date"
                        value={responseDate}
                        onChange={(e) => setResponseDate(e.target.value)}
                        className="w-full bg-[#F8FAFC] border border-slate-300 rounded-xl px-3.5 py-2.5 text-xs text-ashoka-navy font-bold focus:outline-none focus:border-[#FF9933]"
                      />
                    </div>
                  </div>

                  <div>
                    <label className="block text-xs font-bold uppercase tracking-wider text-slate-600 mb-1.5 font-sans">
                      Paste PIO Reply Letter / Email Text
                    </label>
                    <textarea
                      rows={4}
                      value={pioInputText}
                      onChange={(e) => setPioInputText(e.target.value)}
                      placeholder="Paste the official response text received from the PIO here..."
                      className="w-full bg-[#F8FAFC] border border-slate-300 rounded-2xl p-4 text-xs sm:text-sm text-ashoka-navy font-medium focus:outline-none focus:border-[#FF9933] resize-none leading-relaxed placeholder-slate-400"
                    />
                  </div>

                  <div className="flex justify-end">
                    <button
                      type="submit"
                      disabled={analyzing || !pioInputText.trim()}
                      className="py-3 px-6 cursor-pointer bg-gradient-to-r from-court-maroon via-rose-700 to-court-maroon hover:from-rose-700 hover:to-rose-800 transition-colors text-white flex items-center gap-2 shadow-md rounded-xl font-bold text-xs sm:text-sm disabled:opacity-50 tracking-tight"
                    >
                      {analyzing ? <RefreshCw className="animate-spin" size={16} /> : <Sparkles size={16} />}
                      <span>Log & Analyze PIO Reply</span>
                    </button>
                  </div>
                </form>

                {/* First Appeal Button if overdue */}
                {(caseData.watchdog_status === 'DEEMED_REFUSAL' || caseData.is_overdue) && (
                  <div className="mt-6 bg-rose-50 border border-rose-200 rounded-2xl p-5 flex flex-col sm:flex-row sm:items-center justify-between gap-4">
                    <div>
                      <h4 className="text-sm font-extrabold text-court-maroon">
                        First Appeal Available (Statutory Deadline Expired)
                      </h4>
                      <p className="text-xs text-slate-600 mt-0.5 font-medium">
                        Since the 30-day statutory window expired with no recorded reply, you are entitled to file a First Appeal before the Appellate Authority under Section 19(1).
                      </p>
                    </div>
                    <Link
                      href={`/rti/appeal?case_id=${caseData.case_id}&mode=appeal`}
                      className="bg-court-maroon hover:bg-rose-700 text-white font-bold text-xs px-5 py-3 rounded-xl transition shadow-md shrink-0 flex items-center gap-2 tracking-tight"
                    >
                      <span>Draft First Appeal</span>
                      <ArrowRight size={14} />
                    </Link>
                  </div>
                )}
              </div>
            )}

          </div>
        )}

        {/* ============================================================= */}
        {/* MODAL: OWNER FULL COMPLAINT DETAILS DOSSIER                   */}
        {/* ============================================================= */}
        {isOwnerModalOpen && (
          <div className="fixed inset-0 z-50 bg-slate-900/60 backdrop-blur-sm flex items-center justify-center p-4">
            <div className="bg-white text-slate-900 rounded-3xl max-w-2xl w-full p-6 shadow-2xl border border-slate-200 max-h-[90vh] overflow-y-auto space-y-4">
              <div className="flex items-center justify-between border-b border-slate-100 pb-3">
                <div className="flex items-center gap-2">
                  <Lock size={18} className="text-court-maroon" />
                  <h3 className="font-bold text-base text-slate-900">
                    Full Case Dossier (Owner Protected)
                  </h3>
                </div>
                <button
                  type="button"
                  onClick={() => setIsOwnerModalOpen(false)}
                  className="p-1 rounded-lg text-slate-400 hover:text-slate-600 hover:bg-slate-100"
                >
                  <X size={18} />
                </button>
              </div>

              {loadingOwnerDossier ? (
                <div className="py-12 text-center text-xs text-slate-500">
                  <RefreshCw size={20} className="animate-spin mx-auto mb-2 text-court-maroon" />
                  Verifying authenticated case owner credentials...
                </div>
              ) : ownerAuthError ? (
                <div className="p-5 bg-amber-50 border border-amber-200 rounded-2xl text-amber-950 space-y-3 text-xs leading-relaxed">
                  <div className="flex items-center gap-2 font-bold text-sm text-amber-900">
                    <ShieldAlert size={18} className="text-amber-700" />
                    <span>Owner Login Required</span>
                  </div>
                  <p>{ownerAuthError}</p>
                  <div className="pt-2 flex justify-end">
                    <Link
                      href={`/dashboard?return_to=${encodeURIComponent(`/track?case_id=${caseData?.case_id}`)}`}
                      className="px-4 py-2 bg-court-maroon hover:bg-rose-700 text-white rounded-xl font-bold text-xs shadow-sm transition"
                    >
                      Log In to Access Full Complaint
                    </Link>
                  </div>
                </div>
              ) : ownerDossier ? (
                <div className="space-y-4 text-xs">
                  <div className="p-4 bg-slate-50 rounded-2xl border border-slate-200 space-y-2">
                    <div className="flex items-center justify-between">
                      <span className="font-bold text-slate-900 text-sm">
                        {ownerDossier.title || `Matter #${ownerDossier.case_id}`}
                      </span>
                      <span className="font-mono text-emerald-700 bg-emerald-50 px-2 py-0.5 rounded border border-emerald-200 font-bold">
                        {ownerDossier.status}
                      </span>
                    </div>
                    <p className="text-slate-700 leading-relaxed font-sans">
                      {ownerDossier.problem_text || ownerDossier.description || ownerDossier.details?.description || 'Full statement on record.'}
                    </p>
                  </div>

                  {ownerDossier.documents && ownerDossier.documents.length > 0 && (
                    <div>
                      <h4 className="font-bold text-slate-800 mb-2">Attached Documents:</h4>
                      <div className="space-y-1.5">
                        {ownerDossier.documents.map((doc: any, idx: number) => (
                          <div key={idx} className="p-2.5 bg-white border border-slate-200 rounded-xl flex items-center justify-between">
                            <span className="font-mono text-slate-700">{doc.file_name || `Document #${idx + 1}`}</span>
                            <span className="text-[10px] text-slate-400 font-mono">{doc.mime_type}</span>
                          </div>
                        ))}
                      </div>
                    </div>
                  )}

                  <div className="p-3 bg-emerald-50 rounded-xl text-emerald-900 text-[11px] flex items-center gap-2">
                    <ShieldCheck size={14} className="text-emerald-600" />
                    <span>Authenticated ownership confirmed. Full confidential dossier unlocked.</span>
                  </div>
                </div>
              ) : null}

              <div className="pt-2 flex justify-end border-t border-slate-100">
                <button
                  type="button"
                  onClick={() => setIsOwnerModalOpen(false)}
                  className="px-4 py-2 rounded-xl text-xs font-bold text-slate-600 hover:bg-slate-100"
                >
                  Close
                </button>
              </div>
            </div>
          </div>
        )}

      </div>
    </div>
  );
}

export default function TrackPage() {
  return (
    <Suspense 
      fallback={
        <div className="min-h-screen flex flex-col items-center justify-center p-6 text-sm font-bold text-white tracking-wide bg-cover bg-center" style={{ backgroundImage: "url('/bg.image.png')" }}>
          <div className="w-8 h-8 border-4 border-white border-t-transparent rounded-full animate-spin mb-4" />
          Loading NyayPath Case Tracker...
        </div>
      }
    >
      <TrackPageContent />
    </Suspense>
  );
}
