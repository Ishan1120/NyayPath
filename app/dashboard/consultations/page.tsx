'use client';

import React, { useState, useEffect } from 'react';
import Link from 'next/link';
import { useRouter } from 'next/navigation';
import {
  Scale,
  ShieldCheck,
  CheckCircle2,
  Clock,
  XCircle,
  AlertCircle,
  MessageSquare,
  FolderOpen,
  Share2,
  Lock,
  Unlock,
  RefreshCw,
  ArrowRight,
  ExternalLink,
  ChevronRight,
  UserCheck
} from 'lucide-react';
import {
  getCitizenConsultations,
  updateConsultationStatus,
  shareCaseWithLawyer,
  revokeLawyerCaseAccess,
  ConsultationRequest
} from '@/lib/api';

export default function CitizenConsultationsPage() {
  const router = useRouter();
  const [consultations, setConsultations] = useState<ConsultationRequest[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [actionSuccess, setActionSuccess] = useState<string | null>(null);

  // Sharing states map: caseId_lawyerId -> 'GRANTING' | 'REVOKING' | null
  const [actionInProgress, setActionInProgress] = useState<string | null>(null);

  const fetchConsultations = async () => {
    setLoading(true);
    setError(null);
    try {
      const res = await getCitizenConsultations();
      setConsultations(res.consultations || []);
    } catch (err: any) {
      if (err?.response?.status === 401) {
        setError('UNAUTHENTICATED');
      } else {
        setError(err?.response?.data?.detail || 'Failed to load consultation records.');
      }
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchConsultations();
  }, []);

  const handleWithdraw = async (requestId: string) => {
    if (!confirm('Are you sure you wish to withdraw this consultation inquiry?')) return;
    try {
      await updateConsultationStatus(requestId, { status: 'WITHDRAWN' });
      setActionSuccess('Consultation request withdrawn.');
      fetchConsultations();
      setTimeout(() => setActionSuccess(null), 3500);
    } catch (err: any) {
      alert(err?.response?.data?.detail || 'Failed to withdraw consultation request.');
    }
  };

  const handleGrantAccess = async (caseId: string, lawyerUserId: string, requestId: string) => {
    const key = `${caseId}_${lawyerUserId}`;
    setActionInProgress(key);
    try {
      await shareCaseWithLawyer({
        case_id: caseId,
        lawyer_user_id: lawyerUserId,
        shared_scope: 'CASE_AND_DOCS',
        consultation_request_id: requestId
      });
      setActionSuccess(`Case ${caseId} documents successfully shared with advocate.`);
      fetchConsultations();
      setTimeout(() => setActionSuccess(null), 3500);
    } catch (err: any) {
      alert(err?.response?.data?.detail || 'Failed to share case documents.');
    } finally {
      setActionInProgress(null);
    }
  };

  const handleRevokeAccess = async (caseId: string, lawyerUserId: string) => {
    if (!confirm(`Are you sure you want to revoke advocate access to Case ${caseId}? All document access will immediately terminate.`)) {
      return;
    }
    const key = `${caseId}_${lawyerUserId}`;
    setActionInProgress(key);
    try {
      await revokeLawyerCaseAccess({
        case_id: caseId,
        lawyer_user_id: lawyerUserId
      });
      setActionSuccess(`Advocate access to Case ${caseId} immediately revoked.`);
      fetchConsultations();
      setTimeout(() => setActionSuccess(null), 3500);
    } catch (err: any) {
      alert(err?.response?.data?.detail || 'Failed to revoke case access.');
    } finally {
      setActionInProgress(null);
    }
  };

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
            <span>PENDING ADVOCATE REVIEW</span>
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
            <span>CONCLUDED</span>
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
      <div className="max-w-6xl mx-auto px-4 sm:px-6">
        {/* Breadcrumb & Navigation */}
        <div className="mb-6 flex items-center justify-between text-xs text-slate-500">
          <div className="flex items-center gap-2">
            <Link href="/" className="hover:text-slate-800">Home</Link>
            <span>/</span>
            <Link href="/dashboard" className="hover:text-slate-800">Citizen Workspace</Link>
            <span>/</span>
            <span className="text-slate-700 font-semibold">Advocate Consultations</span>
          </div>
          <Link
            href="/dashboard/find-lawyer"
            className="text-court-maroon hover:underline font-semibold flex items-center gap-1"
          >
            Find an Advocate <ChevronRight size={13} />
          </Link>
        </div>

        {/* Header */}
        <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4 mb-6">
          <div>
            <div className="flex items-center gap-2 mb-1">
              <span className="inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full text-[11px] font-bold bg-slate-900 text-amber-300">
                <Scale className="w-3 h-3 text-amber-300" />
                <span>Legal Counsel Desk</span>
              </span>
            </div>
            <h1 className="text-2xl sm:text-3xl font-serif font-bold text-slate-900">
              My Advocate Consultations & Case Permissions
            </h1>
            <p className="text-xs sm:text-sm text-slate-500 mt-0.5">
              Track consultation requests, read advocate guidance, and manage explicit case document sharing.
            </p>
          </div>

          <div className="flex items-center gap-2.5 shrink-0">
            <button
              onClick={fetchConsultations}
              disabled={loading}
              className="p-2 bg-white border border-slate-200 text-slate-600 hover:text-slate-900 rounded-xl hover:bg-slate-50 transition-colors shadow-sm cursor-pointer"
              title="Refresh"
            >
              <RefreshCw className={`w-4 h-4 ${loading ? 'animate-spin' : ''}`} />
            </button>
            <Link
              href="/dashboard/find-lawyer"
              className="px-4 py-2 bg-court-maroon hover:bg-rose-700 text-white rounded-xl text-xs font-bold uppercase tracking-wider transition-all shadow-md flex items-center gap-1.5"
            >
              <Scale size={13} />
              <span>Request New Consultation</span>
            </Link>
          </div>
        </div>

        {/* Global Notifications */}
        {actionSuccess && (
          <div className="mb-6 p-4 bg-emerald-50 border border-emerald-200 rounded-xl text-xs text-emerald-800 flex items-center gap-2 animate-in fade-in">
            <CheckCircle2 className="w-4 h-4 text-emerald-600 shrink-0" />
            <span>{actionSuccess}</span>
          </div>
        )}

        {error === 'UNAUTHENTICATED' && (
          <div className="mb-6 p-6 bg-amber-50 border border-amber-200 rounded-2xl text-amber-900 text-xs">
            <div className="flex items-start gap-3">
              <AlertCircle className="w-5 h-5 text-amber-700 shrink-0 mt-0.5" />
              <div>
                <p className="font-bold">Authentication Required</p>
                <p className="mt-1 text-amber-800">
                  Please log in to your NyayPath citizen account to view your advocate consultation requests.
                </p>
                <Link
                  href="/dashboard/my-cases"
                  className="mt-3 inline-block px-4 py-1.5 bg-court-maroon text-white rounded-lg font-bold uppercase tracking-wider hover:bg-rose-700"
                >
                  Log In to Citizen Workspace
                </Link>
              </div>
            </div>
          </div>
        )}

        {/* Privileged Notice */}
        <div className="mb-6 p-4 bg-purple-50 border border-purple-200 rounded-2xl flex items-start gap-3 text-xs text-purple-900">
          <ShieldCheck className="w-5 h-5 text-purple-700 shrink-0 mt-0.5" />
          <div className="leading-relaxed">
            <p className="font-bold">Privileged & Consent-Based Document Sharing</p>
            <p className="mt-0.5 text-purple-800">
              When an advocate accepts your consultation request, you may grant them access to your NyayPath case facts and evidence documents. You retain full ownership and may revoke advocate access at any time. Institutional proctor internal notes are strictly protected and never shared.
            </p>
          </div>
        </div>

        {/* Consultations List */}
        {loading ? (
          <div className="py-20 text-center">
            <div className="w-8 h-8 border-3 border-court-maroon border-t-transparent rounded-full animate-spin mx-auto mb-3" />
            <p className="text-xs text-slate-500">Loading your consultations...</p>
          </div>
        ) : consultations.length === 0 ? (
          <div className="bg-white rounded-2xl border border-slate-200 p-12 text-center text-slate-500 shadow-sm">
            <MessageSquare className="w-10 h-10 text-slate-300 mx-auto mb-3" />
            <h3 className="font-serif font-bold text-base text-slate-700">No Consultations Yet</h3>
            <p className="text-xs text-slate-400 mt-1 max-w-sm mx-auto mb-6">
              You haven&apos;t sent any consultation requests to advocates. Search our verified directory to connect with legal counsel.
            </p>
            <Link
              href="/dashboard/find-lawyer"
              className="px-6 py-2.5 bg-court-maroon text-white rounded-xl text-xs font-bold uppercase tracking-wider hover:bg-rose-700 shadow-md inline-flex items-center gap-2"
            >
              <Scale size={14} />
              <span>Search Advocates</span>
            </Link>
          </div>
        ) : (
          <div className="space-y-4">
            {consultations.map((req) => (
              <div
                key={req.id}
                className="bg-white rounded-2xl border border-slate-200/80 shadow-sm p-5 sm:p-6 transition-all hover:border-slate-300"
              >
                <div className="flex flex-col lg:flex-row lg:items-start justify-between gap-4">
                  {/* Left Column: Lawyer & Request Details */}
                  <div className="flex-1">
                    <div className="flex flex-wrap items-center gap-2 mb-2">
                      {getStatusBadge(req.status)}
                      <span className="text-xs font-bold text-slate-900">
                        Adv. {req.lawyer?.full_name || 'Counsel'}
                      </span>
                      {req.lawyer?.enrollment_state && (
                        <span className="text-[11px] text-slate-400">
                          • {req.lawyer.enrollment_state}
                        </span>
                      )}
                      <span className="text-[11px] font-bold text-indigo-700 bg-indigo-50 border border-indigo-200/60 px-2 py-0.5 rounded-full">
                        {req.preferred_mode}
                      </span>
                      <span className="text-[11px] text-slate-400 ml-auto">
                        Requested {new Date(req.created_at).toLocaleDateString()}
                      </span>
                    </div>

                    <h3 className="text-sm font-bold text-slate-900 mb-1">
                      {req.legal_issue}
                    </h3>
                    <p className="text-xs text-slate-600 leading-relaxed mb-3 whitespace-pre-line">
                      {req.description}
                    </p>

                    {/* Linked Case Badge */}
                    {req.case_id && (
                      <div className="mb-3 p-3 bg-slate-50 border border-slate-200 rounded-xl flex flex-wrap items-center justify-between gap-3 text-xs">
                        <div className="flex items-center gap-2">
                          <FolderOpen className="w-4 h-4 text-court-maroon" />
                          <span className="text-slate-500">Linked Case:</span>
                          <span className="font-mono font-bold text-court-maroon">{req.case_id}</span>
                          <Link
                            href={`/dashboard/my-cases?case_id=${encodeURIComponent(req.case_id)}`}
                            className="text-court-maroon hover:underline font-bold text-[11px] flex items-center gap-0.5 ml-1"
                          >
                            Inspect <ExternalLink size={11} />
                          </Link>
                        </div>

                        {/* Case Sharing Controls (if Accepted) */}
                        {req.status === 'ACCEPTED' && (
                          <div className="flex items-center gap-2">
                            <button
                              onClick={() => handleGrantAccess(req.case_id!, req.lawyer_user_id, req.id)}
                              disabled={actionInProgress === `${req.case_id}_${req.lawyer_user_id}`}
                              className="px-3 py-1 bg-purple-700 hover:bg-purple-800 text-white rounded-lg text-xs font-bold uppercase transition-all flex items-center gap-1 shadow-sm cursor-pointer"
                            >
                              <Share2 size={12} />
                              <span>Authorize Document Access</span>
                            </button>
                            <button
                              onClick={() => handleRevokeAccess(req.case_id!, req.lawyer_user_id)}
                              disabled={actionInProgress === `${req.case_id}_${req.lawyer_user_id}`}
                              className="px-3 py-1 bg-slate-200 hover:bg-rose-100 hover:text-rose-700 text-slate-700 rounded-lg text-xs font-bold uppercase transition-all flex items-center gap-1 cursor-pointer"
                            >
                              <Lock size={12} />
                              <span>Revoke Access</span>
                            </button>
                          </div>
                        )}
                      </div>
                    )}

                    {/* Lawyer Response Box */}
                    {req.lawyer_response && (
                      <div className="p-3.5 bg-emerald-50/50 border border-emerald-200 rounded-xl text-xs text-slate-800 mt-2">
                        <div className="flex items-center gap-1.5 font-bold text-emerald-800 mb-1">
                          <MessageSquare className="w-3.5 h-3.5" />
                          <span>Advocate Guidance & Consultation Instructions:</span>
                        </div>
                        <p className="italic text-slate-700 leading-relaxed">&ldquo;{req.lawyer_response}&rdquo;</p>
                      </div>
                    )}
                  </div>

                  {/* Right Column: Citizen Actions */}
                  <div className="flex sm:flex-col gap-2 shrink-0 pt-2 lg:pt-0">
                    {req.status === 'PENDING' && (
                      <button
                        onClick={() => handleWithdraw(req.id)}
                        className="px-4 py-2 bg-slate-100 hover:bg-rose-50 hover:text-rose-700 text-slate-700 rounded-xl text-xs font-bold uppercase tracking-wider transition-all cursor-pointer"
                      >
                        Withdraw Request
                      </button>
                    )}

                    {req.lawyer?.id && (
                      <Link
                        href={`/lawyers/${encodeURIComponent(req.lawyer.id)}`}
                        className="px-4 py-2 bg-slate-100 hover:bg-slate-200 text-slate-700 rounded-xl text-xs font-bold uppercase tracking-wider transition-all text-center"
                      >
                        View Advocate Profile
                      </Link>
                    )}
                  </div>
                </div>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
