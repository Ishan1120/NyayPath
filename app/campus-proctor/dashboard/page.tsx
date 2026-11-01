'use client';

import React, { useState, useEffect } from 'react';
import Link from 'next/link';
import { 
  ShieldCheck, 
  Clock, 
  Calendar, 
  FileText, 
  CheckCircle2, 
  AlertTriangle, 
  Lock, 
  RefreshCw, 
  ExternalLink,
  Gavel,
  ChevronRight,
  Eye,
  FileCheck2,
  Users
} from 'lucide-react';
import Navbar from '@/app/Navbar';
import { 
  getProctorMyCases, 
  updateCampusCase, 
  getProctorNotice,
  getCaseDocumentUrl
} from '@/lib/api';

export default function ProctorDashboardWorkspace() {
  const [cases, setCases] = useState<any[]>([]);
  const [loading, setLoading] = useState<boolean>(true);
  const [selectedCase, setSelectedCase] = useState<any | null>(null);
  const [errorMsg, setErrorMsg] = useState<string | null>(null);

  // Status & Notes Action Form
  const [newStatus, setNewStatus] = useState<string>('UNDER_INQUIRY');
  const [proctorNotes, setProctorNotes] = useState<string>('');
  const [hearingDate, setHearingDate] = useState<string>('');
  const [actionTaken, setActionTaken] = useState<string>('');
  const [resolutionDetails, setResolutionDetails] = useState<string>('');
  const [actionLoading, setActionLoading] = useState<boolean>(false);

  // Formal UGC Notice Modal
  const [noticeText, setNoticeText] = useState<string | null>(null);
  const [noticeLoading, setNoticeLoading] = useState<boolean>(false);

  useEffect(() => {
    fetchMyCases();
  }, []);

  const fetchMyCases = async () => {
    setLoading(true);
    setErrorMsg(null);
    try {
      const res = await getProctorMyCases();
      setCases(res.cases || []);
    } catch (err: any) {
      console.error('Error fetching assigned cases', err);
      setErrorMsg(err.response?.data?.detail || 'Failed to load assigned grievances.');
    } finally {
      setLoading(false);
    }
  };

  const handleSelectCase = (c: any) => {
    setSelectedCase(c);
    setNewStatus(c.status || 'UNDER_INQUIRY');
    setProctorNotes(c.proctor_notes || '');
    setHearingDate(c.hearing_date || '');
    setActionTaken(c.action_taken || '');
    setResolutionDetails(c.resolution_details || '');
  };

  const handleUpdateGrievance = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!selectedCase) return;
    setActionLoading(true);
    try {
      await updateCampusCase({
        case_id: selectedCase.case_id,
        new_status: newStatus,
        proctor_notes: proctorNotes,
        hearing_date: hearingDate || undefined,
        action_taken: actionTaken || undefined,
        resolution_details: resolutionDetails || undefined
      });
      alert('Grievance investigation record updated successfully.');
      await fetchMyCases();
      setSelectedCase(null);
    } catch (err: any) {
      alert(err.response?.data?.detail || 'Failed to update grievance record');
    } finally {
      setActionLoading(false);
    }
  };

  const handleGenerateNotice = async (caseId: string) => {
    setNoticeLoading(true);
    try {
      const res = await getProctorNotice(caseId);
      setNoticeText(res.notice_text || 'Notice generated.');
    } catch (err: any) {
      alert(err.response?.data?.detail || 'Failed to generate UGC inquiry notice.');
    } finally {
      setNoticeLoading(false);
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
              <span className="p-2.5 bg-blue-50 border border-blue-100 rounded-xl text-blue-700">
                <ShieldCheck className="w-6 h-6" />
              </span>
              <div>
                <div className="flex items-center gap-2">
                  <h1 className="text-2xl font-black text-slate-900 tracking-tight">
                    Individual Proctor Investigation Desk
                  </h1>
                  <span className="text-xs font-bold px-2.5 py-0.5 rounded-full bg-blue-100 text-blue-800 border border-blue-200">
                    INQUIRY OFFICER
                  </span>
                </div>
                <p className="text-sm text-slate-500 mt-0.5">
                  Assigned Case Queue, Investigation Directives & Hearing Proceedings
                </p>
              </div>
            </div>

            <div className="flex items-center gap-2">
              <Link
                href="/campus-proctor/committee"
                className="px-3.5 py-2 text-xs font-semibold text-slate-700 bg-slate-100 hover:bg-slate-200 rounded-lg transition-colors flex items-center gap-1.5"
              >
                <Users className="w-4 h-4 text-slate-500" />
                Committee View
              </Link>
              <button
                onClick={fetchMyCases}
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
                <p className="font-semibold">Notice</p>
                <p className="text-xs text-amber-700 mt-0.5">{errorMsg}</p>
              </div>
            </div>
          )}
        </div>

        {/* Assigned Inquiries Queue */}
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-8">
          <div className="lg:col-span-1 space-y-4">
            <h2 className="text-base font-bold text-slate-900 flex items-center justify-between">
              <span>My Assigned Inquiries</span>
              <span className="text-xs font-mono px-2 py-0.5 rounded-full bg-slate-100 text-slate-700">
                {cases.length} Active
              </span>
            </h2>

            {loading ? (
              <div className="py-12 text-center text-slate-400 text-sm bg-white rounded-2xl border border-slate-200">
                Loading assigned cases...
              </div>
            ) : cases.length === 0 ? (
              <div className="py-12 text-center text-slate-500 text-sm bg-white rounded-2xl border border-slate-200 p-6">
                No cases currently assigned to you for investigation.
              </div>
            ) : (
              <div className="space-y-3">
                {cases.map((c) => (
                  <div
                    key={c.case_id}
                    onClick={() => handleSelectCase(c)}
                    className={`p-4 rounded-xl border transition-all cursor-pointer ${
                      selectedCase?.case_id === c.case_id
                        ? 'bg-blue-50/60 border-blue-300 ring-2 ring-blue-100 shadow-sm'
                        : 'bg-white border-slate-200 hover:border-slate-300 hover:bg-slate-50/50'
                    }`}
                  >
                    <div className="flex items-center justify-between text-xs mb-1">
                      <span className="font-mono font-bold text-blue-700">{c.case_id}</span>
                      <span className={`px-2 py-0.5 rounded-full font-bold text-[10px] ${
                        c.status === 'RESOLVED' || c.status === 'CLOSED' ? 'bg-emerald-100 text-emerald-800' :
                        c.status === 'HEARING_SCHEDULED' ? 'bg-purple-100 text-purple-800' :
                        'bg-blue-100 text-blue-800'
                      }`}>
                        {c.status}
                      </span>
                    </div>
                    <div className="font-semibold text-slate-900 text-sm truncate">{c.subject}</div>
                    <div className="text-xs text-slate-500 mt-1 flex items-center justify-between">
                      <span>{c.is_anonymous ? 'Protected Student' : c.student_name}</span>
                      <span className="text-[11px] text-slate-400">
                        {c.created_at ? new Date(c.created_at).toLocaleDateString() : ''}
                      </span>
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>

          {/* Investigation Workbench */}
          <div className="lg:col-span-2">
            {selectedCase ? (
              <div className="bg-white border border-slate-200 rounded-2xl p-6 shadow-sm space-y-6">
                <div className="flex items-start justify-between border-b border-slate-100 pb-4">
                  <div>
                    <span className="text-xs font-mono font-bold text-blue-700">{selectedCase.case_id}</span>
                    <h3 className="text-xl font-bold text-slate-900 mt-0.5">{selectedCase.subject}</h3>
                    <div className="flex items-center gap-3 text-xs text-slate-500 mt-1">
                      <span>Category: <strong className="text-slate-700">{selectedCase.category}</strong></span>
                      <span>•</span>
                      <span>Severity: <strong className="text-slate-700">{selectedCase.severity}</strong></span>
                      <span>•</span>
                      <span>
                        Complainant: <strong className="text-slate-700">
                          {selectedCase.is_anonymous ? 'Anonymous Complainant' : selectedCase.student_name}
                        </strong>
                      </span>
                    </div>
                  </div>

                  <button
                    onClick={() => handleGenerateNotice(selectedCase.case_id)}
                    className="px-3 py-1.5 bg-slate-100 hover:bg-slate-200 text-slate-700 text-xs font-bold rounded-lg flex items-center gap-1.5 transition-colors cursor-pointer"
                  >
                    <FileText className="w-3.5 h-3.5" />
                    Formal UGC Notice
                  </button>
                </div>

                {/* Grievance Facts */}
                <div className="p-4 bg-slate-50 rounded-xl">
                  <h4 className="text-xs font-bold text-slate-700 uppercase tracking-wide mb-1.5">Grievance Facts</h4>
                  <p className="text-xs text-slate-700 leading-relaxed whitespace-pre-line">
                    {selectedCase.description || 'No grievance facts entered.'}
                  </p>
                </div>

                {/* Supporting Documents */}
                {selectedCase.supporting_documents && selectedCase.supporting_documents.length > 0 && (
                  <div>
                    <h4 className="text-xs font-bold text-slate-700 uppercase tracking-wide mb-2">Supporting Case Documents</h4>
                    <div className="space-y-2">
                      {selectedCase.supporting_documents.map((doc: any, i: number) => (
                        <div key={i} className="flex items-center justify-between p-2.5 bg-slate-50 border border-slate-200 rounded-xl text-xs">
                          <span className="font-mono text-slate-700 truncate">{doc.file_name || doc.name || `Attachment ${i+1}`}</span>
                          <button
                            onClick={() => handleDownloadDoc(selectedCase.case_id, doc.document_id || doc.id || i.toString())}
                            className="px-2.5 py-1 bg-blue-50 text-blue-700 hover:bg-blue-100 rounded text-xs font-bold flex items-center gap-1 cursor-pointer"
                          >
                            <ExternalLink className="w-3 h-3" /> Inspect Document
                          </button>
                        </div>
                      ))}
                    </div>
                  </div>
                )}

                {/* Status Transition & Investigation Form */}
                <form onSubmit={handleUpdateGrievance} className="space-y-4 pt-4 border-t border-slate-100 text-xs">
                  <h4 className="text-sm font-bold text-slate-900 uppercase tracking-wide">
                    Record Investigation Findings & Transition Workflow
                  </h4>

                  <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                    <div>
                      <label className="font-bold text-slate-700 block mb-1">Workflow Status</label>
                      <select
                        value={newStatus}
                        onChange={(e) => setNewStatus(e.target.value)}
                        className="w-full p-2.5 border border-slate-200 rounded-xl bg-white font-semibold"
                      >
                        <option value="UNDER_INQUIRY">UNDER_INQUIRY</option>
                        <option value="HEARING_SCHEDULED">HEARING_SCHEDULED</option>
                        <option value="ACTION_TAKEN">ACTION_TAKEN</option>
                        <option value="RESOLVED">RESOLVED</option>
                        <option value="CLOSED">CLOSED</option>
                      </select>
                    </div>

                    <div>
                      <label className="font-bold text-slate-700 block mb-1">Hearing Date</label>
                      <input
                        type="date"
                        value={hearingDate}
                        onChange={(e) => setHearingDate(e.target.value)}
                        className="w-full p-2.5 border border-slate-200 rounded-xl"
                      />
                    </div>
                  </div>

                  <div>
                    <label className="font-bold text-slate-700 block mb-1">Proctor Investigation Notes</label>
                    <textarea
                      rows={3}
                      value={proctorNotes}
                      onChange={(e) => setProctorNotes(e.target.value)}
                      placeholder="Enter investigation observations, statements recorded, or inquiry summaries..."
                      className="w-full p-2.5 border border-slate-200 rounded-xl"
                    />
                  </div>

                  <div>
                    <label className="font-bold text-slate-700 block mb-1">Institutional Action Taken</label>
                    <textarea
                      rows={2}
                      value={actionTaken}
                      onChange={(e) => setActionTaken(e.target.value)}
                      placeholder="Disciplinary action, warning issued, hostel reassignment, administrative remedy..."
                      className="w-full p-2.5 border border-slate-200 rounded-xl"
                    />
                  </div>

                  {newStatus === 'RESOLVED' && (
                    <div>
                      <label className="font-bold text-emerald-800 block mb-1">Resolution Summary</label>
                      <textarea
                        rows={2}
                        value={resolutionDetails}
                        onChange={(e) => setResolutionDetails(e.target.value)}
                        placeholder="Formal resolution terms and closing declaration..."
                        className="w-full p-2.5 border border-emerald-200 bg-emerald-50/40 rounded-xl"
                      />
                    </div>
                  )}

                  <div className="flex items-center justify-between pt-2">
                    <span className="text-[11px] text-slate-400 italic">
                      * Proctor reassignment & confidentiality scoping are managed by the Chief Proctor.
                    </span>
                    <button
                      type="submit"
                      disabled={actionLoading}
                      className="px-5 py-2.5 bg-blue-600 hover:bg-blue-700 text-white font-bold rounded-xl transition-colors cursor-pointer disabled:opacity-50"
                    >
                      {actionLoading ? 'Saving...' : 'Update Investigation Record'}
                    </button>
                  </div>
                </form>
              </div>
            ) : (
              <div className="h-full min-h-[400px] flex flex-col items-center justify-center p-8 bg-white border border-slate-200 rounded-2xl text-center text-slate-400">
                <FileText className="w-12 h-12 text-slate-300 mb-3" />
                <p className="font-bold text-slate-600">Select an Inquiry Case to Begin Review</p>
                <p className="text-xs text-slate-400 mt-1 max-w-sm">
                  Choose any assigned case from the queue to inspect complainant statements, record proctor findings, and schedule hearings.
                </p>
              </div>
            )}
          </div>
        </div>
      </main>

      {/* UGC Notice Modal */}
      {noticeText && (
        <div className="fixed inset-0 z-50 bg-slate-900/40 backdrop-blur-sm flex items-center justify-center p-4">
          <div className="bg-white rounded-2xl max-w-2xl w-full p-6 shadow-xl border border-slate-200 max-h-[85vh] flex flex-col">
            <div className="flex justify-between items-center pb-3 border-b border-slate-100">
              <h3 className="font-bold text-slate-900">Official Proctorial Inquiry Notice</h3>
              <button onClick={() => setNoticeText(null)} className="text-slate-400 hover:text-slate-600 font-bold cursor-pointer">
                ✕
              </button>
            </div>
            <pre className="p-4 bg-slate-50 border border-slate-200 rounded-xl font-mono text-xs text-slate-800 whitespace-pre-wrap flex-1 overflow-y-auto my-4">
              {noticeText}
            </pre>
            <div className="flex justify-end gap-2">
              <button
                onClick={() => setNoticeText(null)}
                className="px-4 py-2 bg-slate-100 hover:bg-slate-200 text-slate-700 font-bold text-xs rounded-xl cursor-pointer"
              >
                Close
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

