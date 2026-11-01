'use client';

import React, { useState, useEffect } from 'react';
import Link from 'next/link';
import { useParams, useRouter } from 'next/navigation';
import {
  ArrowLeft,
  FileText,
  Clock,
  CheckCircle2,
  AlertTriangle,
  Building,
  Calendar,
  Download,
  ExternalLink,
  ShieldCheck,
  RefreshCw,
  FolderOpen,
  User,
  HelpCircle,
  FileSearch,
  Lock,
  Eye
} from 'lucide-react';
import { getCitizenCaseDetails, getCaseDocumentUrl } from '@/lib/api';

export default function CaseDetailsPage() {
  const params = useParams();
  const router = useRouter();
  const caseId = (params?.id as string) || '';

  const [caseData, setCaseData] = useState<any>(null);
  const [timeline, setTimeline] = useState<any[]>([]);
  const [documents, setDocuments] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  // Document download state
  const [docLoadingId, setDocLoadingId] = useState<string | null>(null);
  const [docNotice, setDocNotice] = useState<{ docId: string; message: string; ttl: number } | null>(null);

  const fetchDetails = async () => {
    if (!caseId) return;
    setLoading(true);
    setError(null);
    try {
      const res = await getCitizenCaseDetails(caseId);
      setCaseData(res.case);
      setTimeline(res.timeline || []);
      setDocuments(res.documents || []);
    } catch (err: any) {
      if (err?.response?.status === 401) {
        setError('UNAUTHENTICATED');
      } else if (err?.response?.status === 403) {
        setError('FORBIDDEN');
      } else if (err?.response?.status === 404) {
        setError('NOT_FOUND');
      } else {
        setError(err?.response?.data?.detail || 'Failed to load case details.');
      }
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchDetails();
  }, [caseId]);

  const handleDocumentAccess = async (docId: string, fileName: string) => {
    setDocLoadingId(docId);
    setDocNotice(null);
    try {
      // Calls authorized FastAPI document endpoint strictly enforcing <= 300s TTL
      const res = await getCaseDocumentUrl(caseId, docId);
      if (res?.signed_url) {
        setDocNotice({
          docId,
          message: 'Secure link generated. Link expires in 5 minutes for confidentiality.',
          ttl: res.expires_in_seconds || 300
        });
        window.open(res.signed_url, '_blank', 'noopener,noreferrer');
      } else {
        alert('Unable to generate secure document URL. File may be unavailable.');
      }
    } catch (err: any) {
      alert(err?.response?.data?.detail || 'Document access denied or unavailable.');
    } finally {
      setDocLoadingId(null);
    }
  };

  const getStatusBadge = (status: string) => {
    const s = (status || 'SUBMITTED').toUpperCase();
    switch (s) {
      case 'RESOLVED':
      case 'CLOSED':
      case 'COMPLETED':
        return (
          <span className="inline-flex items-center gap-1.5 px-3 py-1 rounded-full text-xs font-bold bg-emerald-50 text-emerald-700 border border-emerald-200">
            <CheckCircle2 className="w-3.5 h-3.5" />
            <span>{s}</span>
          </span>
        );
      case 'UNDER_INQUIRY':
      case 'IN_REVIEW':
      case 'IN_PROGRESS':
        return (
          <span className="inline-flex items-center gap-1.5 px-3 py-1 rounded-full text-xs font-bold bg-blue-50 text-blue-700 border border-blue-200">
            <Clock className="w-3.5 h-3.5" />
            <span>{s}</span>
          </span>
        );
      case 'HEARING_SCHEDULED':
        return (
          <span className="inline-flex items-center gap-1.5 px-3 py-1 rounded-full text-xs font-bold bg-purple-50 text-purple-700 border border-purple-200">
            <AlertTriangle className="w-3.5 h-3.5" />
            <span>HEARING SCHEDULED</span>
          </span>
        );
      case 'ACTION_TAKEN':
        return (
          <span className="inline-flex items-center gap-1.5 px-3 py-1 rounded-full text-xs font-bold bg-teal-50 text-teal-700 border border-teal-200">
            <CheckCircle2 className="w-3.5 h-3.5" />
            <span>ACTION TAKEN</span>
          </span>
        );
      default:
        return (
          <span className="inline-flex items-center gap-1.5 px-3 py-1 rounded-full text-xs font-bold bg-amber-50 text-amber-700 border border-amber-200">
            <Clock className="w-3.5 h-3.5" />
            <span>{s}</span>
          </span>
        );
    }
  };

  return (
    <div className="min-h-screen bg-gradient-to-b from-slate-50 via-white to-slate-50 pt-20 pb-16 font-sans">
      <div className="max-w-5xl mx-auto px-4 sm:px-6 lg:px-8">

        {/* Back Navigation Bar */}
        <div className="flex items-center justify-between pb-6 border-b border-slate-200">
          <Link
            href="/dashboard/my-cases"
            className="inline-flex items-center gap-2 text-xs font-bold text-slate-600 hover:text-court-maroon transition-colors py-1.5 px-3 rounded-xl hover:bg-slate-100"
          >
            <ArrowLeft className="w-4 h-4" />
            <span>Back to My Cases</span>
          </Link>

          <button
            onClick={fetchDetails}
            disabled={loading}
            className="p-2 rounded-xl border border-slate-200 text-slate-500 hover:bg-slate-100 hover:text-slate-800 transition-colors cursor-pointer"
            title="Refresh details"
          >
            <RefreshCw className={`w-4 h-4 ${loading ? 'animate-spin' : ''}`} />
          </button>
        </div>

        {/* Loading State */}
        {loading ? (
          <div className="mt-12 p-16 rounded-3xl bg-white border border-slate-200 text-center flex flex-col items-center justify-center">
            <RefreshCw className="w-8 h-8 animate-spin text-court-maroon mb-3" />
            <h3 className="text-sm font-bold text-slate-800">Loading Case Details...</h3>
            <p className="text-xs text-slate-400 mt-1">Retrieving official case timeline and records</p>
          </div>
        ) : error ? (
          <div className="mt-12 p-8 rounded-3xl bg-white border border-slate-200 text-center">
            <div className="w-12 h-12 rounded-full bg-rose-50 text-rose-600 mx-auto flex items-center justify-center mb-3">
              <AlertTriangle className="w-6 h-6" />
            </div>
            {error === 'FORBIDDEN' ? (
              <>
                <h3 className="text-base font-bold text-slate-900">Access Denied</h3>
                <p className="text-xs text-slate-500 max-w-md mx-auto mt-1">
                  You do not have permission to view this case. Each case is strictly isolated to its authenticated filer.
                </p>
              </>
            ) : error === 'NOT_FOUND' ? (
              <>
                <h3 className="text-base font-bold text-slate-900">Case Not Found</h3>
                <p className="text-xs text-slate-500 max-w-md mx-auto mt-1">
                  No grievance or petition exists with ID <span className="font-mono font-bold">{caseId}</span>. Please verify the Case ID.
                </p>
              </>
            ) : error === 'UNAUTHENTICATED' ? (
              <>
                <h3 className="text-base font-bold text-slate-900">Authentication Required</h3>
                <p className="text-xs text-slate-500 max-w-md mx-auto mt-1">
                  Please log in to your citizen or student account to view this case.
                </p>
                <Link
                  href="/dashboard"
                  className="mt-4 inline-block px-4 py-2 rounded-xl bg-court-maroon text-white text-xs font-bold"
                >
                  Go to Dashboard Sign In
                </Link>
              </>
            ) : (
              <>
                <h3 className="text-base font-bold text-slate-900">Error Loading Case</h3>
                <p className="text-xs text-rose-600 max-w-md mx-auto mt-1">{error}</p>
              </>
            )}
            <div className="mt-4">
              <Link
                href="/dashboard/my-cases"
                className="text-xs font-bold text-court-maroon hover:underline"
              >
                Return to My Cases
              </Link>
            </div>
          </div>
        ) : caseData ? (
          <div className="mt-6 space-y-6">

            {/* Case Header Card */}
            <div className="p-6 rounded-3xl bg-white border border-slate-200 shadow-sm space-y-4">
              <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3">
                <div className="flex items-center gap-2.5 flex-wrap">
                  <span className="font-mono text-sm font-extrabold text-slate-900 bg-slate-100 px-3 py-1 rounded-lg border border-slate-200">
                    {caseData.case_id}
                  </span>
                  {getStatusBadge(caseData.status)}
                  <span className="px-3 py-1 rounded-full text-xs font-semibold bg-slate-100 text-slate-700 border border-slate-200">
                    {caseData.category || 'General Grievance'}
                  </span>
                  {caseData.severity && caseData.severity !== 'NORMAL' && (
                    <span className="px-2.5 py-1 rounded-full text-xs font-bold bg-rose-100 text-rose-800 border border-rose-200">
                      {caseData.severity}
                    </span>
                  )}
                </div>

                <div className="text-xs text-slate-500 font-medium flex items-center gap-3">
                  <span>Filed: {caseData.created_at ? new Date(caseData.created_at).toLocaleDateString() : 'N/A'}</span>
                  <span>•</span>
                  <span>Updated: {caseData.updated_at ? new Date(caseData.updated_at).toLocaleDateString() : 'N/A'}</span>
                </div>
              </div>

              <div>
                <h2 className="text-xl font-bold text-slate-900">{caseData.subject}</h2>
                <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 mt-4 pt-4 border-t border-slate-100 text-xs">
                  <div>
                    <span className="text-slate-400 block text-[11px] font-semibold">Department</span>
                    <span className="font-bold text-slate-800">{caseData.department || 'General Cell'}</span>
                  </div>
                  <div>
                    <span className="text-slate-400 block text-[11px] font-semibold">Academic Year</span>
                    <span className="font-bold text-slate-800">{caseData.year || 'N/A'}</span>
                  </div>
                  <div>
                    <span className="text-slate-400 block text-[11px] font-semibold">Institution</span>
                    <span className="font-bold text-slate-800">{caseData.institution_id || 'Campus'}</span>
                  </div>
                  <div>
                    <span className="text-slate-400 block text-[11px] font-semibold">Incident Date</span>
                    <span className="font-bold text-slate-800">{caseData.incident_date || 'N/A'}</span>
                  </div>
                </div>
              </div>
            </div>

            {/* Case Description Card */}
            <div className="p-6 rounded-3xl bg-white border border-slate-200 shadow-sm space-y-3">
              <h3 className="text-sm font-bold text-slate-900 uppercase tracking-wider flex items-center gap-2">
                <FileText className="w-4 h-4 text-court-maroon" />
                <span>Grievance Description & Facts</span>
              </h3>
              <p className="text-xs sm:text-sm text-slate-700 leading-relaxed whitespace-pre-wrap bg-slate-50 p-4 rounded-2xl border border-slate-200/70">
                {caseData.description}
              </p>
            </div>

            {/* Official Action & Resolution Card (if present) */}
            {(caseData.action_taken || caseData.resolution_details || caseData.hearing_date) && (
              <div className="p-6 rounded-3xl bg-white border border-slate-200 shadow-sm space-y-4">
                <h3 className="text-sm font-bold text-slate-900 uppercase tracking-wider flex items-center gap-2">
                  <ShieldCheck className="w-4 h-4 text-emerald-600" />
                  <span>Official Actions & Redressal Proceedings</span>
                </h3>

                <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                  {caseData.hearing_date && (
                    <div className="p-4 rounded-2xl bg-purple-50/70 border border-purple-200/80 space-y-1">
                      <span className="text-[11px] font-bold uppercase tracking-wider text-purple-700 block">
                        Hearing Schedule
                      </span>
                      <p className="text-xs font-bold text-purple-900">
                        {caseData.hearing_date}
                      </p>
                    </div>
                  )}

                  {caseData.action_taken && (
                    <div className="p-4 rounded-2xl bg-teal-50/70 border border-teal-200/80 space-y-1">
                      <span className="text-[11px] font-bold uppercase tracking-wider text-teal-700 block">
                        Action Taken by Authority
                      </span>
                      <p className="text-xs text-teal-900 leading-relaxed">
                        {caseData.action_taken}
                      </p>
                    </div>
                  )}
                </div>

                {caseData.resolution_details && (
                  <div className="p-4 rounded-2xl bg-emerald-50/70 border border-emerald-200/80 space-y-1">
                    <span className="text-[11px] font-bold uppercase tracking-wider text-emerald-700 block">
                      Formal Resolution Summary
                    </span>
                    <p className="text-xs text-emerald-900 leading-relaxed font-medium">
                      {caseData.resolution_details}
                    </p>
                  </div>
                )}
              </div>
            )}

            {/* Case Activity Progress Timeline (Task 4) */}
            <div className="p-6 rounded-3xl bg-white border border-slate-200 shadow-sm space-y-4">
              <h3 className="text-sm font-bold text-slate-900 uppercase tracking-wider flex items-center gap-2">
                <Clock className="w-4 h-4 text-court-maroon" />
                <span>Case Activity Progress Timeline</span>
              </h3>

              <div className="relative pl-6 space-y-6 before:absolute before:left-2 before:top-2 before:bottom-2 before:w-0.5 before:bg-slate-200">
                {timeline.map((event, idx) => (
                  <div key={event.id || idx} className="relative">
                    <div className="absolute -left-6 top-1 w-4 h-4 rounded-full bg-court-maroon border-2 border-white shadow-sm flex items-center justify-center" />
                    <div className="space-y-1">
                      <div className="flex items-center gap-2 flex-wrap">
                        <span className="text-xs font-bold text-slate-900">{event.title}</span>
                        {event.status && (
                          <span className="text-[10px] font-semibold px-2 py-0.5 rounded-full bg-slate-100 text-slate-600 border border-slate-200">
                            {event.status}
                          </span>
                        )}
                        <span className="text-[10px] text-slate-400">
                          {event.timestamp ? new Date(event.timestamp).toLocaleString() : ''}
                        </span>
                      </div>
                      <p className="text-xs text-slate-600 leading-relaxed">
                        {event.description}
                      </p>
                    </div>
                  </div>
                ))}
              </div>
            </div>

            {/* Supporting Documents Section (Task 5) */}
            <div className="p-6 rounded-3xl bg-white border border-slate-200 shadow-sm space-y-4">
              <div className="flex items-center justify-between">
                <h3 className="text-sm font-bold text-slate-900 uppercase tracking-wider flex items-center gap-2">
                  <FolderOpen className="w-4 h-4 text-court-maroon" />
                  <span>Supporting Documents & Official Records</span>
                </h3>
                <span className="text-xs text-slate-400 font-medium">
                  {documents.length} Attachment(s)
                </span>
              </div>

              {docNotice && (
                <div className="p-3.5 rounded-2xl bg-amber-50 border border-amber-200 text-amber-800 text-xs flex items-center gap-2">
                  <Lock className="w-4 h-4 text-amber-600 shrink-0" />
                  <span>{docNotice.message}</span>
                </div>
              )}

              {documents.length > 0 ? (
                <div className="space-y-2.5">
                  {documents.map((doc, idx) => (
                    <div
                      key={doc.id || idx}
                      className="p-3.5 rounded-2xl border border-slate-200 bg-slate-50/50 hover:bg-slate-50 transition-colors flex items-center justify-between gap-3"
                    >
                      <div className="flex items-center gap-3">
                        <div className="p-2 rounded-xl bg-white border border-slate-200 text-court-maroon">
                          <FileText className="w-4 h-4" />
                        </div>
                        <div>
                          <span className="text-xs font-bold text-slate-800 block">
                            {doc.file_name}
                          </span>
                          <span className="text-[11px] text-slate-400">
                            {doc.file_size_bytes ? `${Math.round(doc.file_size_bytes / 1024)} KB` : 'Verified attachment'} • {doc.mime_type || 'PDF Document'}
                          </span>
                        </div>
                      </div>

                      <button
                        onClick={() => handleDocumentAccess(doc.document_id || doc.id, doc.file_name)}
                        disabled={docLoadingId === (doc.document_id || doc.id)}
                        className="px-3.5 py-2 rounded-xl bg-white hover:bg-slate-100 text-slate-700 hover:text-slate-900 text-xs font-bold border border-slate-200 transition-colors flex items-center gap-1.5 cursor-pointer shadow-sm"
                      >
                        {docLoadingId === (doc.document_id || doc.id) ? (
                          <RefreshCw className="w-3.5 h-3.5 animate-spin text-court-maroon" />
                        ) : (
                          <Eye className="w-3.5 h-3.5 text-slate-500" />
                        )}
                        <span>View Document</span>
                      </button>
                    </div>
                  ))}
                </div>
              ) : (
                <div className="p-8 rounded-2xl border border-dashed border-slate-200 text-center text-slate-500 text-xs">
                  No additional supporting documents were attached to this case.
                </div>
              )}
            </div>

            {/* Assistance Card */}
            <div className="p-5 rounded-3xl bg-slate-900 text-white flex flex-col sm:flex-row items-start sm:items-center justify-between gap-4">
              <div>
                <h4 className="font-bold text-sm">Need help or want to submit an appeal?</h4>
                <p className="text-xs text-slate-300 mt-0.5">
                  NyayPath AI can draft a statutory First Appeal or clarify unresolved legal issues.
                </p>
              </div>
              <Link
                href="/dashboard?tab=assistant"
                className="px-4 py-2 rounded-xl bg-white text-slate-900 font-bold text-xs hover:bg-slate-100 transition-colors shrink-0"
              >
                Open Legal Assistant
              </Link>
            </div>

          </div>
        ) : null}

      </div>
    </div>
  );
}
