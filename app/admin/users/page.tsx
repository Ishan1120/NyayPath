'use client';

import React, { useState, useEffect } from 'react';
import {
  Users,
  Search,
  Filter,
  RefreshCw,
  AlertTriangle,
  CheckCircle2,
  Lock,
  Unlock,
  ShieldAlert,
  ChevronLeft,
  ChevronRight,
  Eye,
  UserCheck,
  UserX,
  X
} from 'lucide-react';
import AdminLayout from '../AdminLayout';
import {
  getPlatformUsers,
  getPlatformUserProfile,
  updatePlatformUserStatus,
  PlatformUserItem
} from '@/lib/api';

export default function AdminUsersPage() {
  const [users, setUsers] = useState<PlatformUserItem[]>([]);
  const [totalUsers, setTotalUsers] = useState<number>(0);
  const [loading, setLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);

  // Filters
  const [search, setSearch] = useState<string>('');
  const [roleFilter, setRoleFilter] = useState<string>('');
  const [statusFilter, setStatusFilter] = useState<string>('');
  const [currentPage, setCurrentPage] = useState<number>(1);
  const pageSize = 15;

  // Selected User Modal
  const [selectedUser, setSelectedUser] = useState<any | null>(null);
  const [loadingProfile, setLoadingProfile] = useState<boolean>(false);

  // Status Action Modal
  const [actionUser, setActionUser] = useState<PlatformUserItem | null>(null);
  const [targetStatus, setTargetStatus] = useState<'active' | 'suspended' | 'revoked'>('suspended');
  const [actionReason, setActionReason] = useState<string>('');
  const [submittingAction, setSubmittingAction] = useState<boolean>(false);
  const [actionMessage, setActionMessage] = useState<{ type: 'success' | 'error'; text: string } | null>(null);

  const [currentAdminUid, setCurrentAdminUid] = useState<string>('');

  useEffect(() => {
    if (typeof window !== 'undefined') {
      try {
        const u = JSON.parse(localStorage.getItem('nyaypath_user') || '{}');
        if (u.user_id) setCurrentAdminUid(u.user_id);
      } catch {}
    }
  }, []);

  const loadUsers = async () => {
    setLoading(true);
    setError(null);
    try {
      const data = await getPlatformUsers({
        search: search.trim() || undefined,
        role: roleFilter || undefined,
        status: statusFilter || undefined,
        page: currentPage,
        page_size: pageSize
      });
      setUsers(data.users || []);
      setTotalUsers(data.total || 0);
    } catch (err: any) {
      setError(err?.response?.data?.detail || 'Failed to load user directory.');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadUsers();
  }, [currentPage, roleFilter, statusFilter]);

  const handleSearchSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    setCurrentPage(1);
    loadUsers();
  };

  const openProfile = async (user: PlatformUserItem) => {
    setLoadingProfile(true);
    setSelectedUser(user);
    try {
      const fullProf = await getPlatformUserProfile(user.id);
      setSelectedUser(fullProf);
    } catch (err) {
      // Keep basic user item
    } finally {
      setLoadingProfile(false);
    }
  };

  const handleOpenAction = (user: PlatformUserItem, status: 'active' | 'suspended' | 'revoked') => {
    setActionUser(user);
    setTargetStatus(status);
    setActionReason('');
    setActionMessage(null);
  };

  const submitStatusChange = async () => {
    if (!actionUser) return;
    if (!actionReason || actionReason.trim().length < 3) {
      setActionMessage({ type: 'error', text: 'Please enter a valid reason (minimum 3 characters).' });
      return;
    }

    setSubmittingAction(true);
    setActionMessage(null);

    try {
      await updatePlatformUserStatus(actionUser.id, {
        new_status: targetStatus,
        reason: actionReason.trim()
      });
      setActionMessage({
        type: 'success',
        text: `Account for ${actionUser.full_name} is now ${targetStatus.toUpperCase()}.`
      });
      setTimeout(() => {
        setActionUser(null);
        loadUsers();
      }, 1200);
    } catch (err: any) {
      setActionMessage({
        type: 'error',
        text: err?.response?.data?.detail || 'Failed to update user account status.'
      });
    } finally {
      setSubmittingAction(false);
    }
  };

  const totalPages = Math.ceil(totalUsers / pageSize) || 1;

  return (
    <AdminLayout
      title="User Management & Access Control"
      subtitle="Platform-wide identity registry across Citizens, Students, Advocates, Proctors, and Institutional Administrators."
      badge="Global Directory"
    >
      {/* Search and Filters Bar */}
      <div className="bg-white p-5 rounded-2xl border border-slate-200 shadow-sm mb-6">
        <form onSubmit={handleSearchSubmit} className="flex flex-col md:flex-row gap-3">
          <div className="relative flex-1">
            <Search className="w-4 h-4 text-slate-400 absolute left-3.5 top-3" />
            <input
              type="text"
              placeholder="Search by full name or email address..."
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              className="w-full pl-10 pr-4 py-2 text-xs sm:text-sm border border-slate-200 rounded-xl focus:outline-none focus:ring-2 focus:ring-court-maroon/20 focus:border-court-maroon"
            />
          </div>

          <div className="flex flex-wrap sm:flex-nowrap gap-2">
            <select
              value={roleFilter}
              onChange={(e) => {
                setRoleFilter(e.target.value);
                setCurrentPage(1);
              }}
              className="px-3 py-2 text-xs sm:text-sm border border-slate-200 rounded-xl bg-white text-slate-700 focus:outline-none focus:ring-2 focus:ring-court-maroon/20"
            >
              <option value="">All Roles</option>
              <option value="citizen">Citizen</option>
              <option value="student">Student</option>
              <option value="lawyer">Advocate / Lawyer</option>
              <option value="institution_admin">Institution Admin</option>
              <option value="chief_proctor">Chief Proctor</option>
              <option value="proctor">Proctor</option>
              <option value="committee_member">Committee Member</option>
            </select>

            <select
              value={statusFilter}
              onChange={(e) => {
                setStatusFilter(e.target.value);
                setCurrentPage(1);
              }}
              className="px-3 py-2 text-xs sm:text-sm border border-slate-200 rounded-xl bg-white text-slate-700 focus:outline-none focus:ring-2 focus:ring-court-maroon/20"
            >
              <option value="">All Statuses</option>
              <option value="active">Active</option>
              <option value="suspended">Suspended</option>
              <option value="revoked">Revoked</option>
            </select>

            <button
              type="submit"
              className="px-4 py-2 text-xs font-semibold rounded-xl bg-court-maroon text-white hover:bg-court-maroon/90 shadow transition-colors"
            >
              Search
            </button>
            <button
              type="button"
              onClick={() => {
                setSearch('');
                setRoleFilter('');
                setStatusFilter('');
                setCurrentPage(1);
              }}
              className="px-3 py-2 text-xs font-medium rounded-xl border border-slate-200 text-slate-600 hover:bg-slate-50 transition-colors"
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
          <button onClick={loadUsers} className="text-xs underline font-semibold">
            Retry
          </button>
        </div>
      )}

      {/* Users Table */}
      <div className="bg-white rounded-2xl border border-slate-200 shadow-sm overflow-hidden mb-6">
        <div className="overflow-x-auto">
          <table className="w-full text-left text-xs sm:text-sm">
            <thead className="bg-slate-100/70 text-slate-600 font-bold uppercase text-[11px] border-b border-slate-200">
              <tr>
                <th className="py-3 px-4">User</th>
                <th className="py-3 px-4">Role</th>
                <th className="py-3 px-4">Affiliation / State</th>
                <th className="py-3 px-4">Status</th>
                <th className="py-3 px-4">Registered</th>
                <th className="py-3 px-4 text-right">Actions</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100 text-slate-700">
              {loading ? (
                <tr>
                  <td colSpan={6} className="py-10 text-center text-slate-400">
                    Loading users directory...
                  </td>
                </tr>
              ) : users.length === 0 ? (
                <tr>
                  <td colSpan={6} className="py-10 text-center text-slate-400">
                    No users matching the selected filters found.
                  </td>
                </tr>
              ) : (
                users.map((u) => {
                  const isCurrentAdmin = u.id === currentAdminUid;
                  return (
                    <tr key={u.id} className="hover:bg-slate-50/50 transition-colors">
                      <td className="py-3 px-4">
                        <div className="font-semibold text-slate-900">{u.full_name}</div>
                        <div className="text-xs text-slate-400 font-mono truncate max-w-[200px]">
                          {u.email}
                        </div>
                      </td>
                      <td className="py-3 px-4">
                        <span className="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-semibold bg-slate-100 text-slate-800 uppercase tracking-wider text-[10px]">
                          {u.role.replace('_', ' ')}
                        </span>
                      </td>
                      <td className="py-3 px-4 text-xs text-slate-600">
                        {u.institution_code ? (
                          <span className="font-semibold text-blue-700">{u.institution_code}</span>
                        ) : u.lawyer_profile ? (
                          <span>{u.lawyer_profile.bar_council || 'State Bar'}</span>
                        ) : (
                          <span className="text-slate-400">—</span>
                        )}
                      </td>
                      <td className="py-3 px-4">
                        {u.account_status === 'active' ? (
                          <span className="inline-flex items-center gap-1 text-emerald-700 font-semibold text-xs">
                            <span className="w-2 h-2 rounded-full bg-emerald-500"></span>
                            Active
                          </span>
                        ) : u.account_status === 'suspended' ? (
                          <span className="inline-flex items-center gap-1 text-amber-700 font-semibold text-xs">
                            <span className="w-2 h-2 rounded-full bg-amber-500"></span>
                            Suspended
                          </span>
                        ) : (
                          <span className="inline-flex items-center gap-1 text-red-700 font-semibold text-xs">
                            <span className="w-2 h-2 rounded-full bg-red-500"></span>
                            Revoked
                          </span>
                        )}
                      </td>
                      <td className="py-3 px-4 text-xs text-slate-400 whitespace-nowrap">
                        {new Date(u.created_at).toLocaleDateString()}
                      </td>
                      <td className="py-3 px-4 text-right">
                        <div className="flex items-center justify-end gap-1.5">
                          <button
                            onClick={() => openProfile(u)}
                            className="p-1.5 text-slate-500 hover:text-court-maroon hover:bg-slate-100 rounded-lg transition-colors"
                            title="Inspect Profile"
                          >
                            <Eye className="w-4 h-4" />
                          </button>

                          {isCurrentAdmin ? (
                            <span className="text-[11px] text-slate-400 italic px-2">Current Admin</span>
                          ) : (
                            <>
                              {u.account_status === 'active' ? (
                                <button
                                  onClick={() => handleOpenAction(u, 'suspended')}
                                  className="px-2.5 py-1 text-xs font-semibold rounded-lg text-amber-700 bg-amber-50 hover:bg-amber-100 border border-amber-200 transition-colors"
                                >
                                  Suspend
                                </button>
                              ) : (
                                <button
                                  onClick={() => handleOpenAction(u, 'active')}
                                  className="px-2.5 py-1 text-xs font-semibold rounded-lg text-emerald-700 bg-emerald-50 hover:bg-emerald-100 border border-emerald-200 transition-colors"
                                >
                                  Reinstate
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
            Showing <strong>{users.length}</strong> of <strong>{totalUsers}</strong> registered users
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

      {/* User Details Drawer / Modal */}
      {selectedUser && (
        <div className="fixed inset-0 z-50 bg-black/50 backdrop-blur-sm flex items-center justify-center p-4">
          <div className="bg-white rounded-2xl max-w-lg w-full p-6 shadow-2xl border border-slate-200 relative">
            <button
              onClick={() => setSelectedUser(null)}
              className="absolute top-4 right-4 text-slate-400 hover:text-slate-600"
            >
              <X className="w-5 h-5" />
            </button>

            <div className="flex items-center gap-3 mb-4">
              <div className="p-3 bg-court-maroon/10 text-court-maroon rounded-xl">
                <Users className="w-6 h-6" />
              </div>
              <div>
                <h3 className="font-serif font-bold text-slate-900 text-lg">
                  {selectedUser.full_name}
                </h3>
                <p className="text-xs text-slate-500 font-mono">{selectedUser.id}</p>
              </div>
            </div>

            <div className="space-y-3 text-xs sm:text-sm text-slate-700 bg-slate-50 p-4 rounded-xl border border-slate-100 mb-6">
              <div className="flex justify-between">
                <span className="text-slate-500">Email:</span>
                <span className="font-semibold text-slate-900">{selectedUser.email}</span>
              </div>
              <div className="flex justify-between">
                <span className="text-slate-500">Role:</span>
                <span className="font-bold text-court-maroon uppercase">{selectedUser.role}</span>
              </div>
              <div className="flex justify-between">
                <span className="text-slate-500">Account Status:</span>
                <span className="font-semibold uppercase">{selectedUser.account_status}</span>
              </div>
              <div className="flex justify-between">
                <span className="text-slate-500">Platform Verified:</span>
                <span>{selectedUser.is_verified ? 'Yes' : 'No'}</span>
              </div>
              <div className="flex justify-between">
                <span className="text-slate-500">Registered:</span>
                <span>{new Date(selectedUser.created_at).toLocaleString()}</span>
              </div>

              {selectedUser.lawyer_profile && (
                <div className="pt-2 border-t border-slate-200 mt-2">
                  <div className="font-semibold text-slate-900 mb-1">Advocate Credentials:</div>
                  <div className="text-xs text-slate-600">
                    Bar Council: {selectedUser.lawyer_profile.bar_council}
                  </div>
                  <div className="text-xs text-slate-600">
                    Enrollment: {selectedUser.lawyer_profile.enrollment_number}
                  </div>
                  <div className="text-xs text-slate-600">
                    Status: <strong className="text-court-maroon">{selectedUser.lawyer_profile.verification_status}</strong>
                  </div>
                </div>
              )}
            </div>

            <div className="flex justify-end">
              <button
                onClick={() => setSelectedUser(null)}
                className="px-4 py-2 rounded-xl text-xs font-semibold bg-slate-100 text-slate-700 hover:bg-slate-200 transition-colors"
              >
                Close
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Account Status Change Modal */}
      {actionUser && (
        <div className="fixed inset-0 z-50 bg-black/50 backdrop-blur-sm flex items-center justify-center p-4">
          <div className="bg-white rounded-2xl max-w-md w-full p-6 shadow-2xl border border-slate-200">
            <div className="flex items-center gap-3 mb-4">
              <div className={`p-3 rounded-xl ${targetStatus === 'active' ? 'bg-emerald-100 text-emerald-700' : 'bg-amber-100 text-amber-700'}`}>
                {targetStatus === 'active' ? <Unlock className="w-6 h-6" /> : <Lock className="w-6 h-6" />}
              </div>
              <div>
                <h3 className="font-serif font-bold text-slate-900 text-lg">
                  {targetStatus === 'active' ? 'Reinstate Account' : 'Suspend Account'}
                </h3>
                <p className="text-xs text-slate-500">{actionUser.full_name} ({actionUser.email})</p>
              </div>
            </div>

            <p className="text-xs text-slate-600 mb-4">
              {targetStatus === 'active'
                ? 'Reinstating this account will immediately restore protected application access across NyayPath.'
                : 'Suspending this account will immediately revoke authentication access and terminate active sessions.'}
            </p>

            <div className="mb-4">
              <label className="block text-xs font-bold text-slate-700 uppercase mb-1">
                Operational Justification / Audit Reason:
              </label>
              <textarea
                rows={3}
                placeholder="Enter mandatory reason for this account status change..."
                value={actionReason}
                onChange={(e) => setActionReason(e.target.value)}
                className="w-full p-3 text-xs sm:text-sm border border-slate-200 rounded-xl focus:outline-none focus:ring-2 focus:ring-court-maroon/20 focus:border-court-maroon"
              />
            </div>

            {actionMessage && (
              <div
                className={`p-3 rounded-xl mb-4 text-xs ${
                  actionMessage.type === 'success'
                    ? 'bg-emerald-50 text-emerald-800 border border-emerald-200'
                    : 'bg-red-50 text-red-800 border border-red-200'
                }`}
              >
                {actionMessage.text}
              </div>
            )}

            <div className="flex items-center justify-end gap-2">
              <button
                type="button"
                onClick={() => setActionUser(null)}
                disabled={submittingAction}
                className="px-4 py-2 rounded-xl text-xs font-medium border border-slate-200 text-slate-600 hover:bg-slate-50"
              >
                Cancel
              </button>
              <button
                type="button"
                onClick={submitStatusChange}
                disabled={submittingAction}
                className={`px-4 py-2 rounded-xl text-xs font-semibold text-white shadow transition-colors ${
                  targetStatus === 'active'
                    ? 'bg-emerald-600 hover:bg-emerald-700'
                    : 'bg-amber-600 hover:bg-amber-700'
                } disabled:opacity-50`}
              >
                {submittingAction ? 'Recording...' : `Confirm ${targetStatus.toUpperCase()}`}
              </button>
            </div>
          </div>
        </div>
      )}
    </AdminLayout>
  );
}

