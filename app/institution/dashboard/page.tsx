'use client';

import React, { useState, useEffect } from 'react';
import Link from 'next/link';
import { 
  Building, 
  ShieldCheck, 
  Users, 
  FileText, 
  Clock, 
  AlertTriangle, 
  CheckCircle2, 
  BarChart3, 
  Search, 
  Filter, 
  RefreshCw, 
  Calendar, 
  Lock, 
  Eye, 
  UserCheck, 
  UserX, 
  ShieldAlert, 
  ChevronRight, 
  ExternalLink,
  ChevronLeft,
  Briefcase
} from 'lucide-react';
import Navbar from '@/app/Navbar';
import {
  getInstitutionDashboardStats,
  getInstitutionAnalytics,
  getInstitutionCases,
  getInstitutionMembers,
  updateInstitutionMemberStatus,
  getCaseDocumentUrl,
  InstitutionStats,
  InstitutionAnalytics,
  InstitutionMember
} from '@/lib/api';

export default function InstitutionAdminDashboard() {
  const [activeTab, setActiveTab] = useState<'grievances' | 'members' | 'analytics'>('grievances');
  const [stats, setStats] = useState<InstitutionStats | null>(null);
  const [analytics, setAnalytics] = useState<InstitutionAnalytics | null>(null);
  const [loadingStats, setLoadingStats] = useState<boolean>(true);

  // Grievances State
  const [cases, setCases] = useState<any[]>([]);
  const [totalCases, setTotalCases] = useState<number>(0);
  const [loadingCases, setLoadingCases] = useState<boolean>(false);
  const [statusFilter, setStatusFilter] = useState<string>('');
  const [severityFilter, setSeverityFilter] = useState<string>('');
  const [categoryFilter, setCategoryFilter] = useState<string>('');
  const [searchQuery, setSearchQuery] = useState<string>('');
  const [currentPage, setCurrentPage] = useState<number>(1);
  const pageSize = 10;

  // Members State
  const [members, setMembers] = useState<InstitutionMember[]>([]);
  const [loadingMembers, setLoadingMembers] = useState<boolean>(false);
  const [memberActionLoading, setMemberActionLoading] = useState<string | null>(null);

  // Selected Case Modal
  const [selectedCase, setSelectedCase] = useState<any | null>(null);

  // Error Message
  const [errorMessage, setErrorMessage] = useState<string | null>(null);

  useEffect(() => {
    fetchStats();
  }, []);

  useEffect(() => {
    if (activeTab === 'grievances') {
      fetchCases();
    } else if (activeTab === 'members') {
      fetchMembers();
    } else if (activeTab === 'analytics') {
      fetchAnalytics();
    }
  }, [activeTab, statusFilter, severityFilter, categoryFilter, currentPage]);

  const fetchStats = async () => {
    setLoadingStats(true);
    setErrorMessage(null);
    try {
      const data = await getInstitutionDashboardStats();
      if (data.status === 'success' && data.stats) {
        setStats(data.stats);
      }
    } catch (err: any) {
      console.error('Failed to load dashboard stats', err);
      setErrorMessage(err.response?.data?.detail || 'Failed to authenticate or retrieve institution stats.');
    } finally {
      setLoadingStats(false);
    }
  };

  const fetchCases = async () => {
    setLoadingCases(true);
    try {
      const offset = (currentPage - 1) * pageSize;
      const data = await getInstitutionCases({
        status: statusFilter || undefined,
        severity: severityFilter || undefined,
        category: categoryFilter || undefined,
        search: searchQuery || undefined,
        limit: pageSize,
        offset: offset
      });
      setCases(data.cases || []);
      setTotalCases(data.total || 0);
    } catch (err: any) {
      console.error('Failed to load institution cases', err);
    } finally {
      setLoadingCases(false);
    }
  };

  const fetchMembers = async () => {
    setLoadingMembers(true);
    try {
      const data = await getInstitutionMembers();
      setMembers(data.members || []);
    } catch (err: any) {
      console.error('Failed to load members', err);
    } finally {
      setLoadingMembers(false);
    }
  };

  const fetchAnalytics = async () => {
    try {
      const data = await getInstitutionAnalytics();
      if (data.status === 'success' && data.analytics) {
        setAnalytics(data.analytics);
      }
    } catch (err: any) {
      console.error('Failed to load analytics', err);
    }
  };

  const handleStatusChange = async (userId: string, newStatus: string) => {
    setMemberActionLoading(userId);
    try {
      await updateInstitutionMemberStatus(userId, newStatus);
      await fetchMembers();
      await fetchStats();
    } catch (err: any) {
      alert(err.response?.data?.detail || 'Failed to update member status');
    } finally {
      setMemberActionLoading(null);
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

  const totalPages = Math.ceil(totalCases / pageSize) || 1;

  return (
    <div className="min-h-screen bg-slate-50 text-slate-900">
      <Navbar />

      <main className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 pt-24 pb-16">
        {/* Workspace Banner */}
        <div className="bg-white border border-slate-200 rounded-2xl p-6 sm:p-8 shadow-sm mb-8">
          <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
            <div>
              <div className="flex items-center gap-3">
                <span className="p-2.5 bg-indigo-50 border border-indigo-100 rounded-xl text-indigo-700">
                  <Building className="w-6 h-6" />
                </span>
                <div>
                  <div className="flex items-center gap-2">
                    <h1 className="text-2xl font-black text-slate-900 tracking-tight">
                      Institution Administrator Workspace
                    </h1>
                    <span className="text-xs font-semibold px-2.5 py-0.5 rounded-full bg-indigo-100 text-indigo-800 border border-indigo-200">
                      ADMIN DESK
                    </span>
                  </div>
                  <p className="text-sm text-slate-500 mt-0.5">
                    Institution Identifier: <span className="font-mono font-semibold text-slate-700">{stats?.institution_id || 'LOCAL_COLLEGE'}</span> | Institutional Proctorial Oversight (Formal SGRC & University Ombudsperson Appeals required under UGC 2023 Regulations)
                  </p>
                </div>
              </div>
            </div>

            <div className="flex items-center gap-3">
              <Link
                href="/campus-proctor/chief"
                className="px-3.5 py-2 text-xs font-semibold text-slate-700 bg-slate-100 hover:bg-slate-200 border border-slate-200 rounded-lg transition-colors flex items-center gap-1.5"
              >
                <ShieldCheck className="w-4 h-4 text-slate-600" />
                Chief Proctor View
              </Link>
              <button
                onClick={() => { fetchStats(); fetchCases(); }}
                className="px-3.5 py-2 text-xs font-semibold text-slate-700 bg-white hover:bg-slate-50 border border-slate-200 rounded-lg shadow-sm transition-colors flex items-center gap-1.5 cursor-pointer"
              >
                <RefreshCw className="w-3.5 h-3.5 text-slate-500" />
                Refresh
              </button>
            </div>
          </div>

          {errorMessage && (
            <div className="mt-4 p-4 rounded-xl bg-amber-50 border border-amber-200 text-amber-800 text-sm flex items-start gap-3">
              <AlertTriangle className="w-5 h-5 text-amber-600 shrink-0 mt-0.5" />
              <div>
                <p className="font-semibold">Notice regarding institutional authorization</p>
                <p className="text-xs text-amber-700 mt-0.5">{errorMessage}</p>
              </div>
            </div>
          )}

          {/* Quick Metrics Cards */}
          <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-6 gap-3 mt-6">
            <div className="bg-slate-50/80 border border-slate-200/80 rounded-xl p-3.5">
              <div className="flex items-center justify-between text-xs font-semibold text-slate-500">
                <span>Total Grievances</span>
                <FileText className="w-4 h-4 text-slate-400" />
              </div>
              <div className="text-2xl font-black text-slate-900 mt-2 font-mono">
                {loadingStats ? '—' : stats?.total_cases ?? 0}
              </div>
              <span className="text-[11px] text-slate-500">All registered filings</span>
            </div>

            <div className="bg-slate-50/80 border border-slate-200/80 rounded-xl p-3.5">
              <div className="flex items-center justify-between text-xs font-semibold text-amber-700">
                <span>Active Inquiries</span>
                <Clock className="w-4 h-4 text-amber-500" />
              </div>
              <div className="text-2xl font-black text-amber-700 mt-2 font-mono">
                {loadingStats ? '—' : stats?.active_inquiries ?? 0}
              </div>
              <span className="text-[11px] text-amber-600">Under investigation</span>
            </div>

            <div className="bg-slate-50/80 border border-slate-200/80 rounded-xl p-3.5">
              <div className="flex items-center justify-between text-xs font-semibold text-purple-700">
                <span>Hearings Set</span>
                <Calendar className="w-4 h-4 text-purple-500" />
              </div>
              <div className="text-2xl font-black text-purple-700 mt-2 font-mono">
                {loadingStats ? '—' : stats?.hearings_scheduled ?? 0}
              </div>
              <span className="text-[11px] text-purple-600">Scheduled proceedings</span>
            </div>

            <div className="bg-slate-50/80 border border-slate-200/80 rounded-xl p-3.5">
              <div className="flex items-center justify-between text-xs font-semibold text-emerald-700">
                <span>Resolved</span>
                <CheckCircle2 className="w-4 h-4 text-emerald-500" />
              </div>
              <div className="text-2xl font-black text-emerald-700 mt-2 font-mono">
                {loadingStats ? '—' : stats?.resolved_cases ?? 0}
              </div>
              <span className="text-[11px] text-emerald-600">Disposed & closed</span>
            </div>

            <div className="bg-slate-50/80 border border-slate-200/80 rounded-xl p-3.5">
              <div className="flex items-center justify-between text-xs font-semibold text-rose-700">
                <span>SLA Breaches</span>
                <AlertTriangle className="w-4 h-4 text-rose-500" />
              </div>
              <div className="text-2xl font-black text-rose-700 mt-2 font-mono">
                {loadingStats ? '—' : stats?.sla_breaches ?? 0}
              </div>
              <span className="text-[11px] text-rose-600">&gt; 15 days pending</span>
            </div>

            <div className="bg-slate-50/80 border border-slate-200/80 rounded-xl p-3.5">
              <div className="flex items-center justify-between text-xs font-semibold text-indigo-700">
                <span>Active Officers</span>
                <Users className="w-4 h-4 text-indigo-500" />
              </div>
              <div className="text-2xl font-black text-indigo-700 mt-2 font-mono">
                {loadingStats ? '—' : stats?.active_members ?? 0}
              </div>
              <span className="text-[11px] text-indigo-600">Proctors & committee</span>
            </div>
          </div>
        </div>

        {/* Tab Navigation */}
        <div className="flex border-b border-slate-200 mb-6 gap-2">
          <button
            onClick={() => setActiveTab('grievances')}
            className={`pb-3 px-4 text-sm font-bold border-b-2 transition-colors flex items-center gap-2 cursor-pointer ${
              activeTab === 'grievances'
                ? 'border-indigo-600 text-indigo-600'
                : 'border-transparent text-slate-500 hover:text-slate-800'
            }`}
          >
            <FileText className="w-4 h-4" />
            Institutional Grievances ({totalCases})
          </button>
          <button
            onClick={() => setActiveTab('members')}
            className={`pb-3 px-4 text-sm font-bold border-b-2 transition-colors flex items-center gap-2 cursor-pointer ${
              activeTab === 'members'
                ? 'border-indigo-600 text-indigo-600'
                : 'border-transparent text-slate-500 hover:text-slate-800'
            }`}
          >
            <Users className="w-4 h-4" />
            Institutional Roster & Members
          </button>
          <button
            onClick={() => setActiveTab('analytics')}
            className={`pb-3 px-4 text-sm font-bold border-b-2 transition-colors flex items-center gap-2 cursor-pointer ${
              activeTab === 'analytics'
                ? 'border-indigo-600 text-indigo-600'
                : 'border-transparent text-slate-500 hover:text-slate-800'
            }`}
          >
            <BarChart3 className="w-4 h-4" />
            Compliance & Redressal Analytics
          </button>
        </div>

        {/* Tab 1: Grievances Management */}
        {activeTab === 'grievances' && (
          <div className="bg-white border border-slate-200 rounded-2xl shadow-sm p-6">
            {/* Filter Bar */}
            <div className="flex flex-col md:flex-row gap-3 mb-6">
              <div className="flex-1 relative">
                <Search className="w-4 h-4 absolute left-3.5 top-1/2 -translate-y-1/2 text-slate-400" />
                <input
                  type="text"
                  placeholder="Search by Case ID or subject keywords..."
                  value={searchQuery}
                  onChange={(e) => setSearchQuery(e.target.value)}
                  onKeyDown={(e) => e.key === 'Enter' && fetchCases()}
                  className="w-full pl-10 pr-4 py-2 text-sm border border-slate-200 rounded-xl focus:outline-none focus:ring-2 focus:ring-indigo-500"
                />
              </div>

              <div className="flex flex-wrap gap-2">
                <select
                  value={statusFilter}
                  onChange={(e) => { setStatusFilter(e.target.value); setCurrentPage(1); }}
                  className="px-3 py-2 text-xs font-semibold bg-white border border-slate-200 rounded-xl text-slate-700 focus:outline-none"
                >
                  <option value="">All Statuses</option>
                  <option value="SUBMITTED">SUBMITTED</option>
                  <option value="UNDER_INQUIRY">UNDER_INQUIRY</option>
                  <option value="HEARING_SCHEDULED">HEARING_SCHEDULED</option>
                  <option value="ACTION_TAKEN">ACTION_TAKEN</option>
                  <option value="RESOLVED">RESOLVED</option>
                  <option value="CLOSED">CLOSED</option>
                </select>

                <select
                  value={severityFilter}
                  onChange={(e) => { setSeverityFilter(e.target.value); setCurrentPage(1); }}
                  className="px-3 py-2 text-xs font-semibold bg-white border border-slate-200 rounded-xl text-slate-700 focus:outline-none"
                >
                  <option value="">All Severities</option>
                  <option value="LOW">LOW</option>
                  <option value="MEDIUM">MEDIUM</option>
                  <option value="HIGH">HIGH</option>
                  <option value="CRITICAL">CRITICAL</option>
                </select>

                <button
                  onClick={() => fetchCases()}
                  className="px-4 py-2 bg-indigo-600 text-white text-xs font-bold rounded-xl hover:bg-indigo-700 transition-colors shadow-sm cursor-pointer"
                >
                  Filter
                </button>
              </div>
            </div>

            {/* Cases Table */}
            {loadingCases ? (
              <div className="py-16 text-center text-slate-400 text-sm">Loading institutional grievances...</div>
            ) : cases.length === 0 ? (
              <div className="py-16 text-center text-slate-500 text-sm">
                No institutional grievances found matching the selected filters.
              </div>
            ) : (
              <div className="overflow-x-auto">
                <table className="w-full text-left text-sm text-slate-600">
                  <thead className="bg-slate-50 border-y border-slate-200 text-xs font-bold text-slate-500 uppercase tracking-wider">
                    <tr>
                      <th className="py-3 px-4">Case Reference</th>
                      <th className="py-3 px-4">Subject & Complainant</th>
                      <th className="py-3 px-4">Category</th>
                      <th className="py-3 px-4">Severity</th>
                      <th className="py-3 px-4">Status</th>
                      <th className="py-3 px-4">Assigned Proctor</th>
                      <th className="py-3 px-4 text-right">Actions</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-slate-100">
                    {cases.map((c) => {
                      const isConf = c.confidentiality_mode === 'CONFIDENTIAL' || c.confidentiality_mode === 'STRICT_CONFIDENTIAL';
                      return (
                        <tr key={c.id || c.case_id} className="hover:bg-slate-50/60 transition-colors">
                          <td className="py-3 px-4">
                            <span className="font-mono font-bold text-slate-900 block">{c.case_id}</span>
                            <span className="text-[11px] text-slate-400">
                              {c.created_at ? new Date(c.created_at).toLocaleDateString() : ''}
                            </span>
                          </td>
                          <td className="py-3 px-4 max-w-xs">
                            <div className="font-semibold text-slate-900 truncate">{c.subject}</div>
                            <div className="text-xs text-slate-500">
                              {c.is_anonymous ? (
                                <span className="inline-flex items-center gap-1 text-slate-400 font-mono text-[11px]">
                                  <Lock className="w-3 h-3" /> Protected Anonymous
                                </span>
                              ) : (
                                <span>{c.student_name || 'Complainant'} ({c.department || 'Student'})</span>
                              )}
                            </div>
                          </td>
                          <td className="py-3 px-4">
                            <span className="text-xs px-2 py-0.5 rounded bg-slate-100 text-slate-700 font-medium">
                              {c.category}
                            </span>
                          </td>
                          <td className="py-3 px-4">
                            <span className={`text-[11px] font-bold px-2 py-0.5 rounded-full ${
                              c.severity === 'CRITICAL' ? 'bg-rose-100 text-rose-800' :
                              c.severity === 'HIGH' ? 'bg-amber-100 text-amber-800' :
                              c.severity === 'MEDIUM' ? 'bg-blue-100 text-blue-800' :
                              'bg-slate-100 text-slate-700'
                            }`}>
                              {c.severity}
                            </span>
                          </td>
                          <td className="py-3 px-4">
                            <span className={`text-[11px] font-bold px-2.5 py-0.5 rounded-full ${
                              c.status === 'RESOLVED' || c.status === 'CLOSED' ? 'bg-emerald-100 text-emerald-800' :
                              c.status === 'HEARING_SCHEDULED' ? 'bg-purple-100 text-purple-800' :
                              c.status === 'ACTION_TAKEN' ? 'bg-indigo-100 text-indigo-800' :
                              c.status === 'UNDER_INQUIRY' ? 'bg-blue-100 text-blue-800' :
                              'bg-slate-100 text-slate-700'
                            }`}>
                              {c.status}
                            </span>
                          </td>
                          <td className="py-3 px-4 text-xs text-slate-600">
                            {c.assigned_proctor ? (
                              <span className="font-medium text-slate-800">{c.assigned_proctor}</span>
                            ) : (
                              <span className="text-amber-600 font-medium italic">Unassigned</span>
                            )}
                          </td>
                          <td className="py-3 px-4 text-right">
                            <button
                              onClick={() => setSelectedCase(c)}
                              className="px-3 py-1.5 text-xs font-bold text-indigo-600 hover:text-indigo-800 bg-indigo-50 hover:bg-indigo-100 rounded-lg transition-colors cursor-pointer"
                            >
                              Inspect
                            </button>
                          </td>
                        </tr>
                      );
                    })}
                  </tbody>
                </table>

                {/* Pagination */}
                <div className="flex items-center justify-between mt-4 pt-4 border-t border-slate-100 text-xs text-slate-500">
                  <div>
                    Page {currentPage} of {totalPages} ({totalCases} total records)
                  </div>
                  <div className="flex gap-2">
                    <button
                      disabled={currentPage <= 1}
                      onClick={() => setCurrentPage(p => Math.max(1, p - 1))}
                      className="px-3 py-1 border border-slate-200 rounded-lg hover:bg-slate-50 disabled:opacity-40 cursor-pointer"
                    >
                      <ChevronLeft className="w-3.5 h-3.5" />
                    </button>
                    <button
                      disabled={currentPage >= totalPages}
                      onClick={() => setCurrentPage(p => Math.min(totalPages, p + 1))}
                      className="px-3 py-1 border border-slate-200 rounded-lg hover:bg-slate-50 disabled:opacity-40 cursor-pointer"
                    >
                      <ChevronRight className="w-3.5 h-3.5" />
                    </button>
                  </div>
                </div>
              </div>
            )}
          </div>
        )}

        {/* Tab 2: Institutional Personnel & Roster */}
        {activeTab === 'members' && (
          <div className="bg-white border border-slate-200 rounded-2xl shadow-sm p-6">
            <div className="flex items-center justify-between mb-6">
              <div>
                <h2 className="text-lg font-bold text-slate-900">Institutional Membership Directory</h2>
                <p className="text-xs text-slate-500">Manage Proctorial Board and Committee Inquiry Officer authorization</p>
              </div>
              <button
                onClick={fetchMembers}
                className="px-3 py-1.5 text-xs font-semibold text-slate-700 bg-slate-100 hover:bg-slate-200 rounded-lg transition-colors cursor-pointer"
              >
                Refresh Roster
              </button>
            </div>

            {loadingMembers ? (
              <div className="py-16 text-center text-slate-400 text-sm">Loading member directory...</div>
            ) : members.length === 0 ? (
              <div className="py-16 text-center text-slate-500 text-sm">No members registered in this institution.</div>
            ) : (
              <div className="overflow-x-auto">
                <table className="w-full text-left text-sm text-slate-600">
                  <thead className="bg-slate-50 border-y border-slate-200 text-xs font-bold text-slate-500 uppercase">
                    <tr>
                      <th className="py-3 px-4">Member / Officer</th>
                      <th className="py-3 px-4">Role</th>
                      <th className="py-3 px-4">Department / Designation</th>
                      <th className="py-3 px-4">Account Status</th>
                      <th className="py-3 px-4 text-right">Administrative Action</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-slate-100">
                    {members.map((m) => (
                      <tr key={m.id || m.user_id} className="hover:bg-slate-50/60">
                        <td className="py-3 px-4">
                          <div className="font-semibold text-slate-900">{m.full_name || 'Institutional Officer'}</div>
                          <div className="text-xs text-slate-400 font-mono">{m.email || m.user_id}</div>
                        </td>
                        <td className="py-3 px-4">
                          <span className="text-xs font-bold uppercase px-2 py-0.5 rounded bg-slate-100 text-slate-700 font-mono">
                            {m.role}
                          </span>
                        </td>
                        <td className="py-3 px-4 text-xs">
                          {m.department || 'Campus Security'} ({m.designation || 'Officer'})
                        </td>
                        <td className="py-3 px-4">
                          <span className={`text-[11px] font-bold px-2.5 py-0.5 rounded-full ${
                            m.account_status === 'active' ? 'bg-emerald-100 text-emerald-800' :
                            m.account_status === 'suspended' ? 'bg-amber-100 text-amber-800' :
                            'bg-rose-100 text-rose-800'
                          }`}>
                            {m.account_status.toUpperCase()}
                          </span>
                        </td>
                        <td className="py-3 px-4 text-right">
                          <div className="flex items-center justify-end gap-2">
                            {m.account_status !== 'active' && (
                              <button
                                disabled={memberActionLoading === m.user_id}
                                onClick={() => handleStatusChange(m.user_id, 'active')}
                                className="px-2.5 py-1 text-xs font-bold text-emerald-700 bg-emerald-50 hover:bg-emerald-100 rounded-lg transition-colors cursor-pointer"
                              >
                                Activate
                              </button>
                            )}
                            {m.account_status !== 'suspended' && (
                              <button
                                disabled={memberActionLoading === m.user_id}
                                onClick={() => handleStatusChange(m.user_id, 'suspended')}
                                className="px-2.5 py-1 text-xs font-bold text-amber-700 bg-amber-50 hover:bg-amber-100 rounded-lg transition-colors cursor-pointer"
                              >
                                Suspend
                              </button>
                            )}
                            {m.account_status !== 'revoked' && (
                              <button
                                disabled={memberActionLoading === m.user_id}
                                onClick={() => handleStatusChange(m.user_id, 'revoked')}
                                className="px-2.5 py-1 text-xs font-bold text-rose-700 bg-rose-50 hover:bg-rose-100 rounded-lg transition-colors cursor-pointer"
                              >
                                Revoke
                              </button>
                            )}
                          </div>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </div>
        )}

        {/* Tab 3: Compliance & Redressal Analytics */}
        {activeTab === 'analytics' && (
          <div className="space-y-6">
            <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
              {/* Category Breakdown */}
              <div className="bg-white border border-slate-200 rounded-2xl shadow-sm p-6">
                <h3 className="text-sm font-bold text-slate-900 uppercase tracking-wide mb-4">
                  Grievances by Statutory Category
                </h3>
                {analytics?.by_category && Object.keys(analytics.by_category).length > 0 ? (
                  <div className="space-y-3">
                    {Object.entries(analytics.by_category).map(([cat, count]) => {
                      const total = analytics.total_cases || 1;
                      const pct = Math.round((count / total) * 100);
                      return (
                        <div key={cat}>
                          <div className="flex justify-between text-xs font-semibold text-slate-700 mb-1">
                            <span>{cat}</span>
                            <span>{count} cases ({pct}%)</span>
                          </div>
                          <div className="w-full bg-slate-100 h-2 rounded-full overflow-hidden">
                            <div className="bg-indigo-600 h-2 rounded-full" style={{ width: `${pct}%` }} />
                          </div>
                        </div>
                      );
                    })}
                  </div>
                ) : (
                  <p className="text-xs text-slate-400">No categorised grievance records available.</p>
                )}
              </div>

              {/* Severity & Resolution Breakdown */}
              <div className="bg-white border border-slate-200 rounded-2xl shadow-sm p-6">
                <h3 className="text-sm font-bold text-slate-900 uppercase tracking-wide mb-4">
                  Severity Distribution & SLA Metrics
                </h3>
                <div className="p-4 bg-slate-50 border border-slate-200 rounded-xl mb-4">
                  <div className="text-xs text-slate-500 font-medium">Average Turnaround SLA</div>
                  <div className="text-2xl font-black text-slate-900 font-mono mt-1">
                    {analytics?.avg_resolution_days ?? 0} Days
                  </div>
                  <span className="text-[11px] text-slate-500">
                    Calculated across {analytics?.resolved_count ?? 0} fully disposed matters
                  </span>
                </div>

                <div className="space-y-3">
                  {analytics?.by_severity && Object.entries(analytics.by_severity).map(([sev, count]) => (
                    <div key={sev} className="flex items-center justify-between text-xs">
                      <span className="font-bold text-slate-700">{sev}</span>
                      <span className="font-mono font-semibold px-2 py-0.5 rounded bg-slate-100 text-slate-800">
                        {count} matters
                      </span>
                    </div>
                  ))}
                </div>
              </div>
            </div>
          </div>
        )}
      </main>

      {/* Case Inspection Modal */}
      {selectedCase && (
        <div className="fixed inset-0 z-50 bg-slate-900/40 backdrop-blur-sm flex items-center justify-center p-4">
          <div className="bg-white rounded-2xl max-w-2xl w-full max-h-[85vh] overflow-y-auto p-6 shadow-xl border border-slate-200">
            <div className="flex items-start justify-between border-b border-slate-100 pb-4 mb-4">
              <div>
                <span className="text-xs font-mono font-bold text-indigo-600">{selectedCase.case_id}</span>
                <h3 className="text-lg font-bold text-slate-900 mt-0.5">{selectedCase.subject}</h3>
              </div>
              <button
                onClick={() => setSelectedCase(null)}
                className="text-slate-400 hover:text-slate-600 font-bold p-1 cursor-pointer"
              >
                ✕
              </button>
            </div>

            <div className="space-y-4 text-xs text-slate-700">
              <div className="grid grid-cols-2 gap-3 p-3 bg-slate-50 rounded-xl">
                <div>
                  <span className="text-slate-400 block">Category</span>
                  <span className="font-semibold text-slate-900">{selectedCase.category}</span>
                </div>
                <div>
                  <span className="text-slate-400 block">Status</span>
                  <span className="font-semibold text-slate-900">{selectedCase.status}</span>
                </div>
                <div>
                  <span className="text-slate-400 block">Complainant</span>
                  <span className="font-semibold text-slate-900">
                    {selectedCase.is_anonymous ? 'Protected Complainant' : selectedCase.student_name}
                  </span>
                </div>
                <div>
                  <span className="text-slate-400 block">Assigned Proctor</span>
                  <span className="font-semibold text-slate-900">{selectedCase.assigned_proctor || 'None'}</span>
                </div>
              </div>

              <div>
                <span className="font-bold text-slate-900 block mb-1">Grievance Description / Facts:</span>
                <p className="p-3 bg-slate-50 rounded-xl text-slate-700 leading-relaxed">
                  {selectedCase.description || 'No description provided.'}
                </p>
              </div>

              {selectedCase.proctor_notes && (
                <div>
                  <span className="font-bold text-slate-900 block mb-1">Proctorial Inquiry Notes:</span>
                  <p className="p-3 bg-amber-50/60 border border-amber-200 rounded-xl text-slate-800">
                    {selectedCase.proctor_notes}
                  </p>
                </div>
              )}

              {selectedCase.hearing_date && (
                <div className="p-3 bg-purple-50 border border-purple-200 rounded-xl flex items-center justify-between">
                  <div className="flex items-center gap-2">
                    <Calendar className="w-4 h-4 text-purple-700" />
                    <span className="font-semibold text-purple-900">Scheduled Inquiry Hearing</span>
                  </div>
                  <span className="font-mono font-bold text-purple-800">{selectedCase.hearing_date}</span>
                </div>
              )}

              {/* Supporting Documents */}
              {selectedCase.supporting_documents && selectedCase.supporting_documents.length > 0 && (
                <div>
                  <span className="font-bold text-slate-900 block mb-2">Supporting Case Documents:</span>
                  <div className="space-y-2">
                    {selectedCase.supporting_documents.map((doc: any, i: number) => (
                      <div key={i} className="flex items-center justify-between p-2.5 bg-slate-50 border border-slate-200 rounded-xl">
                        <span className="font-mono text-xs text-slate-700 truncate">{doc.file_name || doc.name || `Document ${i+1}`}</span>
                        <button
                          onClick={() => handleDownloadDoc(selectedCase.case_id, doc.document_id || doc.id || i.toString())}
                          className="px-2.5 py-1 bg-indigo-50 text-indigo-700 hover:bg-indigo-100 rounded text-xs font-bold flex items-center gap-1 cursor-pointer"
                        >
                          <ExternalLink className="w-3 h-3" /> Secure Access
                        </button>
                      </div>
                    ))}
                  </div>
                </div>
              )}
            </div>

            <div className="mt-6 pt-4 border-t border-slate-100 flex justify-end">
              <button
                onClick={() => setSelectedCase(null)}
                className="px-4 py-2 bg-slate-100 hover:bg-slate-200 text-slate-700 font-bold text-xs rounded-xl cursor-pointer"
              >
                Close Inspection
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

