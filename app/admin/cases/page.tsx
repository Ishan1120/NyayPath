'use client';

import React, { useState, useEffect } from 'react';
import {
  Scale,
  Search,
  Filter,
  RefreshCw,
  AlertTriangle,
  CheckCircle2,
  Lock,
  Unlock,
  ShieldCheck,
  ChevronLeft,
  ChevronRight,
  Eye,
  X,
  FileText,
  Building,
  UserCheck
} from 'lucide-react';
import AdminLayout from '../AdminLayout';
import {
  getPlatformCases,
  getPlatformCaseConfidentialAccess
} from '@/lib/api';

export default function AdminCasesPage() {
  const [cases, setCases] = useState<any[]>([]);
  const [total, setTotal] = useState<number>(0);
  const [loading, setLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);

  // Filters
  const [search, setSearch] = useState<string>('');
  const [caseTypeFilter, setCaseTypeFilter] = useState<string>('');
  const [statusFilter, setStatusFilter] = useState<string>('');
  const [instFilter, setInstFilter] = useState<string>('');
  const [currentPage, setCurrentPage] = useState<number>(1);
  const pageSize = 15;

  // Exceptional Confidential Access Modal
  const [selectedCase, setSelectedCase] = useState<any | null>(null);
  const [accessReason, setAccessReason] = useState<string>('');
  const [requestingAccess, setRequestingAccess] = useState<boolean>(false);
  const [unmaskedCaseData, setUnmaskedCaseData] = useState<any | null>(null);
  const [accessMsg, setAccessMsg] = useState<{ type: 'success' | 'error'; text: string } | null>(null);

  const loadCases = async () => {
    setLoading(true);
    setError(null);
    try {
      const data = await getPlatformCases({
        case_type: caseTypeFilter || undefined,
        status: statusFilter || undefined,
        institution: instFilter || undefined,
        search: search.trim() || undefined,
        page: currentPage,
        page_size: pageSize
      });
      setCases(data.cases || []);
      setTotal(data.total || 0);
    } catch (err: any) {
      setError(err?.response?.data?.detail || 'Failed to load case oversight directory.');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadCases();
  }, [currentPage, caseTypeFilter, statusFilter, instFilter]);

  const handleSearchSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    setCurrentPage(1);
    loadCases();
  };

  const openExceptionalAccess = (caseItem: any) => {
    setSelectedCase(caseItem);
    setAccessReason('');
    setUnmaskedCaseData(null);
    setAccessMsg(null);
  };

  const submitExceptionalAccess = async () => {
    if (!selectedCase) return;
    if (!accessReason || accessReason.trim().length < 10) {
      setAccessMsg({
        type: 'error',
        text: 'A legitimate operational reason (minimum 10 characters) is strictly required.'
      });
      return;
    }

    setRequestingAccess(true);
    setAccessMsg(null);
    try {
      const result = await getPlatformCaseConfidentialAccess(selectedCase.case_id, {
        reason: accessReason.trim()
      });
      setUnmaskedCaseData(result);
      setAccessMsg({
        type: 'success',
        text: 'Access granted and permanently logged in the immutable platform audit trail.'
      });
    } catch (err: any) {
      setAccessMsg({
        type: 'error',
        text: err?.response?.data?.detail || 'Failed to obtain exceptional case access.'
      });
    } finally {
      setRequestingAccess(false);
    }
  };

  const totalPages = Math.ceil(total / pageSize) || 1;

  return (
    <AdminLayout
      title="Global Case Oversight & Redressal Monitoring"
      subtitle="Cross-platform case volumes, progression metrics, and privacy-preserving administrative oversight."
      badge="Privacy-Preserving Telemetry"
    >
      {/* Search & Filters */}
      <div className="bg-white p-5 rounded-2xl border border-slate-200 shadow-sm mb-6">
        <form onSubmit={handleSearchSubmit} className="flex flex-col md:flex-row gap-3">
          <div className="relative flex-1">
            <Search className="w-4 h-4 text-slate-400 absolute left-3.5 top-3" />
            <input
              type="text"
              placeholder="Search by case ID, category, or institution..."
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              className="w-full pl-10 pr-4 py-2 text-xs sm:text-sm border border-slate-200 rounded-xl focus:outline-none focus:ring-2 focus:ring-court-maroon/20 focus:border-court-maroon"
            />
          </div>

          <div className="flex flex-wrap sm:flex-nowrap gap-2">
            <select
              value={caseTypeFilter}
              onChange={(e) => {
                setCaseTypeFilter(e.target.value);
                setCurrentPage(1);
              }}
              className="px-3 py-2 text-xs sm:text-sm border border-slate-200 rounded-xl bg-white text-slate-700"
            >
              <option value="">All Case Types</option>
              <option value="CAMPUS_GRIEVANCE">Campus Grievance</option>
              <option value="RTI">RTI Application</option>
              <option value="FIRST_APPEAL">First Appeal</option>
              <option value="CONSUMER_COMPLAINT">Consumer Dispute</option>
              <option value="GENERAL_GRIEVANCE">General Grievance</option>
            </select>

            <select
              value={statusFilter}
              onChange={(e) => {
                setStatusFilter(e.target.value);
                setCurrentPage(1);
              }}
              className="px-3 py-2 text-xs sm:text-sm border border-slate-200 rounded-xl bg-white text-slate-700"
            >
              <option value="">All Statuses</option>
              <option value="SUBMITTED">Submitted</option>
              <option value="FILED">Filed</option>
              <option value="UNDER_INQUIRY">Under Inquiry</option>
              <option value="HEARING_SCHEDULED">Hearing Scheduled</option>
              <option value="ACTION_TAKEN">Action Taken</option>
              <option value="RESOLVED">Resolved</option>
              <option value="CLOSED">Closed</option>
            </select>

            <button
              type="submit"
              className="px-4 py-2 text-xs font-semibold rounded-xl bg-court-maroon text-white hover:bg-court-maroon/90 shadow transition-colors"
            >
              Filter
            </button>
            <button
              type="button"
              onClick={() => {
                setSearch('');
                setCaseTypeFilter('');
                setStatusFilter('');
                setInstFilter('');
                setCurrentPage(1);
              }}
              className="px-3 py-2 text-xs font-medium rounded-xl border border-slate-200 text-slate-600 hover:bg-slate-50"
            >
              Reset
            </button>
          </div>
        </form>
      </div>

      {error && (
        <div className="bg-red-50 border border-red-200 text-red-700 px-4 py-3 rounded-xl mb-6 text-sm flex items-center justify-between">
          <div className="flex items-center gap-2">
            <AlertTriangle className="w-4 h-4 shrink-0" />
            <span>{error}</span>
          </div>
          <button onClick={loadCases} className="text-xs underline font-semibold">
            Retry
          </button>
        </div>
      )}

      {/* Cases Table */}
      <div className="bg-white rounded-2xl border border-slate-200 shadow-sm overflow-hidden mb-6">
        <div className="overflow-x-auto">
          <table className="w-full text-left text-xs sm:text-sm">
            <thead className="bg-slate-100/70 text-slate-600 font-bold uppercase text-[11px] border-b border-slate-200">
              <tr>
                <th className="py-3 px-4">Case ID</th>
                <th className="py-3 px-4">Type</th>
                <th className="py-3 px-4">Institution</th>
                <th className="py-3 px-4">Category</th>
                <th className="py-3 px-4">Severity</th>
                <th className="py-3 px-4">Confidentiality</th>
                <th className="py-3 px-4">Status</th>
                <th className="py-3 px-4 text-right">Oversight</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100 text-slate-700">
              {loading ? (
                <tr>
                  <td colSpan={8} className="py-10 text-center text-slate-400">
                    Loading global cases...
                  </td>
                </tr>
              ) : cases.length === 0 ? (
                <tr>
                  <td colSpan={8} className="py-10 text-center text-slate-400">
                    No cases found for the selected criteria.
                  </td>
                </tr>
              ) : (
                cases.map((c) => (
                  <tr key={c.id} className="hover:bg-slate-50/50 transition-colors">
                    <td className="py-3 px-4 font-mono font-bold text-slate-900">
                      {c.case_id}
                    </td>
                    <td className="py-3 px-4">
                      <span className="inline-flex items-center px-2 py-0.5 rounded text-[10px] font-bold bg-slate-100 text-slate-700 uppercase">
                        {c.case_type.replace('_', ' ')}
                      </span>
                    </td>
                    <td className="py-3 px-4 text-xs font-semibold text-blue-700">
                      {c.institution_id}
                    </td>
                    <td className="py-3 px-4 text-xs text-slate-700">
                      {c.category}
                    </td>
                    <td className="py-3 px-4">
                      <span
                        className={`inline-flex items-center px-2 py-0.5 rounded text-[10px] font-bold uppercase ${
                          c.severity === 'URGENT'
                            ? 'bg-red-100 text-red-800'
                            : c.severity === 'HIGH'
                            ? 'bg-amber-100 text-amber-800'
                            : 'bg-slate-100 text-slate-700'
                        }`}
                      >
                        {c.severity}
                      </span>
                    </td>
                    <td className="py-3 px-4 text-xs text-slate-500">
                      <span className="inline-flex items-center gap-1">
                        <Lock className="w-3 h-3 text-slate-400" />
                        {c.confidentiality_mode}
                      </span>
                    </td>
                    <td className="py-3 px-4 font-semibold text-xs">
                      <span
                        className={
                          c.status === 'RESOLVED' || c.status === 'CLOSED'
                            ? 'text-emerald-700'
                            : c.status === 'UNDER_INQUIRY' || c.status === 'HEARING_SCHEDULED'
                            ? 'text-indigo-700'
                            : 'text-slate-800'
                        }
                      >
                        {c.status}
                      </span>
                    </td>
                    <td className="py-3 px-4 text-right">
                      <button
                        onClick={() => openExceptionalAccess(c)}
                        className="inline-flex items-center gap-1 px-2.5 py-1 text-xs font-medium rounded-lg text-court-maroon bg-court-maroon/10 hover:bg-court-maroon/20 transition-colors"
                      >
                        <Lock className="w-3 h-3" />
                        Exceptional Access
                      </button>
                    </td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>

        {/* Pagination Bar */}
        <div className="p-4 border-t border-slate-200 flex items-center justify-between bg-slate-50/50 text-xs text-slate-600">
          <div>
            Showing <strong>{cases.length}</strong> of <strong>{total}</strong> cases
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

      {/* Exceptional Confidential Access Modal */}
      {selectedCase && (
        <div className="fixed inset-0 z-50 bg-black/50 backdrop-blur-sm flex items-center justify-center p-4">
          <div className="bg-white rounded-2xl max-w-xl w-full p-6 shadow-2xl border border-slate-200 max-h-[85vh] overflow-y-auto">
            <div className="flex items-center justify-between mb-4">
              <h3 className="font-serif font-bold text-slate-900 text-lg flex items-center gap-2">
                <ShieldCheck className="w-5 h-5 text-court-maroon" />
                Exceptional Confidential Access
              </h3>
              <button
                onClick={() => setSelectedCase(null)}
                className="text-slate-400 hover:text-slate-600"
              >
                <X className="w-5 h-5" />
              </button>
            </div>

            <div className="bg-amber-50 border border-amber-200 text-amber-800 p-3 rounded-xl text-xs mb-4">
              <strong>Statutory Compliance Notice:</strong> Platform Administrator access to confidential grievance details bypasses default institutional masking. This access request is strictly auditable and recorded permanently in the append-only audit trail.
            </div>

            <div className="space-y-1 text-xs text-slate-700 bg-slate-50 p-3 rounded-xl border border-slate-100 mb-4">
              <div>Case ID: <strong className="font-mono text-court-maroon">{selectedCase.case_id}</strong></div>
              <div>Institution: <strong>{selectedCase.institution_id}</strong></div>
              <div>Current Status: <strong>{selectedCase.status}</strong></div>
            </div>

            {!unmaskedCaseData ? (
              <div className="space-y-3 mb-4">
                <label className="block text-xs font-bold text-slate-700 uppercase">
                  Mandatory Operational Justification (Minimum 10 Characters):
                </label>
                <textarea
                  rows={3}
                  placeholder="State the formal statutory, disciplinary inquiry, or regulatory oversight purpose for accessing confidential details..."
                  value={accessReason}
                  onChange={(e) => setAccessReason(e.target.value)}
                  className="w-full p-3 text-xs sm:text-sm border border-slate-200 rounded-xl focus:outline-none focus:ring-2 focus:ring-court-maroon/20 focus:border-court-maroon"
                />

                {accessMsg && (
                  <div
                    className={`p-3 rounded-xl text-xs ${
                      accessMsg.type === 'success'
                        ? 'bg-emerald-50 text-emerald-800 border border-emerald-200'
                        : 'bg-red-50 text-red-800 border border-red-200'
                    }`}
                  >
                    {accessMsg.text}
                  </div>
                )}

                <div className="flex justify-end gap-2 pt-2">
                  <button
                    type="button"
                    onClick={() => setSelectedCase(null)}
                    disabled={requestingAccess}
                    className="px-4 py-2 rounded-xl text-xs font-medium border border-slate-200 text-slate-600 hover:bg-slate-50"
                  >
                    Cancel
                  </button>
                  <button
                    type="button"
                    onClick={submitExceptionalAccess}
                    disabled={requestingAccess}
                    className="px-4 py-2 rounded-xl text-xs font-semibold bg-court-maroon text-white hover:bg-court-maroon/90 shadow disabled:opacity-50"
                  >
                    {requestingAccess ? 'Auditing & Unlocking...' : 'Audit & Access Confidential File'}
                  </button>
                </div>
              </div>
            ) : (
              <div className="space-y-4">
                <div className="p-3 bg-emerald-50 border border-emerald-200 rounded-xl text-xs text-emerald-800 font-semibold flex items-center gap-2">
                  <CheckCircle2 className="w-4 h-4 shrink-0" />
                  Audit Record Registered (ID: {unmaskedCaseData.audit_log_id})
                </div>

                <div className="border border-slate-200 rounded-xl p-4 bg-slate-50/50 space-y-3 text-xs">
                  <h4 className="font-serif font-bold text-slate-900 text-sm">
                    Unmasked Grievance File
                  </h4>
                  {unmaskedCaseData.campus_details ? (
                    <>
                      <div>
                        <span className="text-slate-500">Student Name:</span>{' '}
                        <strong>{unmaskedCaseData.campus_details.student_name || 'Not provided'}</strong>
                      </div>
                      <div>
                        <span className="text-slate-500">Roll Number:</span>{' '}
                        <strong className="font-mono">{unmaskedCaseData.campus_details.roll_number || 'N/A'}</strong>
                      </div>
                      <div>
                        <span className="text-slate-500">Department & Year:</span>{' '}
                        <strong>{unmaskedCaseData.campus_details.department} ({unmaskedCaseData.campus_details.year})</strong>
                      </div>
                      <div>
                        <span className="text-slate-500">Subject:</span>{' '}
                        <strong>{unmaskedCaseData.campus_details.subject}</strong>
                      </div>
                      <div>
                        <span className="text-slate-500">Grievance Description:</span>
                        <p className="mt-1 p-2.5 bg-white border border-slate-200 rounded-lg text-slate-800 leading-relaxed whitespace-pre-wrap">
                          {unmaskedCaseData.campus_details.description}
                        </p>
                      </div>
                      <div>
                        <span className="text-slate-500">Internal Proctor Notes:</span>
                        <p className="mt-1 p-2.5 bg-white border border-slate-200 rounded-lg text-slate-800 italic">
                          {unmaskedCaseData.campus_details.proctor_notes || 'No confidential proctor notes recorded.'}
                        </p>
                      </div>
                    </>
                  ) : (
                    <div>
                      <span className="text-slate-500">Case Data:</span>
                      <pre className="mt-1 p-2 bg-white border border-slate-200 rounded-lg text-[11px] overflow-x-auto">
                        {JSON.stringify(unmaskedCaseData.case?.data, null, 2)}
                      </pre>
                    </div>
                  )}
                </div>

                <div className="flex justify-end">
                  <button
                    onClick={() => setSelectedCase(null)}
                    className="px-4 py-2 rounded-xl text-xs font-semibold bg-slate-800 text-white hover:bg-slate-900"
                  >
                    Close Confidential Viewer
                  </button>
                </div>
              </div>
            )}
          </div>
        </div>
      )}
    </AdminLayout>
  );
}

