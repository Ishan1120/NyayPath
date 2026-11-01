'use client';

import React, { useState, useEffect } from 'react';
import Link from 'next/link';
import { useRouter } from 'next/navigation';
import {
  Briefcase,
  Search,
  Filter,
  ArrowUpDown,
  FileText,
  Clock,
  CheckCircle2,
  AlertTriangle,
  ArrowRight,
  PlusCircle,
  RefreshCw,
  FolderOpen,
  ChevronLeft,
  ChevronRight,
  ShieldCheck,
  Calendar,
  Building,
  UserCheck,
  LogIn
} from 'lucide-react';
import { getCitizenCases, loginCitizen } from '@/lib/api';

export default function MyCasesPage() {
  const router = useRouter();
  const [cases, setCases] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  // Filters & Pagination State
  const [search, setSearch] = useState('');
  const [statusFilter, setStatusFilter] = useState('ALL');
  const [categoryFilter, setCategoryFilter] = useState('ALL');
  const [sortBy, setSortBy] = useState('created_at');
  const [sortOrder, setSortOrder] = useState('desc');
  const [page, setPage] = useState(1);
  const [totalPages, setTotalPages] = useState(1);
  const [totalCount, setTotalCount] = useState(0);

  // Quick Sign In modal if unauthenticated
  const [showAuthModal, setShowAuthModal] = useState(false);
  const [authEmail, setAuthEmail] = useState('student@nit.edu');
  const [authPassword, setAuthPassword] = useState('ProctorPass@2026!');
  const [authLoading, setAuthLoading] = useState(false);
  const [authError, setAuthError] = useState<string | null>(null);

  const fetchCases = async () => {
    setLoading(true);
    setError(null);
    try {
      const res = await getCitizenCases({
        status: statusFilter,
        category: categoryFilter,
        search: search.trim(),
        sort_by: sortBy,
        sort_order: sortOrder,
        page: page,
        limit: 10
      });
      setCases(res.cases || []);
      setTotalPages(res.total_pages || 1);
      setTotalCount(res.total || 0);
    } catch (err: any) {
      if (err?.response?.status === 401) {
        setError('UNAUTHENTICATED');
      } else {
        setError(err?.response?.data?.detail || 'Failed to retrieve cases.');
      }
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchCases();
  }, [statusFilter, categoryFilter, sortBy, sortOrder, page]);

  const handleSearchSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    setPage(1);
    fetchCases();
  };

  const handleQuickLogin = async (e: React.FormEvent) => {
    e.preventDefault();
    setAuthLoading(true);
    setAuthError(null);
    try {
      const res = await loginCitizen({ email: authEmail, password: authPassword });
      if (res?.token && res?.user) {
        localStorage.setItem('nyaypath_citizen_token', res.token);
        localStorage.setItem('nyaypath_user', JSON.stringify(res.user));
        setShowAuthModal(false);
        fetchCases();
      } else {
        setAuthError('Authentication failed: Invalid credentials.');
      }
    } catch (err: any) {
      setAuthError(err?.response?.data?.detail || 'Login failed.');
    } finally {
      setAuthLoading(false);
    }
  };

  const getStatusBadge = (status: string) => {
    const s = (status || 'SUBMITTED').toUpperCase();
    switch (s) {
      case 'RESOLVED':
      case 'CLOSED':
      case 'COMPLETED':
        return (
          <span className="inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full text-[11px] font-bold bg-emerald-50 text-emerald-700 border border-emerald-200">
            <CheckCircle2 className="w-3 h-3" />
            <span>{s}</span>
          </span>
        );
      case 'UNDER_INQUIRY':
      case 'IN_REVIEW':
      case 'IN_PROGRESS':
        return (
          <span className="inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full text-[11px] font-bold bg-blue-50 text-blue-700 border border-blue-200">
            <Clock className="w-3 h-3" />
            <span>{s}</span>
          </span>
        );
      case 'HEARING_SCHEDULED':
        return (
          <span className="inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full text-[11px] font-bold bg-purple-50 text-purple-700 border border-purple-200">
            <AlertTriangle className="w-3 h-3" />
            <span>HEARING SCHEDULED</span>
          </span>
        );
      case 'ACTION_TAKEN':
        return (
          <span className="inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full text-[11px] font-bold bg-teal-50 text-teal-700 border border-teal-200">
            <CheckCircle2 className="w-3 h-3" />
            <span>ACTION TAKEN</span>
          </span>
        );
      default:
        return (
          <span className="inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full text-[11px] font-bold bg-amber-50 text-amber-700 border border-amber-200">
            <Clock className="w-3 h-3" />
            <span>{s}</span>
          </span>
        );
    }
  };

  return (
    <div className="min-h-screen bg-gradient-to-b from-slate-50 via-white to-slate-50 pt-20 pb-16 font-sans">
      <div className="max-w-6xl mx-auto px-4 sm:px-6 lg:px-8">
        
        {/* Header Breadcrumbs & Action Button */}
        <div className="flex flex-col sm:flex-row sm:items-center justify-between pb-6 border-b border-slate-200 gap-4">
          <div>
            <div className="flex items-center gap-2 text-xs font-bold uppercase tracking-wider text-court-maroon mb-1">
              <Link href="/dashboard" className="hover:underline flex items-center gap-1">
                <span>Citizen Dashboard</span>
              </Link>
              <span>/</span>
              <span className="text-slate-500">My Cases</span>
            </div>
            <h1 className="text-2xl sm:text-3xl font-extrabold text-slate-900 tracking-tight">
              My Cases Workspace
            </h1>
            <p className="text-sm text-slate-600 mt-0.5">
              Comprehensive list of all your filed legal grievances, RTIs, and petitions.
            </p>
          </div>

          <div className="flex items-center gap-2.5 self-start sm:self-auto">
            <button
              onClick={fetchCases}
              disabled={loading}
              className="p-2.5 rounded-xl border border-slate-200 bg-white hover:bg-slate-50 text-slate-600 transition-colors cursor-pointer"
              title="Refresh case list"
            >
              <RefreshCw className={`w-4 h-4 ${loading ? 'animate-spin' : ''}`} />
            </button>
            <Link
              href="/dashboard?tab=assistant"
              className="px-4 py-2.5 rounded-xl bg-gradient-to-r from-court-maroon to-rose-700 text-white font-bold text-xs shadow-md hover:from-rose-700 hover:to-rose-800 transition-all flex items-center gap-2 cursor-pointer shrink-0"
            >
              <PlusCircle className="w-4 h-4" />
              <span>File New Case</span>
            </Link>
          </div>
        </div>

        {/* Unauthenticated Alert Banner */}
        {error === 'UNAUTHENTICATED' && (
          <div className="mt-6 p-6 rounded-3xl bg-gradient-to-r from-rose-900 via-court-maroon to-slate-900 text-white shadow-xl flex flex-col sm:flex-row items-start sm:items-center justify-between gap-4">
            <div>
              <h3 className="font-bold text-lg">Citizen Authentication Required</h3>
              <p className="text-xs text-rose-100 max-w-xl mt-1">
                You must be logged in to view your filed grievances and official records. Sign in with your registered email or demo account.
              </p>
            </div>
            <button
              onClick={() => setShowAuthModal(true)}
              className="px-5 py-2.5 rounded-xl bg-white text-court-maroon hover:bg-rose-50 font-bold text-xs shadow-md transition-all shrink-0 cursor-pointer flex items-center gap-2"
            >
              <LogIn className="w-4 h-4" />
              <span>Sign In Now</span>
            </button>
          </div>
        )}

        {/* Filter & Search Bar */}
        <div className="mt-6 p-4 rounded-3xl bg-white border border-slate-200 shadow-sm space-y-4">
          {/* Search Row */}
          <form onSubmit={handleSearchSubmit} className="flex gap-2">
            <div className="relative flex-1">
              <Search className="w-4 h-4 text-slate-400 absolute left-3.5 top-1/2 -translate-y-1/2" />
              <input
                type="text"
                value={search}
                onChange={(e) => setSearch(e.target.value)}
                placeholder="Search by Case ID, subject, or keywords..."
                className="w-full pl-10 pr-4 py-2 rounded-xl border border-slate-200 text-xs focus:ring-2 focus:ring-court-maroon focus:outline-none"
              />
            </div>
            <button
              type="submit"
              className="px-4 py-2 rounded-xl bg-slate-900 hover:bg-slate-800 text-white text-xs font-bold transition-all shadow-sm shrink-0"
            >
              Search
            </button>
            {search && (
              <button
                type="button"
                onClick={() => {
                  setSearch('');
                  setPage(1);
                  fetchCases();
                }}
                className="px-3 py-2 rounded-xl border border-slate-200 hover:bg-slate-100 text-slate-600 text-xs font-semibold"
              >
                Clear
              </button>
            )}
          </form>

          {/* Status Tabs */}
          <div className="flex items-center gap-1.5 overflow-x-auto pb-1 text-xs">
            <span className="text-slate-400 font-bold text-[11px] uppercase mr-1 flex items-center gap-1 shrink-0">
              <Filter className="w-3 h-3" />
              <span>Status:</span>
            </span>
            {[
              { label: 'All', value: 'ALL' },
              { label: 'Active', value: 'ACTIVE' },
              { label: 'Submitted', value: 'SUBMITTED' },
              { label: 'Under Inquiry', value: 'UNDER_INQUIRY' },
              { label: 'Hearing Scheduled', value: 'HEARING_SCHEDULED' },
              { label: 'Resolved / Closed', value: 'RESOLVED' }
            ].map((tab) => (
              <button
                key={tab.value}
                onClick={() => {
                  setStatusFilter(tab.value);
                  setPage(1);
                }}
                className={`px-3 py-1.5 rounded-full font-bold whitespace-nowrap transition-colors cursor-pointer text-xs ${
                  statusFilter === tab.value
                    ? 'bg-court-maroon text-white shadow-sm'
                    : 'bg-slate-100 text-slate-600 hover:bg-slate-200'
                }`}
              >
                {tab.label}
              </button>
            ))}
          </div>

          {/* Category & Sorting Controls */}
          <div className="flex flex-wrap items-center justify-between gap-3 pt-3 border-t border-slate-100 text-xs text-slate-600">
            <div className="flex items-center gap-3 flex-wrap">
              <div className="flex items-center gap-1.5">
                <span className="font-semibold text-slate-500">Category:</span>
                <select
                  value={categoryFilter}
                  onChange={(e) => {
                    setCategoryFilter(e.target.value);
                    setPage(1);
                  }}
                  className="px-2.5 py-1 rounded-lg border border-slate-200 bg-white font-medium focus:ring-1 focus:ring-court-maroon focus:outline-none text-xs"
                >
                  <option value="ALL">All Categories</option>
                  <option value="Academic">Academic</option>
                  <option value="Hostel">Hostel</option>
                  <option value="Infrastructure">Infrastructure</option>
                  <option value="Disciplinary">Disciplinary</option>
                  <option value="RTI">RTI Inquiries</option>
                  <option value="Consumer">Consumer Complaints</option>
                </select>
              </div>

              <div className="flex items-center gap-1.5">
                <span className="font-semibold text-slate-500">Sort By:</span>
                <select
                  value={sortBy}
                  onChange={(e) => {
                    setSortBy(e.target.value);
                    setPage(1);
                  }}
                  className="px-2.5 py-1 rounded-lg border border-slate-200 bg-white font-medium focus:ring-1 focus:ring-court-maroon focus:outline-none text-xs"
                >
                  <option value="created_at">Date Created</option>
                  <option value="updated_at">Last Updated</option>
                  <option value="status">Status</option>
                  <option value="category">Category</option>
                </select>
                <button
                  type="button"
                  onClick={() => {
                    setSortOrder(sortOrder === 'asc' ? 'desc' : 'asc');
                    setPage(1);
                  }}
                  className="p-1 rounded-lg border border-slate-200 hover:bg-slate-100 text-slate-600"
                  title={`Order: ${sortOrder.toUpperCase()}`}
                >
                  <ArrowUpDown className="w-3.5 h-3.5" />
                </button>
              </div>
            </div>

            <div className="text-slate-500 font-medium">
              Showing <span className="font-bold text-slate-900">{cases.length}</span> of{' '}
              <span className="font-bold text-slate-900">{totalCount}</span> cases
            </div>
          </div>
        </div>

        {/* Case List Content */}
        <div className="mt-6 space-y-4">
          {loading ? (
            <div className="p-16 rounded-3xl bg-white border border-slate-200 text-center flex flex-col items-center justify-center">
              <RefreshCw className="w-8 h-8 animate-spin text-court-maroon mb-3" />
              <p className="text-sm font-bold text-slate-700">Loading your cases...</p>
              <p className="text-xs text-slate-400 mt-1">Retrieving authoritative records from database</p>
            </div>
          ) : error && error !== 'UNAUTHENTICATED' ? (
            <div className="p-8 rounded-3xl bg-rose-50 border border-rose-200 text-rose-800 text-center">
              <AlertTriangle className="w-8 h-8 mx-auto text-rose-600 mb-2" />
              <h3 className="font-bold text-sm">Error Loading Cases</h3>
              <p className="text-xs text-rose-600 mt-1">{error}</p>
              <button
                onClick={fetchCases}
                className="mt-4 px-4 py-2 rounded-xl bg-rose-700 text-white text-xs font-bold hover:bg-rose-800 transition-colors"
              >
                Retry
              </button>
            </div>
          ) : cases.length > 0 ? (
            cases.map((c) => (
              <div
                key={c.case_id}
                className="p-5 rounded-3xl bg-white border border-slate-200/90 shadow-sm hover:shadow-md transition-all flex flex-col md:flex-row items-start md:items-center justify-between gap-4"
              >
                <div className="flex items-start gap-4 flex-1">
                  <div className="p-3 rounded-2xl bg-rose-50 text-court-maroon border border-rose-100 shrink-0">
                    <FileText className="w-5 h-5" />
                  </div>
                  <div className="space-y-1.5 flex-1">
                    <div className="flex items-center gap-2 flex-wrap">
                      <span className="font-mono text-xs font-extrabold text-slate-900 bg-slate-100 px-2.5 py-0.5 rounded-md border border-slate-200">
                        {c.case_id}
                      </span>
                      {getStatusBadge(c.status)}
                      <span className="px-2.5 py-0.5 rounded-full text-[10px] font-semibold bg-slate-100 text-slate-700 border border-slate-200">
                        {c.category || 'General'}
                      </span>
                      {c.severity && c.severity !== 'NORMAL' && (
                        <span className="px-2 py-0.5 rounded-full text-[10px] font-bold uppercase bg-rose-100 text-rose-800 border border-rose-200">
                          {c.severity}
                        </span>
                      )}
                    </div>

                    <h3 className="text-sm font-bold text-slate-900 hover:text-court-maroon transition-colors line-clamp-1">
                      <Link href={`/dashboard/my-cases/${encodeURIComponent(c.case_id)}`}>
                        {c.subject}
                      </Link>
                    </h3>

                    <p className="text-xs text-slate-500 line-clamp-2 leading-relaxed">
                      {c.description}
                    </p>

                    <div className="flex items-center gap-4 text-[11px] text-slate-400 flex-wrap pt-1">
                      <span className="flex items-center gap-1">
                        <Calendar className="w-3 h-3 text-slate-400" />
                        <span>Filed: {c.created_at ? new Date(c.created_at).toLocaleDateString() : 'N/A'}</span>
                      </span>
                      {c.department && (
                        <span className="flex items-center gap-1">
                          <Building className="w-3 h-3 text-slate-400" />
                          <span>Dept: {c.department}</span>
                        </span>
                      )}
                      {c.documents_count > 0 && (
                        <span className="flex items-center gap-1 text-slate-600 font-semibold">
                          <FileText className="w-3 h-3 text-court-maroon" />
                          <span>{c.documents_count} Document(s)</span>
                        </span>
                      )}
                    </div>
                  </div>
                </div>

                <div className="flex items-center gap-3 shrink-0 self-end md:self-auto pt-2 md:pt-0 border-t md:border-t-0 border-slate-100 w-full md:w-auto justify-end">
                  <Link
                    href={`/dashboard/my-cases/${encodeURIComponent(c.case_id)}`}
                    className="px-4 py-2 rounded-xl bg-slate-900 hover:bg-slate-800 text-white text-xs font-bold transition-all shadow-sm flex items-center gap-1.5"
                  >
                    <span>View Details</span>
                    <ArrowRight className="w-3.5 h-3.5" />
                  </Link>
                </div>
              </div>
            ))
          ) : (
            <div className="p-16 rounded-3xl bg-white border border-dashed border-slate-200 text-center">
              <div className="w-14 h-14 rounded-full bg-rose-50 text-court-maroon mx-auto flex items-center justify-center mb-3">
                <FolderOpen className="w-7 h-7" />
              </div>
              <h3 className="text-base font-bold text-slate-900">No cases match your criteria</h3>
              <p className="text-xs text-slate-500 max-w-md mx-auto mt-1 leading-relaxed">
                {search || statusFilter !== 'ALL' || categoryFilter !== 'ALL'
                  ? 'No grievances or legal petitions matched your active filters. Try clearing your search or status selection.'
                  : 'You have not submitted any cases yet. You can file a campus grievance, statutory RTI inquiry, or consumer petition with AI assistance.'}
              </p>
              <div className="mt-5 flex items-center justify-center gap-3">
                {(search || statusFilter !== 'ALL' || categoryFilter !== 'ALL') ? (
                  <button
                    onClick={() => {
                      setSearch('');
                      setStatusFilter('ALL');
                      setCategoryFilter('ALL');
                      setPage(1);
                    }}
                    className="px-4 py-2 rounded-xl bg-slate-100 hover:bg-slate-200 text-slate-700 text-xs font-bold transition-colors cursor-pointer"
                  >
                    Reset All Filters
                  </button>
                ) : (
                  <Link
                    href="/dashboard?tab=assistant"
                    className="px-5 py-2.5 rounded-xl bg-gradient-to-r from-court-maroon to-rose-700 text-white text-xs font-bold shadow-md hover:from-rose-700 hover:to-rose-800 transition-all"
                  >
                    File New Grievance
                  </Link>
                )}
              </div>
            </div>
          )}
        </div>

        {/* Pagination Controls */}
        {totalPages > 1 && (
          <div className="mt-8 flex items-center justify-between border-t border-slate-200 pt-4">
            <button
              onClick={() => setPage(Math.max(1, page - 1))}
              disabled={page <= 1 || loading}
              className="px-3.5 py-1.5 rounded-xl border border-slate-200 text-xs font-bold text-slate-700 hover:bg-slate-50 disabled:opacity-50 disabled:cursor-not-allowed flex items-center gap-1 cursor-pointer"
            >
              <ChevronLeft className="w-3.5 h-3.5" />
              <span>Previous</span>
            </button>

            <span className="text-xs text-slate-500 font-medium">
              Page <span className="font-bold text-slate-900">{page}</span> of{' '}
              <span className="font-bold text-slate-900">{totalPages}</span>
            </span>

            <button
              onClick={() => setPage(Math.min(totalPages, page + 1))}
              disabled={page >= totalPages || loading}
              className="px-3.5 py-1.5 rounded-xl border border-slate-200 text-xs font-bold text-slate-700 hover:bg-slate-50 disabled:opacity-50 disabled:cursor-not-allowed flex items-center gap-1 cursor-pointer"
            >
              <span>Next</span>
              <ChevronRight className="w-3.5 h-3.5" />
            </button>
          </div>
        )}

      </div>

      {/* Sign-In Modal */}
      {showAuthModal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 backdrop-blur-sm p-4 font-sans">
          <div className="bg-white rounded-3xl max-w-md w-full p-6 shadow-2xl border border-slate-200">
            <div className="flex items-center justify-between pb-4 border-b border-slate-100">
              <div className="flex items-center gap-2">
                <ShieldCheck className="w-5 h-5 text-court-maroon" />
                <h3 className="font-bold text-slate-900 text-base">Sign In to Citizen Workspace</h3>
              </div>
              <button
                onClick={() => setShowAuthModal(false)}
                className="text-slate-400 hover:text-slate-600 text-sm font-bold"
              >
                ✕
              </button>
            </div>

            <form onSubmit={handleQuickLogin} className="mt-4 space-y-4">
              <div>
                <label className="block text-xs font-bold text-slate-700 mb-1">Email Address</label>
                <input
                  type="email"
                  value={authEmail}
                  onChange={(e) => setAuthEmail(e.target.value)}
                  className="w-full px-3.5 py-2.5 rounded-xl border border-slate-300 text-xs focus:ring-2 focus:ring-court-maroon focus:outline-none"
                  placeholder="student@nit.edu or citizen@nyaypath.in"
                  required
                />
              </div>

              <div>
                <label className="block text-xs font-bold text-slate-700 mb-1">Password</label>
                <input
                  type="password"
                  value={authPassword}
                  onChange={(e) => setAuthPassword(e.target.value)}
                  className="w-full px-3.5 py-2.5 rounded-xl border border-slate-300 text-xs focus:ring-2 focus:ring-court-maroon focus:outline-none"
                  placeholder="Enter password"
                  required
                />
              </div>

              {authError && (
                <div className="p-3 rounded-xl bg-rose-50 border border-rose-200 text-rose-700 text-xs">
                  {authError}
                </div>
              )}

              <div className="p-3 rounded-2xl bg-slate-50 border border-slate-200 text-xs space-y-1.5">
                <span className="font-bold text-slate-700 block text-[11px] uppercase tracking-wider">
                  Test Credentials (Click to select)
                </span>
                <div className="flex gap-2">
                  <button
                    type="button"
                    onClick={() => {
                      setAuthEmail('student@nit.edu');
                      setAuthPassword('ProctorPass@2026!');
                    }}
                    className="px-2.5 py-1 rounded-lg bg-white border border-slate-200 text-slate-800 text-[11px] font-semibold hover:border-court-maroon"
                  >
                    Student (Aarav)
                  </button>
                  <button
                    type="button"
                    onClick={() => {
                      setAuthEmail('citizen@nyaypath.in');
                      setAuthPassword('ProctorPass@2026!');
                    }}
                    className="px-2.5 py-1 rounded-lg bg-white border border-slate-200 text-slate-800 text-[11px] font-semibold hover:border-court-maroon"
                  >
                    Citizen (Priya)
                  </button>
                </div>
              </div>

              <div className="flex items-center justify-end gap-2 pt-2">
                <button
                  type="button"
                  onClick={() => setShowAuthModal(false)}
                  className="px-4 py-2 rounded-xl text-slate-600 text-xs font-semibold hover:bg-slate-100"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  disabled={authLoading}
                  className="px-5 py-2 rounded-xl bg-gradient-to-r from-court-maroon to-rose-700 text-white text-xs font-bold hover:from-rose-700 hover:to-rose-800 transition-all flex items-center gap-1.5 cursor-pointer shadow-md"
                >
                  {authLoading && <RefreshCw className="w-3.5 h-3.5 animate-spin" />}
                  <span>Sign In</span>
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

    </div>
  );
}
