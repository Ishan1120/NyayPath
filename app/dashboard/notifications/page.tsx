'use client';

import React, { useState, useEffect } from 'react';
import Link from 'next/link';
import { useRouter } from 'next/navigation';
import {
  Bell,
  BellRing,
  CheckCircle2,
  Clock,
  FileText,
  Scale,
  AlertTriangle,
  ArrowRight,
  Trash2,
  Check,
  CheckCheck,
  RefreshCw,
  Search,
  Filter,
  ExternalLink,
  ChevronLeft,
  ShieldCheck,
  LogIn,
  MessageSquare,
  Zap
} from 'lucide-react';
import {
  getUserNotifications,
  getUnreadNotificationCount,
  markNotificationAsRead,
  markAllNotificationsAsRead,
  deleteNotification,
  loginCitizen,
  CaseNotification
} from '@/lib/api';

export default function NotificationsPage() {
  const router = useRouter();
  const [notifications, setNotifications] = useState<CaseNotification[]>([]);
  const [loading, setLoading] = useState(true);
  const [unreadCount, setUnreadCount] = useState(0);
  const [filterTab, setFilterTab] = useState<'ALL' | 'UNREAD' | 'READ'>('ALL');
  const [searchQuery, setSearchQuery] = useState('');
  const [error, setError] = useState<string | null>(null);
  const [actionLoading, setActionLoading] = useState<string | null>(null);

  // Unauthenticated fallback state
  const [showAuthModal, setShowAuthModal] = useState(false);
  const [authEmail, setAuthEmail] = useState('student@nit.edu');
  const [authPassword, setAuthPassword] = useState('ProctorPass@2026!');
  const [authLoading, setAuthLoading] = useState(false);
  const [authError, setAuthError] = useState<string | null>(null);

  const fetchNotifications = async () => {
    setLoading(true);
    setError(null);
    try {
      const isReadParam =
        filterTab === 'UNREAD' ? false : filterTab === 'READ' ? true : undefined;
      const data = await getUserNotifications({
        is_read: isReadParam,
        limit: 50
      });
      setNotifications(data.notifications || []);
      setUnreadCount(Number(data.unread_count || 0));
    } catch (err: any) {
      if (err?.response?.status === 401) {
        setError('UNAUTHENTICATED');
      } else {
        setError(err?.response?.data?.detail || 'Failed to load notifications.');
      }
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchNotifications();
  }, [filterTab]);

  const handleMarkOneRead = async (id: string, e?: React.MouseEvent) => {
    if (e) e.stopPropagation();
    setActionLoading(id);
    try {
      await markNotificationAsRead(id);
      setNotifications(prev =>
        prev.map(n => (n.id === id ? { ...n, is_read: true } : n))
      );
      setUnreadCount(prev => Math.max(0, prev - 1));
    } catch {
      // Fail silently
    } finally {
      setActionLoading(null);
    }
  };

  const handleMarkAllRead = async () => {
    setActionLoading('ALL');
    try {
      await markAllNotificationsAsRead();
      setNotifications(prev => prev.map(n => ({ ...n, is_read: true })));
      setUnreadCount(0);
    } catch {
      // Fail silently
    } finally {
      setActionLoading(null);
    }
  };

  const handleDelete = async (id: string, e: React.MouseEvent) => {
    e.stopPropagation();
    setActionLoading(`del-${id}`);
    try {
      await deleteNotification(id);
      setNotifications(prev => prev.filter(n => n.id !== id));
      // Re-fetch unread count
      const unreadData = await getUnreadNotificationCount();
      setUnreadCount(Number(unreadData.unread_count || 0));
    } catch {
      // Fail silently
    } finally {
      setActionLoading(null);
    }
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
        setError(null);
        fetchNotifications();
      } else {
        setAuthError('Authentication failed: Invalid credentials.');
      }
    } catch (err: any) {
      setAuthError(err?.response?.data?.detail || 'Login failed.');
    } finally {
      setAuthLoading(false);
    }
  };

  const formatDateTime = (iso?: string) => {
    if (!iso) return '';
    try {
      const d = new Date(iso);
      return d.toLocaleDateString('en-IN', {
        day: 'numeric',
        month: 'short',
        year: 'numeric',
        hour: '2-digit',
        minute: '2-digit'
      });
    } catch {
      return '';
    }
  };

  const formatRelativeTime = (iso?: string) => {
    if (!iso) return '';
    try {
      const diffMs = Date.now() - new Date(iso).getTime();
      const diffSec = Math.floor(diffMs / 1000);
      if (diffSec < 60) return 'Just now';
      const diffMin = Math.floor(diffSec / 60);
      if (diffMin < 60) return `${diffMin}m ago`;
      const diffHr = Math.floor(diffMin / 60);
      if (diffHr < 24) return `${diffHr}h ago`;
      const diffDays = Math.floor(diffHr / 24);
      return `${diffDays}d ago`;
    } catch {
      return '';
    }
  };

  const getEventIcon = (eventType: string) => {
    switch (eventType) {
      case 'CASE_SUBMITTED':
        return <FileText className="w-5 h-5 text-blue-600" />;
      case 'HEARING_SCHEDULED':
        return <Clock className="w-5 h-5 text-purple-600" />;
      case 'CASE_WITHDRAWN':
        return <AlertTriangle className="w-5 h-5 text-amber-600" />;
      case 'CITIZEN_REMARK_ADDED':
        return <MessageSquare className="w-5 h-5 text-cyan-600" />;
      case 'EXPEDITE_REQUESTED':
        return <Zap className="w-5 h-5 text-orange-600" />;
      case 'CASE_RESOLVED':
        return <CheckCircle2 className="w-5 h-5 text-emerald-600" />;
      case 'CASE_STATUS_UPDATED':
      default:
        return <Scale className="w-5 h-5 text-indigo-600" />;
    }
  };

  const filteredNotifications = notifications.filter(n => {
    if (!searchQuery.trim()) return true;
    const q = searchQuery.toLowerCase();
    return (
      n.title.toLowerCase().includes(q) ||
      n.message.toLowerCase().includes(q) ||
      (n.related_case_id && n.related_case_id.toLowerCase().includes(q))
    );
  });

  return (
    <div className="min-h-screen bg-gradient-to-b from-slate-50 via-white to-slate-50 pt-24 pb-16 px-4 sm:px-6 lg:px-8 font-sans">
      <div className="max-w-5xl mx-auto space-y-6">
        {/* Navigation Breadcrumb */}
        <div className="flex items-center gap-2 text-xs text-slate-500 font-medium">
          <Link href="/dashboard" className="hover:text-court-maroon transition-colors">
            Dashboard
          </Link>
          <span>/</span>
          <span className="text-slate-800 font-semibold">Notifications</span>
        </div>

        {/* Top Header Card */}
        <div className="bg-white rounded-2xl border border-slate-200/80 p-6 sm:p-8 shadow-sm flex flex-col md:flex-row md:items-center justify-between gap-6">
          <div className="space-y-1">
            <div className="flex items-center gap-3">
              <div className="p-2.5 rounded-xl bg-rose-50 border border-rose-200 text-court-maroon">
                <BellRing className="w-6 h-6" />
              </div>
              <div>
                <h1 className="text-2xl font-bold text-slate-900 tracking-tight">
                  Notification Center
                </h1>
                <p className="text-xs text-slate-500">
                  Real-time updates regarding your filed cases, hearings, and status milestones.
                </p>
              </div>
            </div>
          </div>

          <div className="flex items-center gap-3 shrink-0">
            {unreadCount > 0 && (
              <button
                onClick={handleMarkAllRead}
                disabled={actionLoading === 'ALL'}
                className="inline-flex items-center gap-1.5 px-3.5 py-2 rounded-xl text-xs font-semibold bg-rose-50 hover:bg-rose-100 text-court-maroon border border-rose-200 transition-colors cursor-pointer disabled:opacity-50"
              >
                <CheckCheck className="w-4 h-4" />
                <span>Mark All Read</span>
              </button>
            )}
            <button
              onClick={fetchNotifications}
              className="inline-flex items-center gap-1.5 px-3.5 py-2 rounded-xl text-xs font-semibold bg-slate-100 hover:bg-slate-200 text-slate-700 transition-colors cursor-pointer"
            >
              <RefreshCw className={`w-3.5 h-3.5 ${loading ? 'animate-spin' : ''}`} />
              <span>Refresh</span>
            </button>
          </div>
        </div>

        {/* Filter Controls & Search */}
        <div className="bg-white rounded-2xl border border-slate-200/80 p-4 shadow-sm flex flex-col sm:flex-row items-center justify-between gap-4">
          {/* Tabs */}
          <div className="flex items-center gap-1 p-1 bg-slate-100/80 rounded-xl w-full sm:w-auto">
            <button
              onClick={() => setFilterTab('ALL')}
              className={`px-4 py-1.5 rounded-lg text-xs font-bold transition-all cursor-pointer ${
                filterTab === 'ALL'
                  ? 'bg-white text-slate-900 shadow-sm'
                  : 'text-slate-600 hover:text-slate-900'
              }`}
            >
              All Updates
            </button>
            <button
              onClick={() => setFilterTab('UNREAD')}
              className={`px-4 py-1.5 rounded-lg text-xs font-bold transition-all cursor-pointer flex items-center gap-1.5 ${
                filterTab === 'UNREAD'
                  ? 'bg-white text-rose-700 shadow-sm'
                  : 'text-slate-600 hover:text-slate-900'
              }`}
            >
              <span>Unread</span>
              {unreadCount > 0 && (
                <span className="bg-rose-600 text-white text-[10px] px-1.5 py-0.2 rounded-full font-bold">
                  {unreadCount}
                </span>
              )}
            </button>
            <button
              onClick={() => setFilterTab('READ')}
              className={`px-4 py-1.5 rounded-lg text-xs font-bold transition-all cursor-pointer ${
                filterTab === 'READ'
                  ? 'bg-white text-slate-900 shadow-sm'
                  : 'text-slate-600 hover:text-slate-900'
              }`}
            >
              Read
            </button>
          </div>

          {/* Search Box */}
          <div className="relative w-full sm:w-64">
            <Search className="w-4 h-4 text-slate-400 absolute left-3 top-2.5" />
            <input
              type="text"
              value={searchQuery}
              onChange={e => setSearchQuery(e.target.value)}
              placeholder="Search notifications..."
              className="w-full pl-9 pr-3 py-1.5 text-xs bg-slate-50 border border-slate-200 rounded-xl focus:bg-white focus:outline-none focus:ring-2 focus:ring-court-maroon/20 focus:border-court-maroon transition-all"
            />
          </div>
        </div>

        {/* Content Body */}
        {error === 'UNAUTHENTICATED' ? (
          <div className="bg-white rounded-2xl border border-rose-200 p-8 text-center space-y-4">
            <ShieldCheck className="w-10 h-10 text-rose-600 mx-auto" />
            <div>
              <h3 className="text-base font-bold text-slate-900">Authentication Required</h3>
              <p className="text-xs text-slate-500 mt-1 max-w-md mx-auto">
                Sign in with your verified credentials to access confidential case alerts and notifications.
              </p>
            </div>
            <button
              onClick={() => setShowAuthModal(true)}
              className="inline-flex items-center gap-2 px-4 py-2 rounded-xl text-xs font-bold bg-court-maroon text-white hover:bg-rose-800 transition-colors cursor-pointer"
            >
              <LogIn className="w-4 h-4" />
              <span>Sign In to Access Notifications</span>
            </button>
          </div>
        ) : loading ? (
          <div className="space-y-3">
            {[1, 2, 3].map(i => (
              <div
                key={i}
                className="bg-white rounded-2xl border border-slate-200 p-5 animate-pulse flex items-start gap-4"
              >
                <div className="w-10 h-10 rounded-xl bg-slate-100" />
                <div className="flex-1 space-y-2">
                  <div className="h-4 bg-slate-100 rounded w-1/3" />
                  <div className="h-3 bg-slate-100 rounded w-2/3" />
                </div>
              </div>
            ))}
          </div>
        ) : filteredNotifications.length === 0 ? (
          <div className="bg-white rounded-2xl border border-slate-200/80 p-12 text-center space-y-3">
            <Bell className="w-10 h-10 text-slate-300 mx-auto" />
            <h3 className="text-base font-bold text-slate-800">No Notifications Found</h3>
            <p className="text-xs text-slate-500 max-w-sm mx-auto">
              {filterTab === 'UNREAD'
                ? "You're all caught up! There are no unread notifications right now."
                : 'No notification records match your current filter.'}
            </p>
          </div>
        ) : (
          <div className="space-y-3">
            {filteredNotifications.map(item => (
              <div
                key={item.id}
                className={`bg-white rounded-2xl border transition-all p-5 shadow-sm hover:shadow-md flex flex-col sm:flex-row items-start gap-4 ${
                  !item.is_read
                    ? 'border-rose-200/80 bg-rose-50/20'
                    : 'border-slate-200/80'
                }`}
              >
                {/* Event Icon */}
                <div className="p-3 rounded-xl bg-slate-50 border border-slate-100 shrink-0">
                  {getEventIcon(item.event_type)}
                </div>

                {/* Content */}
                <div className="flex-1 min-w-0 space-y-1.5">
                  <div className="flex flex-wrap items-center justify-between gap-2">
                    <div className="flex items-center gap-2">
                      {!item.is_read && (
                        <span className="w-2 h-2 rounded-full bg-rose-600 animate-ping" />
                      )}
                      <h4 className="text-sm font-bold text-slate-900 tracking-tight">
                        {item.title}
                      </h4>
                    </div>
                    <div className="flex items-center gap-2 text-[11px] text-slate-400">
                      <span>{formatRelativeTime(item.created_at)}</span>
                      <span>•</span>
                      <span>{formatDateTime(item.created_at)}</span>
                    </div>
                  </div>

                  <p className="text-xs text-slate-600 leading-relaxed">
                    {item.message}
                  </p>

                  <div className="pt-2 flex flex-wrap items-center justify-between gap-3">
                    {/* Case Link */}
                    {item.related_case_id ? (
                      <Link
                        href={`/dashboard/my-cases?case_id=${encodeURIComponent(item.related_case_id)}`}
                        className="inline-flex items-center gap-1.5 text-xs font-mono font-semibold text-court-maroon hover:text-rose-700 bg-rose-50 border border-rose-200/70 px-2.5 py-1 rounded-lg transition-colors"
                      >
                        <span>Case #{item.related_case_id}</span>
                        <ArrowRight className="w-3 h-3" />
                      </Link>
                    ) : <div />}

                    {/* Action Buttons */}
                    <div className="flex items-center gap-2">
                      {!item.is_read ? (
                        <button
                          onClick={e => handleMarkOneRead(item.id, e)}
                          disabled={actionLoading === item.id}
                          className="inline-flex items-center gap-1 text-[11px] font-semibold text-slate-600 hover:text-slate-900 bg-slate-100 hover:bg-slate-200 px-2.5 py-1 rounded-lg transition-colors cursor-pointer"
                        >
                          <Check className="w-3 h-3" />
                          <span>Mark Read</span>
                        </button>
                      ) : (
                        <span className="text-[10px] text-slate-400 font-medium px-2 py-0.5 bg-slate-50 rounded">
                          Read
                        </span>
                      )}
                      <button
                        onClick={e => handleDelete(item.id, e)}
                        disabled={actionLoading === `del-${item.id}`}
                        title="Delete notification"
                        className="p-1.5 text-slate-400 hover:text-rose-600 hover:bg-rose-50 rounded-lg transition-colors cursor-pointer"
                      >
                        <Trash2 className="w-3.5 h-3.5" />
                      </button>
                    </div>
                  </div>
                </div>
              </div>
            ))}
          </div>
        )}
      </div>

      {/* Quick Sign-In Modal */}
      {showAuthModal && (
        <div className="fixed inset-0 z-50 bg-slate-900/40 backdrop-blur-sm flex items-center justify-center p-4">
          <div className="bg-white rounded-2xl max-w-sm w-full p-6 shadow-2xl border border-slate-200 space-y-4">
            <div className="text-center space-y-1">
              <h3 className="text-base font-bold text-slate-900">Citizen Sign In</h3>
              <p className="text-xs text-slate-500">
                Authenticate to view your real-time case notifications
              </p>
            </div>

            {authError && (
              <div className="p-3 bg-rose-50 border border-rose-200 rounded-xl text-xs text-rose-700">
                {authError}
              </div>
            )}

            <form onSubmit={handleQuickLogin} className="space-y-3">
              <div>
                <label className="text-xs font-semibold text-slate-700 block mb-1">
                  Email Address
                </label>
                <input
                  type="email"
                  required
                  value={authEmail}
                  onChange={e => setAuthEmail(e.target.value)}
                  className="w-full text-xs px-3 py-2 border border-slate-200 rounded-xl focus:outline-none focus:ring-2 focus:ring-court-maroon/20 focus:border-court-maroon"
                />
              </div>

              <div>
                <label className="text-xs font-semibold text-slate-700 block mb-1">
                  Password
                </label>
                <input
                  type="password"
                  required
                  value={authPassword}
                  onChange={e => setAuthPassword(e.target.value)}
                  className="w-full text-xs px-3 py-2 border border-slate-200 rounded-xl focus:outline-none focus:ring-2 focus:ring-court-maroon/20 focus:border-court-maroon"
                />
              </div>

              <button
                type="submit"
                disabled={authLoading}
                className="w-full py-2 bg-court-maroon text-white font-bold text-xs rounded-xl hover:bg-rose-800 transition-colors cursor-pointer disabled:opacity-50"
              >
                {authLoading ? 'Signing in...' : 'Sign In'}
              </button>
            </form>

            <button
              onClick={() => setShowAuthModal(false)}
              className="w-full text-center text-xs text-slate-400 hover:text-slate-600 cursor-pointer"
            >
              Cancel
            </button>
          </div>
        </div>
      )}
    </div>
  );
}