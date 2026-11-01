'use client';

import React, { useState, useEffect } from 'react';
import {
  Gavel,
  Search,
  Filter,
  RefreshCw,
  AlertTriangle,
  CheckCircle2,
  Clock,
  ShieldCheck,
  ChevronLeft,
  ChevronRight,
  Eye,
  X,
  UserCheck,
  UserX,
  FileText
} from 'lucide-react';
import AdminLayout from '../AdminLayout';
import {
  getPlatformLawyerQueue,
  processPlatformLawyerDecision
} from '@/lib/api';

export default function AdminLawyersPage() {
  const [lawyers, setLawyers] = useState<any[]>([]);
  const [total, setTotal] = useState<number>(0);
  const [loading, setLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);

  // Filters
  const [statusFilter, setStatusFilter] = useState<string>('PENDING');
  const [currentPage, setCurrentPage] = useState<number>(1);
  const pageSize = 15;

  // Decision Modal
  const [selectedLawyer, setSelectedLawyer] = useState<any | null>(null);
  const [decisionType, setDecisionType] = useState<'VERIFIED' | 'REJECTED' | 'SUSPENDED'>('VERIFIED');
  const [decisionNotes, setDecisionNotes] = useState<string>('');
  const [submittingDecision, setSubmittingDecision] = useState<boolean>(false);
  const [decisionMsg, setDecisionMsg] = useState<{ type: 'success' | 'error'; text: string } | null>(null);

  const [currentAdminUid, setCurrentAdminUid] = useState<string>('');

  useEffect(() => {
    if (typeof window !== 'undefined') {
      try {
        const u = JSON.parse(localStorage.getItem('nyaypath_user') || '{}');
        if (u.user_id) setCurrentAdminUid(u.user_id);
      } catch {}
    }
  }, []);

  const loadQueue = async () => {
    setLoading(true);
    setError(null);
    try {
      const data = await getPlatformLawyerQueue({
        status: statusFilter === 'ALL' ? undefined : statusFilter,
        page: currentPage,
        page_size: pageSize
      });
      setLawyers(data.lawyers || []);
      setTotal(data.total || 0);
    } catch (err: any) {
      setError(err?.response?.data?.detail || 'Failed to load lawyer verification queue.');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadQueue();
  }, [currentPage, statusFilter]);

  const openDecisionModal = (lawyer: any, decision: 'VERIFIED' | 'REJECTED' | 'SUSPENDED') => {
    setSelectedLawyer(lawyer);
    setDecisionType(decision);
    setDecisionNotes('');
    setDecisionMsg(null);
  };

  const submitDecision = async () => {
    if (!selectedLawyer) return;

    setSubmittingDecision(true);
    setDecisionMsg(null);
    try {
      await processPlatformLawyerDecision(selectedLawyer.id, {
        decision: decisionType,
        notes: decisionNotes.trim() || undefined
      });
      setDecisionMsg({
        type: 'success',
        text: `Advocate ${selectedLawyer.full_name} is now ${decisionType}.`
      });
      setTimeout(() => {
        setSelectedLawyer(null);
        loadQueue();
      }, 1000);
    } catch (err: any) {
      setDecisionMsg({
        type: 'error',
        text: err?.response?.data?.detail || 'Failed to execute verification decision.'
      });
    } finally {
      setSubmittingDecision(false);
    }
  };

  const totalPages = Math.ceil(total / pageSize) || 1;

  return (
    <AdminLayout
      title="Advocate Verification & Bar Oversight"
      subtitle="Examine Bar Council enrollment credentials, practice history, and process verification decisions."
      badge="Bar Credentials Vault"
    >
      {/* Status Filter Tabs */}
      <div className="bg-white p-3 rounded-2xl border border-slate-200 shadow-sm mb-6 flex flex-wrap items-center justify-between gap-3">
        <div className="flex items-center gap-1.5 overflow-x-auto">
          {[
            { id: 'PENDING', label: 'Pending Review' },
            { id: 'VERIFIED', label: 'Verified Advocates' },
            { id: 'REJECTED', label: 'Rejected' },
            { id: 'SUSPENDED', label: 'Suspended' },
            { id: 'ALL', label: 'All Entries' }
          ].map((tab) => (
            <button
              key={tab.id}
              onClick={() => {
                setStatusFilter(tab.id);
                setCurrentPage(1);
              }}
              className={`px-3.5 py-1.5 rounded-xl text-xs font-semibold transition-all whitespace-nowrap ${
                statusFilter === tab.id
                  ? 'bg-court-maroon text-white shadow-sm'
                  : 'text-slate-600 hover:bg-slate-100'
              }`}
            >
              {tab.label}
            </button>
          ))}
        </div>

        <button
          onClick={loadQueue}
          disabled={loading}
          className="inline-flex items-center gap-1.5 px-3 py-1.5 text-xs font-medium rounded-lg text-slate-600 hover:bg-slate-50 border border-slate-200"
        >
          <RefreshCw className={`w-3.5 h-3.5 ${loading ? 'animate-spin' : ''}`} />
          Refresh
        </button>
      </div>

      {error && (
        <div className="bg-red-50 border border-red-200 text-red-700 px-4 py-3 rounded-xl mb-6 text-sm flex items-center justify-between">
          <div className="flex items-center gap-2">
            <AlertTriangle className="w-4 h-4 shrink-0" />
            <span>{error}</span>
          </div>
          <button onClick={loadQueue} className="text-xs underline font-semibold">
            Retry
          </button>
        </div>
      )}

      {/* Lawyers Table */}
      <div className="bg-white rounded-2xl border border-slate-200 shadow-sm overflow-hidden mb-6">
        <div className="overflow-x-auto">
          <table className="w-full text-left text-xs sm:text-sm">
            <thead className="bg-slate-100/70 text-slate-600 font-bold uppercase text-[11px] border-b border-slate-200">
              <tr>
                <th className="py-3 px-4">Advocate</th>
                <th className="py-3 px-4">Bar Council</th>
                <th className="py-3 px-4">Enrollment No.</th>
                <th className="py-3 px-4">Experience</th>
                <th className="py-3 px-4">Status</th>
                <th className="py-3 px-4">Submission Date</th>
                <th className="py-3 px-4 text-right">Verification Actions</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100 text-slate-700">
              {loading ? (
                <tr>
                  <td colSpan={7} className="py-10 text-center text-slate-400">
                    Loading verification queue...
                  </td>
                </tr>
              ) : lawyers.length === 0 ? (
                <tr>
                  <td colSpan={7} className="py-10 text-center text-slate-400">
                    No advocate records found for status '{statusFilter}'.
                  </td>
                </tr>
              ) : (
                lawyers.map((lawyer) => {
                  const isCurrentAdmin = lawyer.id === currentAdminUid;
                  return (
                    <tr key={lawyer.id} className="hover:bg-slate-50/50 transition-colors">
                      <td className="py-3 px-4">
                        <div className="font-semibold text-slate-900">{lawyer.full_name}</div>
                        <div className="text-xs text-slate-400 font-mono truncate max-w-[200px]">
                          {lawyer.email}
                        </div>
                      </td>
                      <td className="py-3 px-4 text-xs font-semibold text-slate-700">
                        {lawyer.bar_council} ({lawyer.enrollment_state})
                      </td>
                      <td className="py-3 px-4 font-mono text-xs font-bold text-court-maroon">
                        {lawyer.enrollment_number}
                      </td>
                      <td className="py-3 px-4 text-xs text-slate-600">
                        {lawyer.years_of_practice} years
                      </td>
                      <td className="py-3 px-4">
                        {lawyer.verification_status === 'VERIFIED' ? (
                          <span className="inline-flex items-center gap-1 text-emerald-700 font-semibold text-xs">
                            <CheckCircle2 className="w-3.5 h-3.5" />
                            NyayPath Verified
                          </span>
                        ) : lawyer.verification_status === 'PENDING' ? (
                          <span className="inline-flex items-center gap-1 text-amber-700 font-semibold text-xs">
                            <Clock className="w-3.5 h-3.5" />
                            Pending Review
                          </span>
                        ) : lawyer.verification_status === 'SUSPENDED' ? (
                          <span className="inline-flex items-center gap-1 text-red-600 font-semibold text-xs">
                            <AlertTriangle className="w-3.5 h-3.5" />
                            Suspended
                          </span>
                        ) : (
                          <span className="inline-flex items-center gap-1 text-slate-500 font-semibold text-xs">
                            Rejected
                          </span>
                        )}
                      </td>
                      <td className="py-3 px-4 text-xs text-slate-400 whitespace-nowrap">
                        {new Date(lawyer.created_at).toLocaleDateString()}
                      </td>
                      <td className="py-3 px-4 text-right">
                        <div className="flex items-center justify-end gap-1.5">
                          {isCurrentAdmin ? (
                            <span className="text-[11px] text-slate-400 italic px-2">Self-Verification Prohibited</span>
                          ) : (
                            <>
                              {lawyer.verification_status !== 'VERIFIED' && (
                                <button
                                  onClick={() => openDecisionModal(lawyer, 'VERIFIED')}
                                  className="px-2.5 py-1 text-xs font-semibold rounded-lg text-emerald-700 bg-emerald-50 hover:bg-emerald-100 border border-emerald-200 transition-colors"
                                >
                                  Verify
                                </button>
                              )}
                              {lawyer.verification_status !== 'REJECTED' && lawyer.verification_status !== 'VERIFIED' && (
                                <button
                                  onClick={() => openDecisionModal(lawyer, 'REJECTED')}
                                  className="px-2.5 py-1 text-xs font-semibold rounded-lg text-slate-700 bg-slate-100 hover:bg-slate-200 transition-colors"
                                >
                                  Reject
                                </button>
                              )}
                              {lawyer.verification_status === 'VERIFIED' && (
                                <button
                                  onClick={() => openDecisionModal(lawyer, 'SUSPENDED')}
                                  className="px-2.5 py-1 text-xs font-semibold rounded-lg text-red-700 bg-red-50 hover:bg-red-100 border border-red-200 transition-colors"
                                >
                                  Suspend
                                </button>
                              )}
                            </>
                          )}
                        </div>
                      </td>
                    </tr>
                  );
                })
              )}
            </tbody>
          </table>
        </div>

        {/* Pagination Bar */}
        <div className="p-4 border-t border-slate-200 flex items-center justify-between bg-slate-50/50 text-xs text-slate-600">
          <div>
            Showing <strong>{lawyers.length}</strong> of <strong>{total}</strong> lawyer records
          </div>
          <div className="flex items-center gap-2">
            <button
              onClick={() => setCurrentPage((p) => Math.max(1, p - 1))}
              disabled={currentPage <= 1}
              className="p-1.5 rounded-lg border border-slate-200 text-slate-600 hover:bg-slate-100 disabled:opacity-40"
            >
              <ChevronLeft className="w-4 h-4" />
            </button>
            <span>
              Page {currentPage} of {totalPages}
            </span>
            <button
              onClick={() => setCurrentPage((p) => Math.min(totalPages, p + 1))}
              disabled={currentPage >= totalPages}
              className="p-1.5 rounded-lg border border-slate-200 text-slate-600 hover:bg-slate-100 disabled:opacity-40"
            >
              <ChevronRight className="w-4 h-4" />
            </button>
          </div>
        </div>
      </div>

      {/* Decision Modal */}
      {selectedLawyer && (
        <div className="fixed inset-0 z-50 bg-black/50 backdrop-blur-sm flex items-center justify-center p-4">
          <div className="bg-white rounded-2xl max-w-md w-full p-6 shadow-2xl border border-slate-200">
            <h3 className="font-serif font-bold text-slate-900 text-lg mb-1">
              Confirm Advocate Decision: {decisionType}
            </h3>
            <p className="text-xs text-slate-600 mb-4">
              Advocate: <strong>{selectedLawyer.full_name}</strong> ({selectedLawyer.bar_council})
            </p>

            <div className="bg-slate-50 p-3 rounded-xl border border-slate-100 text-xs text-slate-700 space-y-1 mb-4">
              <div>Bar Enrollment: <strong className="font-mono text-court-maroon">{selectedLawyer.enrollment_number}</strong></div>
              <div>State of Enrollment: <strong>{selectedLawyer.enrollment_state}</strong></div>
              <div>Years of Practice: <strong>{selectedLawyer.years_of_practice}</strong></div>
            </div>

            <div className="mb-4">
              <label className="block text-xs font-bold text-slate-700 uppercase mb-1">
                Verification Findings / Administrative Notes:
              </label>
              <textarea
                rows={3}
                placeholder="Enter verification findings, certificate confirmation notes, or rejection reason..."
                value={decisionNotes}
                onChange={(e) => setDecisionNotes(e.target.value)}
                className="w-full p-3 text-xs sm:text-sm border border-slate-200 rounded-xl focus:outline-none focus:ring-2 focus:ring-court-maroon/20 focus:border-court-maroon"
              />
            </div>

            {decisionMsg && (
              <div
                className={`p-3 rounded-xl mb-4 text-xs ${
                  decisionMsg.type === 'success'
                    ? 'bg-emerald-50 text-emerald-800 border border-emerald-200'
                    : 'bg-red-50 text-red-800 border border-red-200'
                }`}
              >
                {decisionMsg.text}
              </div>
            )}

            <div className="flex justify-end gap-2">
              <button
                type="button"
                onClick={() => setSelectedLawyer(null)}
                disabled={submittingDecision}
                className="px-4 py-2 rounded-xl text-xs font-medium border border-slate-200 text-slate-600 hover:bg-slate-50"
              >
                Cancel
              </button>
              <button
                type="button"
                onClick={submitDecision}
                disabled={submittingDecision}
                className={`px-4 py-2 rounded-xl text-xs font-semibold text-white shadow ${
                  decisionType === 'VERIFIED'
                    ? 'bg-emerald-600 hover:bg-emerald-700'
                    : decisionType === 'SUSPENDED'
                    ? 'bg-red-600 hover:bg-red-700'
                    : 'bg-slate-800 hover:bg-slate-900'
                } disabled:opacity-50`}
              >
                {submittingDecision ? 'Executing...' : `Confirm ${decisionType}`}
              </button>
            </div>
          </div>
        </div>
      )}
    </AdminLayout>
  );
}
