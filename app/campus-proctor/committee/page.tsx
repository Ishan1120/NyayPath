'use client';

import React, { useState, useEffect } from 'react';
import Link from 'next/link';
import { 
  Users, 
  ShieldCheck, 
  FileText, 
  Clock, 
  Calendar, 
  AlertTriangle, 
  CheckCircle2, 
  RefreshCw, 
  ExternalLink,
  Lock,
  ChevronRight,
  Send,
  Building
} from 'lucide-react';
import Navbar from '@/app/Navbar';
import { 
  getCommitteeInquiries, 
  submitCommitteeObservations, 
  getCaseDocumentUrl 
} from '@/lib/api';

export default function CommitteeWorkspace() {
  const [inquiries, setInquiries] = useState<any[]>([]);
  const [loading, setLoading] = useState<boolean>(true);
  const [selectedCase, setSelectedCase] = useState<any | null>(null);
  const [errorMsg, setErrorMsg] = useState<string | null>(null);

  // Observations Form State
  const [observations, setObservations] = useState<string>('');
  const [findings, setFindings] = useState<string>('');
  const [recommendations, setRecommendations] = useState<string>('');
  const [submitting, setSubmitting] = useState<boolean>(false);
  const [successMsg, setSuccessMsg] = useState<string | null>(null);

  useEffect(() => {
    fetchInquiries();
  }, []);

  const fetchInquiries = async () => {
    setLoading(true);
    setErrorMsg(null);
    try {
      const res = await getCommitteeInquiries();
      setInquiries(res.inquiries || []);
    } catch (err: any) {
      console.error('Failed to load committee inquiries', err);
      setErrorMsg(err.response?.data?.detail || 'Access denied: You do not have active committee inquiries or your account is suspended.');
    } finally {
      setLoading(false);
    }
  };

  const handleSelectCase = (c: any) => {
    setSelectedCase(c);
    setObservations('');
    setFindings('');
    setRecommendations('');
    setSuccessMsg(null);
  };

  const handleSubmitObservations = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!selectedCase || !observations.trim()) return;
    setSubmitting(true);
    setSuccessMsg(null);
    try {
      await submitCommitteeObservations({
        case_id: selectedCase.case_id,
        observations: observations.trim(),
        findings: findings.trim(),
        recommendations: recommendations.trim()
      });
      setSuccessMsg('Committee observations and findings recorded successfully.');
      setObservations('');
      setFindings('');
      setRecommendations('');
    } catch (err: any) {
      alert(err.response?.data?.detail || 'Failed to submit committee observations');
    } finally {
      setSubmitting(false);
    }
  };

  const handleDownloadDoc = async (caseId: string, docId: string) => {
    try {
      const res = await getCaseDocumentUrl(caseId, docId);
      if (res.signed_url) {
        window.open(res.signed_url, '_blank');
      }
    } catch (err: any) {
      alert(err.response?.data?.detail || 'Document access denied or expired.');
    }
  };

  return (
    <div className="min-h-screen bg-slate-50 text-slate-900">
      <Navbar />

      <main className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 pt-24 pb-16">
        {/* Banner */}
        <div className="bg-white border border-slate-200 rounded-2xl p-6 sm:p-8 shadow-sm mb-8">
          <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
            <div className="flex items-center gap-3">
              <span className="p-2.5 bg-purple-50 border border-purple-100 rounded-xl text-purple-700">
                <Users className="w-6 h-6" />
              </span>
              <div>
                <div className="flex items-center gap-2">
                  <h1 className="text-2xl font-black text-slate-900 tracking-tight">
                    Inquiry Committee Member Workspace
                  </h1>
                  <span className="text-xs font-bold px-2.5 py-0.5 rounded-full bg-purple-100 text-purple-800 border border-purple-200">
                    COMMITTEE MEMBER
                  </span>
                </div>
                <p className="text-sm text-slate-500 mt-0.5">
                  Assigned Confidential Inquiries, Evidence Review & Joint Committee Findings
                </p>
              </div>
            </div>

            <div className="flex items-center gap-2">
              <Link
                href="/campus-proctor/dashboard"
                className="px-3.5 py-2 text-xs font-semibold text-slate-700 bg-slate-100 hover:bg-slate-200 rounded-lg transition-colors flex items-center gap-1.5"
              >
                <ShieldCheck className="w-4 h-4 text-slate-500" />
                Proctor Desk
              </Link>
              <button
                onClick={fetchInquiries}
                className="px-3.5 py-2 text-xs font-semibold text-slate-700 bg-white hover:bg-slate-50 border border-slate-200 rounded-lg transition-colors flex items-center gap-1.5 cursor-pointer shadow-sm"
              >
                <RefreshCw className="w-3.5 h-3.5 text-slate-500" />
                Refresh
              </button>
            </div>
          </div>

          {errorMsg && (
            <div className="mt-4 p-4 rounded-xl bg-amber-50 border border-amber-200 text-amber-800 text-sm flex items-start gap-3">
              <AlertTriangle className="w-5 h-5 text-amber-600 shrink-0 mt-0.5" />
              <div>
                <p className="font-semibold">Access Restriction Notice</p>
                <p className="text-xs text-amber-700 mt-0.5">{errorMsg}</p>
              </div>
            </div>
          )}
        </div>

        {/* Content Layout */}
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-8">
          {/* Active Committee Assignments */}
          <div className="lg:col-span-1 space-y-4">
            <h2 className="text-base font-bold text-slate-900 flex items-center justify-between">
              <span>My Committee Inquiries</span>
              <span className="text-xs font-mono px-2 py-0.5 rounded-full bg-purple-100 text-purple-800">
                {inquiries.length} Active
              </span>
            </h2>

            {loading ? (
              <div className="py-12 text-center text-slate-400 text-sm bg-white rounded-2xl border border-slate-200">
                Loading assigned committee inquiries...
              </div>
            ) : inquiries.length === 0 ? (
              <div className="py-12 text-center text-slate-500 text-sm bg-white rounded-2xl border border-slate-200 p-6">
                No active committee inquiries currently assigned to you.
              </div>
            ) : (
              <div className="space-y-3">
                {inquiries.map((c) => (
                  <div
                    key={c.case_id}
                    onClick={() => handleSelectCase(c)}
                    className={`p-4 rounded-xl border transition-all cursor-pointer ${
                      selectedCase?.case_id === c.case_id
                        ? 'bg-purple-50/60 border-purple-300 ring-2 ring-purple-100 shadow-sm'
                        : 'bg-white border-slate-200 hover:border-slate-300 hover:bg-slate-50/50'
                    }`}
                  >
                    <div className="flex items-center justify-between text-xs mb-1">
                      <span className="font-mono font-bold text-purple-700">{c.case_id}</span>
                      <span className="text-[10px] font-bold px-2 py-0.5 rounded-full bg-purple-100 text-purple-800">
                        {c.committee_role?.toUpperCase() || 'MEMBER'}
                      </span>
                    </div>
                    <div className="font-semibold text-slate-900 text-sm truncate">{c.subject}</div>
                    <div className="text-xs text-slate-500 mt-1 flex items-center justify-between">
                      <span className="font-mono text-[11px]">{c.committee_name || 'Inquiry Board'}</span>
                      <span className="text-[11px] text-slate-400">
                        {c.created_at ? new Date(c.created_at).toLocaleDateString() : ''}
                      </span>
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>

          {/* Committee Workbench & Observations */}
          <div className="lg:col-span-2">
            {selectedCase ? (
              <div className="bg-white border border-slate-200 rounded-2xl p-6 shadow-sm space-y-6">
                <div className="flex items-start justify-between border-b border-slate-100 pb-4">
                  <div>
                    <span className="text-xs font-mono font-bold text-purple-700">{selectedCase.case_id}</span>
                    <h3 className="text-xl font-bold text-slate-900 mt-0.5">{selectedCase.subject}</h3>
                    <div className="flex items-center gap-3 text-xs text-slate-500 mt-1">
                      <span>Category: <strong className="text-slate-700">{selectedCase.category}</strong></span>
                      <span>•</span>
                      <span>Severity: <strong className="text-slate-700">{selectedCase.severity}</strong></span>
                      <span>•</span>
                      <span>
                        Complainant: <strong className="text-slate-700">
                          {selectedCase.is_anonymous ? 'Protected Student' : selectedCase.student_name}
                        </strong>
                      </span>
                    </div>
                  </div>

                  <span className="text-xs font-bold px-2.5 py-1 rounded-full bg-slate-100 text-slate-700">
                    {selectedCase.status}
                  </span>
                </div>

                {/* Grievance Facts */}
                <div className="p-4 bg-slate-50 rounded-xl">
                  <h4 className="text-xs font-bold text-slate-700 uppercase tracking-wide mb-1">Inquiry Case Particulars</h4>
                  <p className="text-xs text-slate-700 leading-relaxed whitespace-pre-line">
                    {selectedCase.description || 'No particulars entered.'}
                  </p>
                </div>

                {/* Confidential Evidence Documents */}
                {selectedCase.supporting_documents && selectedCase.supporting_documents.length > 0 && (
                  <div>
                    <h4 className="text-xs font-bold text-slate-700 uppercase tracking-wide mb-2">Confidential Case Evidence</h4>
                    <div className="space-y-2">
                      {selectedCase.supporting_documents.map((doc: any, i: number) => (
                        <div key={i} className="flex items-center justify-between p-2.5 bg-slate-50 border border-slate-200 rounded-xl text-xs">
                          <span className="font-mono text-slate-700 truncate">{doc.file_name || doc.name || `Attachment ${i+1}`}</span>
                          <button
                            onClick={() => handleDownloadDoc(selectedCase.case_id, doc.document_id || doc.id || i.toString())}
                            className="px-2.5 py-1 bg-purple-50 text-purple-700 hover:bg-purple-100 rounded text-xs font-bold flex items-center gap-1 cursor-pointer"
                          >
                            <ExternalLink className="w-3 h-3" /> Authorised Review
                          </button>
                        </div>
                      ))}
                    </div>
                  </div>
                )}

                {/* Submit Committee Findings */}
                <form onSubmit={handleSubmitObservations} className="space-y-4 pt-4 border-t border-slate-100 text-xs">
                  <h4 className="text-sm font-bold text-slate-900 uppercase tracking-wide">
                    Record Committee Observations & Joint Findings
                  </h4>

                  {successMsg && (
                    <div className="p-3 bg-emerald-50 border border-emerald-200 text-emerald-800 rounded-xl text-xs font-medium flex items-center gap-2">
                      <CheckCircle2 className="w-4 h-4 text-emerald-600" />
                      {successMsg}
                    </div>
                  )}

                  <div>
                    <label className="font-bold text-slate-700 block mb-1">Committee Observations (Required)</label>
                    <textarea
                      required
                      rows={3}
                      value={observations}
                      onChange={(e) => setObservations(e.target.value)}
                      placeholder="Enter committee inquiry observations, witness statements, or corroborating facts..."
                      className="w-full p-2.5 border border-slate-200 rounded-xl"
                    />
                  </div>

                  <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                    <div>
                      <label className="font-bold text-slate-700 block mb-1">Key Findings</label>
                      <textarea
                        rows={3}
                        value={findings}
                        onChange={(e) => setFindings(e.target.value)}
                        placeholder="Inquiry findings regarding culpability, breach of conduct, or mitigating factors..."
                        className="w-full p-2.5 border border-slate-200 rounded-xl"
                      />
                    </div>

                    <div>
                      <label className="font-bold text-slate-700 block mb-1">Recommendations to Chief Proctor</label>
                      <textarea
                        rows={3}
                        value={recommendations}
                        onChange={(e) => setRecommendations(e.target.value)}
                        placeholder="Proposed institutional remedies, disciplinary penalties, or counseling directives..."
                        className="w-full p-2.5 border border-slate-200 rounded-xl"
                      />
                    </div>
                  </div>

                  <div className="flex justify-end pt-2">
                    <button
                      type="submit"
                      disabled={submitting || !observations.trim()}
                      className="px-5 py-2.5 bg-purple-600 hover:bg-purple-700 text-white font-bold rounded-xl transition-colors cursor-pointer disabled:opacity-50 flex items-center gap-1.5"
                    >
                      <Send className="w-3.5 h-3.5" />
                      {submitting ? 'Submitting...' : 'Record Committee Findings'}
                    </button>
                  </div>
                </form>
              </div>
            ) : (
              <div className="h-full min-h-[400px] flex flex-col items-center justify-center p-8 bg-white border border-slate-200 rounded-2xl text-center text-slate-400">
                <Users className="w-12 h-12 text-slate-300 mb-3" />
                <p className="font-bold text-slate-600">Select an Inquiry Case to Participate</p>
                <p className="text-xs text-slate-400 mt-1 max-w-sm">
                  View assigned confidential evidence, inspect grievance facts, and submit observations and recommendations to the Chief Proctor.
                </p>
              </div>
            )}
          </div>
        </div>
      </main>
    </div>
  );
}

