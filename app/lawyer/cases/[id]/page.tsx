'use client';

import React, { useState, useEffect, use } from 'react';
import Link from 'next/link';
import { useRouter } from 'next/navigation';
import {
  Scale,
  ShieldAlert,
  ShieldCheck,
  Clock,
  ArrowLeft,
  Sparkles,
  AlertTriangle,
  FileText,
  Calendar,
  CheckCircle2,
  RefreshCw,
  HelpCircle,
  ExternalLink,
  ChevronRight
} from 'lucide-react';
import { getLawyerCaseTimeline, getLawyerCaseAiSummary } from '@/lib/api';

export default function LawyerCaseDossierPage({ params }: { params: Promise<{ id: string }> }) {
  const router = useRouter();
  const resolvedParams = use(params);
  const caseId = decodeURIComponent(resolvedParams.id);

  const [loading, setLoading] = useState(true);
  const [timelineData, setTimelineData] = useState<any>(null);
  const [error, setError] = useState<string | null>(null);

  // AI Assistant states
  const [generatingAi, setGeneratingAi] = useState(false);
  const [aiSummary, setAiSummary] = useState<any>(null);
  const [aiError, setAiError] = useState<string | null>(null);

  const fetchTimeline = async () => {
    setLoading(true);
    setError(null);
    try {
      const data = await getLawyerCaseTimeline(caseId);
      setTimelineData(data);
    } catch (err: any) {
      console.error('Failed to load case timeline:', err);
      setError(
        err?.response?.data?.detail ||
        err?.message ||
        'Access denied: You do not have active authorized access to this complaint.'
      );
    } finally {
      setLoading(false);
    }
  };

  const handleGenerateAiSummary = async () => {
    setGeneratingAi(true);
    setAiError(null);
    try {
      const data = await getLawyerCaseAiSummary(caseId);
      setAiSummary(data);
    } catch (err: any) {
      console.error('Failed to generate AI summary:', err);
      setAiError(
        err?.response?.data?.detail ||
        err?.message ||
        'Failed to generate AI case summary.'
      );
    } finally {
      setGeneratingAi(false);
    }
  };

  useEffect(() => {
    if (caseId) {
      fetchTimeline();
    }
  }, [caseId]);

  return (
    <div className="min-h-screen bg-slate-50 font-sans text-slate-800 pb-20">
      {/* Top Header */}
      <header className="bg-white border-b border-slate-200 sticky top-0 z-30">
        <div className="max-w-6xl mx-auto px-4 sm:px-6 py-4 flex items-center justify-between">
          <div className="flex items-center gap-3">
            <Link
              href="/lawyer/dashboard"
              className="p-2 rounded-lg hover:bg-slate-100 text-slate-600 transition"
              title="Return to Dashboard"
            >
              <ArrowLeft size={18} />
            </Link>
            <div>
              <div className="flex items-center gap-2">
                <span className="font-mono text-xs font-bold px-2 py-0.5 rounded bg-rose-50 text-court-maroon border border-rose-200">
                  #{caseId}
                </span>
                <span className="text-xs px-2.5 py-0.5 rounded-full bg-slate-100 text-slate-700 font-semibold uppercase">
                  {timelineData?.category || 'Complaint Matter'}
                </span>
                {timelineData?.shared_scope && (
                  <span className="text-xs px-2.5 py-0.5 rounded-full bg-emerald-50 text-emerald-800 border border-emerald-200 font-medium">
                    Consent Scope: {timelineData.shared_scope}
                  </span>
                )}
              </div>
              <h1 className="text-base font-bold text-slate-900 mt-0.5">
                Authorized Complaint Dossier & Chronology
              </h1>
            </div>
          </div>

          <div className="flex items-center gap-2">
            <button
              onClick={fetchTimeline}
              disabled={loading}
              className="p-2 rounded-lg border border-slate-200 hover:bg-slate-50 text-slate-600 transition text-xs flex items-center gap-1.5"
            >
              <RefreshCw size={13} className={loading ? 'animate-spin' : ''} />
              <span className="hidden sm:inline">Refresh</span>
            </button>
            <button
              onClick={handleGenerateAiSummary}
              disabled={generatingAi || loading || !timelineData}
              className="px-3.5 py-2 rounded-xl bg-gradient-to-r from-court-maroon to-slate-900 text-amber-300 hover:text-white font-bold text-xs shadow-sm flex items-center gap-1.5 transition cursor-pointer disabled:opacity-50"
            >
              <Sparkles size={14} className="text-amber-400" />
              <span>{generatingAi ? 'Analyzing Record...' : 'AI Case Assistant'}</span>
            </button>
          </div>
        </div>
      </header>

      <main className="max-w-6xl mx-auto px-4 sm:px-6 pt-6 space-y-6">
        {/* Error Notification */}
        {error && (
          <div className="p-4 rounded-2xl bg-rose-50 border border-rose-200 text-rose-900 flex items-start gap-3">
            <ShieldAlert size={20} className="text-court-maroon shrink-0 mt-0.5" />
            <div>
              <h3 className="font-bold text-sm">Access Denied or Record Inaccessible</h3>
              <p className="text-xs text-rose-800 mt-0.5">{error}</p>
              <p className="text-xs text-rose-700 mt-2 font-medium">
                Under NyayPath privacy safeguards, counsel may only inspect complaint history if the citizen has granted an active, unrevoked consent record with CASE_AND_DOCS or FULL scope.
              </p>
            </div>
          </div>
        )}

        {/* Loading Spinner */}
        {loading && (
          <div className="py-20 text-center">
            <RefreshCw size={24} className="animate-spin text-slate-400 mx-auto mb-3" />
            <p className="text-xs text-slate-500 font-medium">Loading verified complaint records & chronology...</p>
          </div>
        )}

        {/* AI Case Intelligence Summary Box */}
        {aiSummary && (
          <div className="bg-gradient-to-br from-slate-900 to-court-maroon text-slate-100 rounded-3xl p-6 shadow-xl border border-slate-800 space-y-4">
            <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2 border-b border-white/10 pb-3">
              <div className="flex items-center gap-2">
                <Sparkles size={16} className="text-amber-400" />
                <h3 className="font-bold text-sm text-amber-200 uppercase tracking-wide">
                  Grounded AI Case Intelligence Summary
                </h3>
              </div>
              <span className="text-[11px] font-mono text-slate-300 bg-white/10 px-2 py-0.5 rounded">
                Grounded in {aiSummary.verified_timeline_event_count} Verified Events
              </span>
            </div>

            <p className="text-xs sm:text-sm text-slate-200 leading-relaxed font-sans">
              {aiSummary.summary}
            </p>

            {/* Key Developments linked to event IDs */}
            {aiSummary.key_developments?.length > 0 && (
              <div className="space-y-2 pt-2">
                <h4 className="text-xs font-bold text-amber-300 uppercase tracking-wider">
                  Key Timeline Developments (Linked to Source Records):
                </h4>
                <div className="grid grid-cols-1 md:grid-cols-2 gap-2.5">
                  {aiSummary.key_developments.map((kd: any, idx: number) => (
                    <a
                      key={idx}
                      href={`#${kd.nav_target_id || `timeline-event-${kd.source_event_id}`}`}
                      className="block bg-white/5 hover:bg-white/10 border border-white/10 hover:border-amber-400/40 rounded-xl p-3 text-xs transition cursor-pointer group/kd"
                      title="Click to view verified source milestone in timeline below"
                    >
                      <div className="flex items-center justify-between mb-1">
                        <span className="font-bold text-slate-100 group-hover/kd:text-amber-300 transition">{kd.title}</span>
                        <span className="text-[10px] font-mono text-amber-400">
                          {kd.date ? new Date(kd.date).toLocaleDateString() : 'Recorded'}
                        </span>
                      </div>
                      <p className="text-[11px] text-slate-300 leading-relaxed">{kd.summary}</p>
                      <div className="flex items-center justify-between mt-1 text-[9px] font-mono text-slate-400">
                        <span>Source Event ID: #{kd.source_event_id} ({kd.source_record})</span>
                        <span className="text-amber-400 opacity-80 group-hover/kd:opacity-100 flex items-center gap-0.5">
                          View in timeline &darr;
                        </span>
                      </div>
                    </a>
                  ))}
                </div>
              </div>
            )}

            {/* Counsel Investigation Checklist */}
            {aiSummary.investigation_questions?.length > 0 && (
              <div className="bg-white/10 rounded-xl p-3.5 space-y-2 text-xs">
                <h4 className="font-bold text-amber-300 flex items-center gap-1.5">
                  <HelpCircle size={13} />
                  <span>Recommended Questions for Client Consultation:</span>
                </h4>
                <ul className="list-disc list-inside space-y-1 text-slate-200 text-[11px]">
                  {aiSummary.investigation_questions.map((q: string, i: number) => (
                    <li key={i}>{q}</li>
                  ))}
                </ul>
              </div>
            )}

            <div className="pt-2 text-[10px] text-slate-400 flex items-center gap-1 border-t border-white/10">
              <ShieldCheck size={12} className="text-emerald-400" />
              <span>{aiSummary.disclaimer}</span>
            </div>
          </div>
        )}

        {/* Timeline Historical Gaps Warning */}
        {timelineData?.timeline_gaps?.length > 0 && (
          <div className="p-4 rounded-2xl bg-amber-50 border border-amber-200 text-amber-900 flex items-start gap-3">
            <AlertTriangle size={18} className="text-amber-600 shrink-0 mt-0.5" />
            <div className="text-xs">
              <span className="font-bold">Historical Record Notice:</span>
              <ul className="list-disc list-inside mt-1 space-y-0.5 text-amber-800">
                {timelineData.timeline_gaps.map((gap: string, i: number) => (
                  <li key={i}>{gap}</li>
                ))}
              </ul>
            </div>
          </div>
        )}

        {/* Timeline Events View */}
        {timelineData && (
          <div className="bg-white rounded-3xl border border-slate-200 p-6 shadow-sm space-y-6">
            <div className="flex items-center justify-between border-b border-slate-100 pb-4">
              <div>
                <h2 className="text-sm font-bold text-slate-900">
                  Verified Chronological Event History ({timelineData.total_events} Milestones)
                </h2>
                <p className="text-xs text-slate-500 mt-0.5">
                  Chronological trail from initial submission to current status. Internal proctor notes and secret verification hashes are excluded under privacy constraints.
                </p>
              </div>
            </div>

            <div className="relative pl-6 space-y-6 before:absolute before:left-2.5 before:top-3 before:bottom-3 before:w-0.5 before:bg-slate-200">
              {timelineData.events?.map((ev: any, idx: number) => (
                <div
                  key={ev.event_id || idx}
                  id={`timeline-event-${ev.event_id}`}
                  className="relative group scroll-mt-24"
                >
                  <div className="absolute -left-[19px] top-1.5 w-3 h-3 rounded-full bg-court-maroon ring-4 ring-white" />
                  <div className="bg-slate-50 rounded-2xl p-4 border border-slate-200 hover:border-slate-300 transition">
                    <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-1 mb-1.5">
                      <div className="flex items-center gap-2">
                        <span className="font-bold text-xs text-slate-900">{ev.title}</span>
                        <span className="text-[10px] font-mono px-2 py-0.5 rounded bg-slate-200 text-slate-700">
                          {ev.event_type}
                        </span>
                      </div>
                      <span className="text-[11px] font-mono text-slate-400">
                        {ev.timestamp ? new Date(ev.timestamp).toLocaleString() : 'Date N/A'}
                      </span>
                    </div>

                    <p className="text-xs text-slate-600 leading-relaxed">
                      {typeof ev.details === 'object' ? JSON.stringify(ev.details) : ev.details}
                    </p>

                    <div className="mt-2 text-[10px] text-slate-400 font-mono">
                      Event ID: #{ev.event_id} | Source: {ev.source}
                    </div>
                  </div>
                </div>
              ))}
            </div>
          </div>
        )}
      </main>
    </div>
  );
}

