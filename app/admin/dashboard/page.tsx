'use client';

import React, { useState, useEffect } from 'react';
import Link from 'next/link';
import {
  Users,
  Building,
  Gavel,
  Scale,
  Calendar,
  Bell,
  RefreshCw,
  Clock,
  CheckCircle2,
  AlertTriangle,
  ArrowRight,
  ShieldCheck,
  TrendingUp,
  Activity,
  UserCheck,
  FileText
} from 'lucide-react';
import AdminLayout from '../AdminLayout';
import {
  getPlatformOverview,
  getPlatformActivity,
  PlatformOverviewStats,
  PlatformAuditLogItem
} from '@/lib/api';

export default function AdminDashboardPage() {
  const [stats, setStats] = useState<PlatformOverviewStats | null>(null);
  const [activities, setActivities] = useState<PlatformAuditLogItem[]>([]);
  const [loading, setLoading] = useState<boolean>(true);
  const [refreshing, setRefreshing] = useState<boolean>(false);
  const [error, setError] = useState<string | null>(null);

  const loadData = async (isRefresh: boolean = false) => {
    if (isRefresh) setRefreshing(true);
    else setLoading(true);
    setError(null);

    try {
      const [overviewData, activityData] = await Promise.all([
        getPlatformOverview(),
        getPlatformActivity(10)
      ]);
      setStats(overviewData);
      setActivities(activityData.activities || []);
    } catch (err: any) {
      setError(err?.response?.data?.detail || 'Failed to load platform statistics.');
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  };

  useEffect(() => {
    loadData();
  }, []);

  return (
    <AdminLayout
      title="Platform Operations & Global Oversight"
      subtitle="Comprehensive system metrics, cross-institutional telemetry, and active administrative activity."
      badge="Live Telemetry"
    >
      {/* Top Action Bar */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 mb-6">
        <div>
          <h2 className="text-lg font-serif font-bold text-slate-900">
            Platform Ecosystem Overview
          </h2>
          <p className="text-xs text-slate-500">
            Real-time aggregates from authoritative PostgreSQL state.
          </p>
        </div>
        <button
          onClick={() => loadData(true)}
          disabled={loading || refreshing}
          className="inline-flex items-center gap-1.5 px-3.5 py-1.5 text-xs font-semibold rounded-lg bg-white border border-slate-200 text-slate-700 hover:bg-slate-50 shadow-sm transition-colors disabled:opacity-50"
        >
          <RefreshCw className={`w-3.5 h-3.5 ${refreshing ? 'animate-spin' : ''}`} />
          {refreshing ? 'Refreshing...' : 'Refresh Metrics'}
        </button>
      </div>

      {error && (
        <div className="bg-red-50 border border-red-200 text-red-700 px-4 py-3 rounded-xl mb-6 text-sm flex items-center justify-between">
          <div className="flex items-center gap-2">
            <AlertTriangle className="w-4 h-4 shrink-0" />
            <span>{error}</span>
          </div>
          <button onClick={() => loadData(true)} className="text-xs underline font-semibold">
            Retry
          </button>
        </div>
      )}

      {/* Global Statistics Grid */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4 mb-8">
        {/* Total Users */}
        <div className="bg-white rounded-xl border border-slate-200 p-5 shadow-sm hover:shadow-md transition-shadow">
          <div className="flex items-center justify-between text-slate-500 mb-2">
            <span className="text-xs font-bold uppercase tracking-wider">Total Accounts</span>
            <Users className="w-4 h-4 text-court-maroon" />
          </div>
          <div className="text-2xl sm:text-3xl font-serif font-bold text-slate-900">
            {loading ? '...' : (stats?.total_users ?? 0)}
          </div>
          <div className="mt-2 text-xs text-slate-500 flex items-center gap-3">
            <span>Citizens: <strong className="text-slate-800">{stats?.citizens ?? 0}</strong></span>
            <span>Students: <strong className="text-slate-800">{stats?.students ?? 0}</strong></span>
          </div>
        </div>

        {/* Legal Advocates */}
        <div className="bg-white rounded-xl border border-slate-200 p-5 shadow-sm hover:shadow-md transition-shadow">
          <div className="flex items-center justify-between text-slate-500 mb-2">
            <span className="text-xs font-bold uppercase tracking-wider">Advocates</span>
            <Gavel className="w-4 h-4 text-court-gold" />
          </div>
          <div className="text-2xl sm:text-3xl font-serif font-bold text-slate-900">
            {loading ? '...' : (stats?.lawyers ?? 0)}
          </div>
          <div className="mt-2 text-xs text-slate-500 flex items-center gap-3">
            <span className="text-emerald-600 font-semibold">
              Verified: {stats?.verified_lawyers ?? 0}
            </span>
            <span className="text-amber-600 font-semibold">
              Pending: {stats?.pending_lawyers ?? 0}
            </span>
          </div>
        </div>

        {/* Institutions */}
        <div className="bg-white rounded-xl border border-slate-200 p-5 shadow-sm hover:shadow-md transition-shadow">
          <div className="flex items-center justify-between text-slate-500 mb-2">
            <span className="text-xs font-bold uppercase tracking-wider">Institutions</span>
            <Building className="w-4 h-4 text-blue-600" />
          </div>
          <div className="text-2xl sm:text-3xl font-serif font-bold text-slate-900">
            {loading ? '...' : (stats?.institutions ?? 0)}
          </div>
          <div className="mt-2 text-xs text-slate-500 flex items-center gap-3">
            <span>Active: <strong className="text-slate-800">{stats?.active_institutions ?? 0}</strong></span>
            <span>Officers: <strong className="text-slate-800">{stats?.institutional_memberships ?? 0}</strong></span>
          </div>
        </div>

        {/* Registered Cases */}
        <div className="bg-white rounded-xl border border-slate-200 p-5 shadow-sm hover:shadow-md transition-shadow">
          <div className="flex items-center justify-between text-slate-500 mb-2">
            <span className="text-xs font-bold uppercase tracking-wider">Grievances & Cases</span>
            <Scale className="w-4 h-4 text-indigo-600" />
          </div>
          <div className="text-2xl sm:text-3xl font-serif font-bold text-slate-900">
            {loading ? '...' : (stats?.total_cases ?? 0)}
          </div>
          <div className="mt-2 text-xs text-slate-500 flex items-center gap-3">
            <span>Active: <strong className="text-indigo-600">{stats?.active_cases ?? 0}</strong></span>
            <span>Resolved: <strong className="text-emerald-600">{stats?.resolved_cases ?? 0}</strong></span>
          </div>
        </div>
      </div>

      {/* Secondary Metrics Bar */}
      <div className="grid grid-cols-1 sm:grid-cols-3 gap-4 mb-8">
        <div className="bg-slate-100 rounded-xl p-4 border border-slate-200 flex items-center justify-between">
          <div>
            <div className="text-xs text-slate-500 font-semibold uppercase">Pending Consultations</div>
            <div className="text-xl font-bold text-slate-900 mt-1">
              {loading ? '...' : (stats?.pending_consultations ?? 0)}
            </div>
          </div>
          <FileText className="w-6 h-6 text-slate-400" />
        </div>

        <div className="bg-slate-100 rounded-xl p-4 border border-slate-200 flex items-center justify-between">
          <div>
            <div className="text-xs text-slate-500 font-semibold uppercase">Confirmed Meetings</div>
            <div className="text-xl font-bold text-slate-900 mt-1">
              {loading ? '...' : (stats?.scheduled_meetings ?? 0)}
            </div>
          </div>
          <Calendar className="w-6 h-6 text-slate-400" />
        </div>

        <div className="bg-slate-100 rounded-xl p-4 border border-slate-200 flex items-center justify-between">
          <div>
            <div className="text-xs text-slate-500 font-semibold uppercase">Dispatched Alerts</div>
            <div className="text-xl font-bold text-slate-900 mt-1">
              {loading ? '...' : (stats?.total_notifications ?? 0)}
            </div>
          </div>
          <Bell className="w-6 h-6 text-slate-400" />
        </div>
      </div>

      {/* Recent Activity Table */}
      <div className="bg-white rounded-2xl border border-slate-200 shadow-sm overflow-hidden mb-8">
        <div className="p-5 border-b border-slate-200 flex items-center justify-between bg-slate-50/50">
          <div className="flex items-center gap-2">
            <Activity className="w-4 h-4 text-court-maroon" />
            <h3 className="font-serif font-bold text-slate-900 text-sm sm:text-base">
              Recent Administrative Activity Log
            </h3>
          </div>
          <Link
            href="/admin/audit-logs"
            className="text-xs font-semibold text-court-maroon hover:underline flex items-center gap-1"
          >
            View Full Audit Trail
            <ArrowRight className="w-3.5 h-3.5" />
          </Link>
        </div>

        <div className="overflow-x-auto">
          <table className="w-full text-left text-xs sm:text-sm">
            <thead className="bg-slate-100/70 text-slate-600 font-bold uppercase text-[11px] border-b border-slate-200">
              <tr>
                <th className="py-3 px-4">Action</th>
                <th className="py-3 px-4">Entity</th>
                <th className="py-3 px-4">Actor</th>
                <th className="py-3 px-4">Reason / Notes</th>
                <th className="py-3 px-4">Timestamp</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100 text-slate-700">
              {loading ? (
                <tr>
                  <td colSpan={5} className="py-8 text-center text-slate-400">
                    Loading activity feed...
                  </td>
                </tr>
              ) : activities.length === 0 ? (
                <tr>
                  <td colSpan={5} className="py-8 text-center text-slate-400">
                    No recent administrative activity recorded.
                  </td>
                </tr>
              ) : (
                activities.map((act) => (
                  <tr key={act.id} className="hover:bg-slate-50/50 transition-colors">
                    <td className="py-3 px-4 font-semibold text-slate-900">
                      <span className="inline-flex items-center px-2 py-0.5 rounded text-[11px] font-bold bg-slate-100 text-slate-800">
                        {act.action_type}
                      </span>
                    </td>
                    <td className="py-3 px-4 font-mono text-xs text-slate-600">
                      {act.target_entity_type}: {act.target_entity_id}
                    </td>
                    <td className="py-3 px-4 text-xs text-slate-600">
                      {act.actor_email}
                    </td>
                    <td className="py-3 px-4 text-xs text-slate-500 max-w-xs truncate">
                      {act.reason || act.details?.decision || 'Automated action'}
                    </td>
                    <td className="py-3 px-4 text-xs text-slate-400 whitespace-nowrap">
                      {new Date(act.created_at).toLocaleString()}
                    </td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>
      </div>
    </AdminLayout>
  );
}
