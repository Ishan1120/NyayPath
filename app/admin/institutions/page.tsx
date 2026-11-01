'use client';

import React, { useState, useEffect } from 'react';
import {
  Building,
  Search,
  Plus,
  RefreshCw,
  AlertTriangle,
  CheckCircle2,
  Users,
  Scale,
  Lock,
  Unlock,
  ChevronLeft,
  ChevronRight,
  Eye,
  X,
  FileText
} from 'lucide-react';
import AdminLayout from '../AdminLayout';
import {
  getPlatformInstitutions,
  getPlatformInstitutionDetails,
  registerPlatformInstitution,
  togglePlatformInstitutionStatus,
  PlatformInstitutionItem
} from '@/lib/api';

export default function AdminInstitutionsPage() {
  const [institutions, setInstitutions] = useState<PlatformInstitutionItem[]>([]);
  const [total, setTotal] = useState<number>(0);
  const [loading, setLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);

  // Filters
  const [search, setSearch] = useState<string>('');
  const [statusFilter, setStatusFilter] = useState<string>('');
  const [currentPage, setCurrentPage] = useState<number>(1);
  const pageSize = 15;

  // Register Modal
  const [showRegisterModal, setShowRegisterModal] = useState<boolean>(false);
  const [newCode, setNewCode] = useState<string>('');
  const [newName, setNewName] = useState<string>('');
  const [newCity, setNewCity] = useState<string>('');
  const [newState, setNewState] = useState<string>('');
  const [newType, setNewType] = useState<string>('university');
  const [registering, setRegistering] = useState<boolean>(false);
  const [registerMsg, setRegisterMsg] = useState<{ type: 'success' | 'error'; text: string } | null>(null);

  // Inspection Drawer
  const [selectedInst, setSelectedInst] = useState<any | null>(null);
  const [loadingDetails, setLoadingDetails] = useState<boolean>(false);

  // Status Toggle Modal
  const [toggleInst, setToggleInst] = useState<PlatformInstitutionItem | null>(null);
  const [toggleActive, setToggleActive] = useState<boolean>(false);
  const [toggleReason, setToggleReason] = useState<string>('');
  const [toggling, setToggling] = useState<boolean>(false);
  const [toggleMsg, setToggleMsg] = useState<{ type: 'success' | 'error'; text: string } | null>(null);

  const loadInstitutions = async () => {
    setLoading(true);
    setError(null);
    try {
      const activeParam = statusFilter === 'active' ? true : statusFilter === 'inactive' ? false : undefined;
      const data = await getPlatformInstitutions({
        search: search.trim() || undefined,
        is_active: activeParam,
        page: currentPage,
        page_size: pageSize
      });
      setInstitutions(data.institutions || []);
      setTotal(data.total || 0);
    } catch (err: any) {
      setError(err?.response?.data?.detail || 'Failed to load institutions.');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadInstitutions();
  }, [currentPage, statusFilter]);

  const handleSearchSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    setCurrentPage(1);
    loadInstitutions();
  };

  const handleRegisterSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!newCode || !newName || !newCity || !newState) {
      setRegisterMsg({ type: 'error', text: 'All fields are required.' });
      return;
    }

    setRegistering(true);
    setRegisterMsg(null);
    try {
      await registerPlatformInstitution({
        code: newCode.trim().toUpperCase(),
        name: newName.trim(),
        city: newCity.trim(),
        state: newState.trim(),
        type: newType,
        is_active: true
      });
      setRegisterMsg({ type: 'success', text: 'Institution onboarded successfully!' });
      setTimeout(() => {
        setShowRegisterModal(false);
        setNewCode('');
        setNewName('');
        setNewCity('');
        setNewState('');
        loadInstitutions();
      }, 1000);
    } catch (err: any) {
      setRegisterMsg({
        type: 'error',
        text: err?.response?.data?.detail || 'Failed to register institution.'
      });
    } finally {
      setRegistering(false);
    }
  };

  const inspectInstitution = async (inst: PlatformInstitutionItem) => {
    setLoadingDetails(true);
    setSelectedInst(inst);
    try {
      const full = await getPlatformInstitutionDetails(inst.id);
      setSelectedInst(full);
    } catch {
      // Keep basic data
    } finally {
      setLoadingDetails(false);
    }
  };

  const openStatusToggle = (inst: PlatformInstitutionItem, targetState: boolean) => {
    setToggleInst(inst);
    setToggleActive(targetState);
    setToggleReason('');
    setToggleMsg(null);
  };

  const submitStatusToggle = async () => {
    if (!toggleInst) return;
    if (!toggleReason || toggleReason.trim().length < 3) {
      setToggleMsg({ type: 'error', text: 'Mandatory reason (min 3 characters) required.' });
      return;
    }

    setToggling(true);
    setToggleMsg(null);
    try {
      await togglePlatformInstitutionStatus(toggleInst.id, {
        is_active: toggleActive,
        reason: toggleReason.trim()
      });
      setToggleMsg({
        type: 'success',
        text: `Institution ${toggleInst.name} is now ${toggleActive ? 'ACTIVATED' : 'DEACTIVATED'}.`
      });
      setTimeout(() => {
        setToggleInst(null);
        loadInstitutions();
      }, 1000);
    } catch (err: any) {
      setToggleMsg({
        type: 'error',
        text: err?.response?.data?.detail || 'Failed to update institution status.'
      });
    } finally {
      setToggling(false);
    }
  };

  const totalPages = Math.ceil(total / pageSize) || 1;

  return (
    <AdminLayout
      title="Institution Management & Onboarding"
      subtitle="Register, activate, inspect and oversee educational campuses integrated with NyayPath."
      badge="Multi-Tenant Registry"
    >
      {/* Top Search & Actions */}
      <div className="bg-white p-5 rounded-2xl border border-slate-200 shadow-sm mb-6 flex flex-col md:flex-row md:items-center justify-between gap-4">
        <form onSubmit={handleSearchSubmit} className="flex-1 flex flex-col sm:flex-row gap-3">
          <div className="relative flex-1">
            <Search className="w-4 h-4 text-slate-400 absolute left-3.5 top-3" />
            <input
              type="text"
              placeholder="Search by institution name, code, or city..."
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              className="w-full pl-10 pr-4 py-2 text-xs sm:text-sm border border-slate-200 rounded-xl focus:outline-none focus:ring-2 focus:ring-court-maroon/20 focus:border-court-maroon"
            />
          </div>

          <select
            value={statusFilter}
            onChange={(e) => {
              setStatusFilter(e.target.value);
              setCurrentPage(1);
            }}
            className="px-3 py-2 text-xs sm:text-sm border border-slate-200 rounded-xl bg-white text-slate-700 focus:outline-none focus:ring-2 focus:ring-court-maroon/20"
          >
            <option value="">All Statuses</option>
            <option value="active">Active Only</option>
            <option value="inactive">Deactivated Only</option>
          </select>

          <button
            type="submit"
            className="px-4 py-2 text-xs font-semibold rounded-xl bg-court-maroon text-white hover:bg-court-maroon/90 shadow transition-colors"
          >
            Filter
          </button>
        </form>

        <button
          onClick={() => {
            setShowRegisterModal(true);
            setRegisterMsg(null);
          }}
          className="inline-flex items-center gap-1.5 px-4 py-2.5 rounded-xl text-xs font-semibold text-white bg-slate-900 hover:bg-slate-800 shadow transition-colors shrink-0"
        >
          <Plus className="w-4 h-4" />
          Onboard Institution
        </button>
      </div>

      {error && (
        <div className="bg-red-50 border border-red-200 text-red-700 px-4 py-3 rounded-xl mb-6 text-sm flex items-center justify-between">
          <div className="flex items-center gap-2">
            <AlertTriangle className="w-4 h-4 shrink-0" />
            <span>{error}</span>
          </div>
          <button onClick={loadInstitutions} className="text-xs underline font-semibold">
            Retry
          </button>
        </div>
      )}

      {/* Institutions Table */}
      <div className="bg-white rounded-2xl border border-slate-200 shadow-sm overflow-hidden mb-6">
        <div className="overflow-x-auto">
          <table className="w-full text-left text-xs sm:text-sm">
            <thead className="bg-slate-100/70 text-slate-600 font-bold uppercase text-[11px] border-b border-slate-200">
              <tr>
                <th className="py-3 px-4">Institution Name</th>
                <th className="py-3 px-4">Code</th>
                <th className="py-3 px-4">Location</th>
                <th className="py-3 px-4">Type</th>
                <th className="py-3 px-4">Officers</th>
                <th className="py-3 px-4">Grievances</th>
                <th className="py-3 px-4">Status</th>
                <th className="py-3 px-4 text-right">Actions</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100 text-slate-700">
              {loading ? (
                <tr>
                  <td colSpan={8} className="py-10 text-center text-slate-400">
                    Loading institutions...
                  </td>
                </tr>
              ) : institutions.length === 0 ? (
                <tr>
                  <td colSpan={8} className="py-10 text-center text-slate-400">
                    No institutions found.
                  </td>
                </tr>
              ) : (
                institutions.map((inst) => (
                  <tr key={inst.id} className="hover:bg-slate-50/50 transition-colors">
                    <td className="py-3 px-4 font-semibold text-slate-900">
                      {inst.name}
                    </td>
                    <td className="py-3 px-4 font-mono text-xs font-bold text-court-maroon">
                      {inst.code}
                    </td>
                    <td className="py-3 px-4 text-xs text-slate-600">
                      {inst.city}, {inst.state}
                    </td>
                    <td className="py-3 px-4 uppercase text-[11px] text-slate-500 font-medium">
                      {inst.type}
                    </td>
                    <td className="py-3 px-4">
                      <span className="inline-flex items-center gap-1 font-semibold text-slate-700">
                        <Users className="w-3.5 h-3.5 text-slate-400" />
                        {inst.member_count}
                      </span>
                    </td>
                    <td className="py-3 px-4">
                      <span className="inline-flex items-center gap-1 font-semibold text-indigo-700">
                        <Scale className="w-3.5 h-3.5 text-indigo-400" />
                        {inst.grievance_count}
                      </span>
                    </td>
                    <td className="py-3 px-4">
                      {inst.is_active ? (
                        <span className="inline-flex items-center gap-1 text-emerald-700 font-semibold text-xs">
                          <span className="w-2 h-2 rounded-full bg-emerald-500"></span>
                          Active
                        </span>
                      ) : (
                        <span className="inline-flex items-center gap-1 text-slate-500 font-semibold text-xs">
                          <span className="w-2 h-2 rounded-full bg-slate-400"></span>
                          Deactivated
                        </span>
                      )}
                    </td>
                    <td className="py-3 px-4 text-right">
                      <div className="flex items-center justify-end gap-1.5">
                        <button
                          onClick={() => inspectInstitution(inst)}
                          className="p-1.5 text-slate-500 hover:text-court-maroon hover:bg-slate-100 rounded-lg transition-colors"
                          title="View Details & Roster"
                        >
                          <Eye className="w-4 h-4" />
                        </button>

                        {inst.is_active ? (
                          <button
                            onClick={() => openStatusToggle(inst, false)}
                            className="px-2.5 py-1 text-xs font-semibold rounded-lg text-amber-700 bg-amber-50 hover:bg-amber-100 border border-amber-200 transition-colors"
                          >
                            Deactivate
                          </button>
                        ) : (
                          <button
                            onClick={() => openStatusToggle(inst, true)}
                            className="px-2.5 py-1 text-xs font-semibold rounded-lg text-emerald-700 bg-emerald-50 hover:bg-emerald-100 border border-emerald-200 transition-colors"
                          >
                            Activate
                          </button>
                        )}
                      </div>
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
            Showing <strong>{institutions.length}</strong> of <strong>{total}</strong> institutions
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

      {/* Register Institution Modal */}
      {showRegisterModal && (
        <div className="fixed inset-0 z-50 bg-black/50 backdrop-blur-sm flex items-center justify-center p-4">
          <div className="bg-white rounded-2xl max-w-md w-full p-6 shadow-2xl border border-slate-200">
            <div className="flex items-center justify-between mb-4">
              <h3 className="font-serif font-bold text-slate-900 text-lg flex items-center gap-2">
                <Building className="w-5 h-5 text-court-maroon" />
                Onboard New Campus
              </h3>
              <button
                onClick={() => setShowRegisterModal(false)}
                className="text-slate-400 hover:text-slate-600"
              >
                <X className="w-5 h-5" />
              </button>
            </div>

            <form onSubmit={handleRegisterSubmit} className="space-y-3">
              <div>
                <label className="block text-xs font-bold text-slate-700 uppercase mb-1">
                  Institution Code (Unique Identifier)
                </label>
                <input
                  type="text"
                  placeholder="e.g. NIT_DELHI, IIT_BOMBAY"
                  value={newCode}
                  onChange={(e) => setNewCode(e.target.value.toUpperCase())}
                  required
                  className="w-full p-2.5 text-xs sm:text-sm font-mono border border-slate-200 rounded-xl focus:outline-none focus:ring-2 focus:ring-court-maroon/20 focus:border-court-maroon"
                />
              </div>

              <div>
                <label className="block text-xs font-bold text-slate-700 uppercase mb-1">
                  Institution Official Name
                </label>
                <input
                  type="text"
                  placeholder="e.g. National Institute of Technology Delhi"
                  value={newName}
                  onChange={(e) => setNewName(e.target.value)}
                  required
                  className="w-full p-2.5 text-xs sm:text-sm border border-slate-200 rounded-xl focus:outline-none focus:ring-2 focus:ring-court-maroon/20 focus:border-court-maroon"
                />
              </div>

              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="block text-xs font-bold text-slate-700 uppercase mb-1">
                    City
                  </label>
                  <input
                    type="text"
                    placeholder="e.g. New Delhi"
                    value={newCity}
                    onChange={(e) => setNewCity(e.target.value)}
                    required
                    className="w-full p-2.5 text-xs sm:text-sm border border-slate-200 rounded-xl"
                  />
                </div>
                <div>
                  <label className="block text-xs font-bold text-slate-700 uppercase mb-1">
                    State
                  </label>
                  <input
                    type="text"
                    placeholder="e.g. Delhi"
                    value={newState}
                    onChange={(e) => setNewState(e.target.value)}
                    required
                    className="w-full p-2.5 text-xs sm:text-sm border border-slate-200 rounded-xl"
                  />
                </div>
              </div>

              <div>
                <label className="block text-xs font-bold text-slate-700 uppercase mb-1">
                  Institution Type
                </label>
                <select
                  value={newType}
                  onChange={(e) => setNewType(e.target.value)}
                  className="w-full p-2.5 text-xs sm:text-sm border border-slate-200 rounded-xl bg-white"
                >
                  <option value="university">University</option>
                  <option value="autonomous_institute">Autonomous Institute</option>
                  <option value="affiliated_college">Affiliated College</option>
                </select>
              </div>

              {registerMsg && (
                <div
                  className={`p-3 rounded-xl text-xs ${
                    registerMsg.type === 'success'
                      ? 'bg-emerald-50 text-emerald-800 border border-emerald-200'
                      : 'bg-red-50 text-red-800 border border-red-200'
                  }`}
                >
                  {registerMsg.text}
                </div>
              )}

              <div className="flex justify-end gap-2 pt-2">
                <button
                  type="button"
                  onClick={() => setShowRegisterModal(false)}
                  disabled={registering}
                  className="px-4 py-2 rounded-xl text-xs font-medium border border-slate-200 text-slate-600 hover:bg-slate-50"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  disabled={registering}
                  className="px-4 py-2 rounded-xl text-xs font-semibold bg-court-maroon text-white hover:bg-court-maroon/90 shadow disabled:opacity-50"
                >
                  {registering ? 'Onboarding...' : 'Onboard Institution'}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* Institution Details & Roster Drawer */}
      {selectedInst && (
        <div className="fixed inset-0 z-50 bg-black/50 backdrop-blur-sm flex items-center justify-center p-4">
          <div className="bg-white rounded-2xl max-w-xl w-full p-6 shadow-2xl border border-slate-200 relative max-h-[85vh] overflow-y-auto">
            <button
              onClick={() => setSelectedInst(null)}
              className="absolute top-4 right-4 text-slate-400 hover:text-slate-600"
            >
              <X className="w-5 h-5" />
            </button>

            <div className="flex items-center gap-3 mb-4">
              <div className="p-3 bg-blue-100 text-blue-700 rounded-xl">
                <Building className="w-6 h-6" />
              </div>
              <div>
                <h3 className="font-serif font-bold text-slate-900 text-lg">
                  {selectedInst.name}
                </h3>
                <p className="text-xs text-court-maroon font-mono font-bold">{selectedInst.code}</p>
              </div>
            </div>

            <div className="grid grid-cols-2 gap-3 text-xs bg-slate-50 p-4 rounded-xl border border-slate-100 mb-6">
              <div>
                <span className="text-slate-500">Location:</span>{' '}
                <strong>{selectedInst.city}, {selectedInst.state}</strong>
              </div>
              <div>
                <span className="text-slate-500">Type:</span>{' '}
                <strong className="uppercase">{selectedInst.type}</strong>
              </div>
              <div>
                <span className="text-slate-500">Operational Status:</span>{' '}
                <strong className={selectedInst.is_active ? 'text-emerald-700' : 'text-slate-500'}>
                  {selectedInst.is_active ? 'Active' : 'Deactivated'}
                </strong>
              </div>
              <div>
                <span className="text-slate-500">Total Grievances:</span>{' '}
                <strong>{selectedInst.grievance_count ?? 0}</strong>
              </div>
            </div>

            {/* Officer Roster */}
            <h4 className="font-serif font-bold text-slate-900 text-sm mb-2 flex items-center gap-2">
              <Users className="w-4 h-4 text-court-maroon" />
              Proctorial & Administrative Roster ({selectedInst.roster?.length || 0})
            </h4>

            <div className="border border-slate-200 rounded-xl divide-y divide-slate-100 overflow-hidden mb-6 text-xs">
              {!selectedInst.roster || selectedInst.roster.length === 0 ? (
                <div className="p-4 text-center text-slate-400">
                  No institutional officers registered yet.
                </div>
              ) : (
                selectedInst.roster.map((m: any) => (
                  <div key={m.id} className="p-3 flex items-center justify-between hover:bg-slate-50">
                    <div>
                      <span className="font-mono text-slate-600 block">{m.user_id}</span>
                      <span className="font-semibold text-slate-900 uppercase text-[10px]">
                        {m.role.replace('_', ' ')}
                      </span>
                    </div>
                    <span className="px-2 py-0.5 rounded text-[10px] font-bold uppercase bg-slate-100 text-slate-700">
                      {m.account_status}
                    </span>
                  </div>
                ))
              )}
            </div>

            <div className="flex justify-end">
              <button
                onClick={() => setSelectedInst(null)}
                className="px-4 py-2 rounded-xl text-xs font-semibold bg-slate-100 text-slate-700 hover:bg-slate-200 transition-colors"
              >
                Close
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Activate / Deactivate Modal */}
      {toggleInst && (
        <div className="fixed inset-0 z-50 bg-black/50 backdrop-blur-sm flex items-center justify-center p-4">
          <div className="bg-white rounded-2xl max-w-md w-full p-6 shadow-2xl border border-slate-200">
            <h3 className="font-serif font-bold text-slate-900 text-lg mb-2">
              {toggleActive ? 'Activate Institution' : 'Deactivate Institution'}
            </h3>
            <p className="text-xs text-slate-600 mb-4">
              {toggleActive
                ? `Activating ${toggleInst.name} allows officers and students to file and process grievances.`
                : `Deactivating ${toggleInst.name} suspends active operations. All historical grievances and audit logs remain intact.`}
            </p>

            <div className="mb-4">
              <label className="block text-xs font-bold text-slate-700 uppercase mb-1">
                Operational Reason:
              </label>
              <textarea
                rows={3}
                placeholder="Enter mandatory justification..."
                value={toggleReason}
                onChange={(e) => setToggleReason(e.target.value)}
                className="w-full p-3 text-xs sm:text-sm border border-slate-200 rounded-xl focus:outline-none focus:ring-2 focus:ring-court-maroon/20 focus:border-court-maroon"
              />
            </div>

            {toggleMsg && (
              <div
                className={`p-3 rounded-xl mb-4 text-xs ${
                  toggleMsg.type === 'success'
                    ? 'bg-emerald-50 text-emerald-800 border border-emerald-200'
                    : 'bg-red-50 text-red-800 border border-red-200'
                }`}
              >
                {toggleMsg.text}
              </div>
            )}

            <div className="flex justify-end gap-2">
              <button
                type="button"
                onClick={() => setToggleInst(null)}
                disabled={toggling}
                className="px-4 py-2 rounded-xl text-xs font-medium border border-slate-200 text-slate-600 hover:bg-slate-50"
              >
                Cancel
              </button>
              <button
                type="button"
                onClick={submitStatusToggle}
                disabled={toggling}
                className={`px-4 py-2 rounded-xl text-xs font-semibold text-white shadow ${
                  toggleActive ? 'bg-emerald-600 hover:bg-emerald-700' : 'bg-amber-600 hover:bg-amber-700'
                } disabled:opacity-50`}
              >
                {toggling ? 'Updating...' : `Confirm ${toggleActive ? 'Activation' : 'Deactivation'}`}
              </button>
            </div>
          </div>
        </div>
      )}
    </AdminLayout>
  );
}

