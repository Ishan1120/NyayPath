'use client';

import React, { useState, useEffect } from 'react';
import {
  Activity,
  Search,
  Filter,
  RefreshCw,
  AlertTriangle,
  CheckCircle2,
  Lock,
  ChevronLeft,
  ChevronRight,
  Eye,
  X,
  ShieldCheck,
  FileText
} from 'lucide-react';
import AdminLayout from '../AdminLayout';
import {
  getPlatformAuditLogs,
  PlatformAuditLogItem
} from '@/lib/api';

export default function AdminAuditLogsPage() {
  const [logs, setLogs] = useState<PlatformAuditLogItem[]>([]);
  const [total, setTotal] = useState<number>(0);
  const [loading, setLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);

  // Filters
  const [actionFilter, setActionFilter] = useState<string>('');
  const [entityFilter, setEntityFilter] = useState<string>('');
  const [instFilter, setInstFilter] = useState<string>('');
  const [currentPage, setCurrentPage] = useState<number>(1);
  const pageSize = 25;

  // Selected Detail Modal
  const [selectedLog, setSelectedLog] = useState<PlatformAuditLogItem | null>(null);

  const loadAuditLogs = async () => {
    setLoading(true);
    setError(null);
    try {
      const data = await getPlatformAuditLogs({
        action_type: actionFilter || undefined,
        entity_type: entityFilter || undefined,
        institution: instFilter || undefined,
        page: currentPage,
        page_size: pageSize
      });
      setLogs(data.audit_logs || []);
      setTotal(data.total || 0);
    } catch (err: any) {
      setError(err?.response?.data?.detail || 'Failed to load platform audit trail.');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadAuditLogs();
  }, [currentPage, actionFilter, entityFilter, instFilter]);

  const totalPages = Math.ceil(total / pageSize) || 1;

  const getActionBadge = (action: string) => {
    if (action.includes('SUSPEND') || action.includes('DEACTIVATE') || action.includes('REJECT')) {
      return 'bg-amber-100 text-amber-800 border-amber-200';
    }
    if (action.includes('ACTIVE') || action.includes('VERIF') || action.includes('REGISTER')) {
      return 'bg-emerald-100 text-emerald-800 border-emerald-200';
    }
    if (action.includes('CONFIDENTIAL') || action.includes('ACCESS')) {
      return 'bg-purple-100 text-purple-800 border-purple-200';
    }
    return 'bg-slate-100 text-slate-800 border-slate-200';
  };

  return (
    <AdminLayout
      title="Immutable Audit & Administrative Activity Centre"
      subtitle="Cryptographically tamper-proof, append-only operational log recording all platform administrative actions."
      badge="Append-Only Vault"
    >
      {/* Guarantees Notice */}
      <div className="bg-slate-900 text-white p-4 rounded-2xl shadow-sm mb-6 flex flex-col sm:flex-row sm:items-center justify-between gap-3 text-xs">
        <div className="flex items-center gap-2">
          <ShieldCheck className="w-4 h-4 text-court-gold shrink-0" />
          <span>
            <strong>PostgreSQL Engine Enforcement:</strong> Updates and Deletions are structurally prohibited by database trigger <code>trg_platform_audit_immutability</code>.
          </span>
        </div>
        <button
          onClick={loadAuditLogs}
          disabled={loading}
          className="inline-flex items-center gap-1.5 px-3 py-1.5 text-xs font-semibold rounded-lg bg-white/10 hover:bg-white/20 text-white shrink-0"
        >
          <RefreshCw className={`w-3.5 h-3.5 ${loading ? 'animate-spin' : ''}`} />
          Refresh Log
        </button>
      </div>

      {/* Filter Bar */}
      <div className="bg-white p-4 rounded-2xl border border-slate-200 shadow-sm mb-6 flex flex-wrap gap-2 items-center">
        <select
          value={actionFilter}
          onChange={(e) => {
            setActionFilter(e.target.value);
            setCurrentPage(1);
          }}
          className="px-3 py-2 text-xs sm:text-sm border border-slate-200 rounded-xl bg-white text-slate-700 focus:outline-none focus:ring-2 focus:ring-court-maroon/20"
        >
          <option value="">All Action Types</option>
          <option value="USER_ACTIVE">User Reinstated</option>
          <option value="USER_SUSPENDED">User Suspended</option>
          <option value="USER_REVOKED">User Revoked</option>
          <option value="INSTITUTION_REGISTERED">Institution Registered</option>
          <option value="INSTITUTION_ACTIVATED">Institution Activated</option>
          <option value="INSTITUTION_DEACTIVATED">Institution Deactivated</option>
          <option value="LAWYER_VERIFIED">Lawyer Verified</option>
          <option value="LAWYER_REJECTED">Lawyer Rejected</option>
          <option value="LAWYER_SUSPENDED">Lawyer Suspended</option>
          <option value="EXCEPTIONAL_CONFIDENTIAL_CASE_ACCESS">Exceptional Case Access</option>
        </select>

        <select
          value={entityFilter}
          onChange={(e) => {
            setEntityFilter(e.target.value);
            setCurrentPage(1);
          }}
          className="px-3 py-2 text-xs sm:text-sm border border-slate-200 rounded-xl bg-white text-slate-700 focus:outline-none focus:ring-2 focus:ring-court-maroon/20"
        >
          <option value="">All Entity Types</option>
          <option value="USER">User</option>
          <option value="INSTITUTION">Institution</option>
          <option value="LAWYER">Lawyer</option>
          <option value="CASE">Case</option>
          <option value="SYSTEM">System</option>
        </select>

        <button
          onClick={() => {
            setActionFilter('');
            setEntityFilter('');
            setInstFilter('');
            setCurrentPage(1);
          }}
          className="px-3 py-2 text-xs font-medium rounded-xl border border-slate-200 text-slate-600 hover:bg-slate-50"
        >
          Reset Filters
        </button>
      </div>

      {error && (
        <div className="bg-red-50 border border-red-200 text-red-700 px-4 py-3 rounded-xl mb-6 text-sm flex items-center justify-between">
          <div className="flex items-center gap-2">
            <AlertTriangle className="w-4 h-4 shrink-0" />
            <span>{error}</span>
          </div>
          <button onClick={loadAuditLogs} className="text-xs underline font-semibold">
            Retry
          </button>
        </div>
      )}

      {/* Audit Log Table */}
      <div className="bg-white rounded-2xl border border-slate-200 shadow-sm overflow-hidden mb-6">
        <div className="overflow-x-auto">
          <table className="w-full text-left text-xs sm:text-sm">
            <thead className="bg-slate-100/70 text-slate-600 font-bold uppercase text-[11px] border-b border-slate-200">
              <tr>
                <th className="py-3 px-4">Event Action</th>
                <th className="py-3 px-4">Entity</th>
                <th className="py-3 px-4">Admin Actor</th>
                <th className="py-3 px-4">Audit Reason / Remarks</th>
                <th className="py-3 px-4">Timestamp</th>
                <th className="py-3 px-4 text-right">Details</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100 text-slate-700">
              {loading ? (
                <tr>
                  <td colSpan={6} className="py-10 text-center text-slate-400">
                    Loading audit trail...
                  </td>
                </tr>
              ) : logs.length === 0 ? (
                <tr>
                  <td colSpan={6} className="py-10 text-center text-slate-400">
                    No audit records matching the specified filters.
                  </td>
                </tr>
              ) : (
                logs.map((log) => (
                  <tr key={log.id} className="hover:bg-slate-50/50 transition-colors">
                    <td className="py-3 px-4">
                      <span
                        className={`inline-flex items-center px-2 py-0.5 rounded text-[10px] font-bold border uppercase tracking-wider ${getActionBadge(
                          log.action_type
                        )}`}
                      >
                        {log.action_type}
                      </span>
                    </td>
                    <td className="py-3 px-4 text-xs font-mono font-semibold text-slate-800">
                      {log.target_entity_type}: <span className="text-slate-500">{log.target_entity_id}</span>
                    </td>
                    <td className="py-3 px-4 text-xs text-slate-600">
                      <div>{log.actor_email}</div>
                      <div className="text-[10px] text-slate-400 font-mono truncate max-w-[150px]">
                        {log.actor_user_id}
                      </div>
                    </td>
                    <td className="py-3 px-4 text-xs text-slate-600 max-w-xs truncate">
                      {log.reason || 'Standard administrative operation'}
                    </td>
                    <td className="py-3 px-4 text-xs text-slate-400 whitespace-nowrap">
                      {new Date(log.created_at).toLocaleString()}
                    </td>
                    <td className="py-3 px-4 text-right">
                      <button
                        onClick={() => setSelectedLog(log)}
                        className="p-1.5 text-slate-500 hover:text-court-maroon hover:bg-slate-100 rounded-lg transition-colors"
                        title="View Full JSON Record"
                      >
                        <Eye className="w-4 h-4" />
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
            Showing <strong>{logs.length}</strong> of <strong>{total}</strong> audit entries
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

      {/* JSON Record Modal */}
      {selectedLog && (
        <div className="fixed inset-0 z-50 bg-black/50 backdrop-blur-sm flex items-center justify-center p-4">
          <div className="bg-white rounded-2xl max-w-lg w-full p-6 shadow-2xl border border-slate-200">
            <div className="flex items-center justify-between mb-4">
              <h3 className="font-serif font-bold text-slate-900 text-lg flex items-center gap-2">
                <FileText className="w-5 h-5 text-court-maroon" />
                Immutable Audit Record
              </h3>
              <button
                onClick={() => setSelectedLog(null)}
                className="text-slate-400 hover:text-slate-600"
              >
                <X className="w-5 h-5" />
              </button>
            </div>

            <div className="space-y-2 text-xs text-slate-700 bg-slate-50 p-4 rounded-xl border border-slate-100 mb-4">
              <div>Record ID: <strong className="font-mono text-court-maroon">{selectedLog.id}</strong></div>
              <div>Event: <strong className="font-bold">{selectedLog.action_type}</strong></div>
              <div>Target: <strong>{selectedLog.target_entity_type} ({selectedLog.target_entity_id})</strong></div>
              <div>Actor: <strong>{selectedLog.actor_email}</strong></div>
              <div>Timestamp: <strong>{new Date(selectedLog.created_at).toISOString()}</strong></div>
              <div>Reason: <em>{selectedLog.reason || 'None specified'}</em></div>
            </div>

            <div className="mb-4">
              <div className="text-xs font-bold text-slate-700 uppercase mb-1">Details Payload:</div>
              <pre className="p-3 bg-slate-900 text-emerald-400 rounded-xl text-[11px] overflow-x-auto max-h-48 font-mono">
                {JSON.stringify(selectedLog.details, null, 2)}
              </pre>
            </div>

            <div className="flex justify-end">
              <button
                onClick={() => setSelectedLog(null)}
                className="px-4 py-2 rounded-xl text-xs font-semibold bg-slate-100 text-slate-700 hover:bg-slate-200"
              >
                Close
              </button>
            </div>
          </div>
        </div>
      )}
    </AdminLayout>
  );
}

