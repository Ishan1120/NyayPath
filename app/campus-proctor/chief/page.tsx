'use client';

import React, { useState, useEffect } from 'react';
import Link from 'next/link';
import { 
  ShieldCheck, 
  Users, 
  Clock, 
  Calendar, 
  AlertTriangle, 
  CheckCircle2, 
  Search, 
  UserPlus, 
  UserMinus, 
  FileText, 
  RefreshCw, 
  ChevronRight, 
  ChevronLeft,
  Building,
  Gavel,
  Lock,
  ArrowRight
} from 'lucide-react';
import Navbar from '@/app/Navbar';
import {
  getChiefTriageQueue,
  getInstitutionCommitteeRoster,
  assignCaseCommitteeMember,
  revokeCaseCommitteeMember,
  getCaseCommitteeAssignments,
  updateCampusCase,
  getCampusCase,
  listCampusCases
} from '@/lib/api';

export default function ChiefProctorWorkspace() {
  const [activeTab, setActiveTab] = useState<'triage' | 'active_cases' | 'committees'>('triage');
  const [triageCases, setTriageCases] = useState<any[]>([]);
  const [activeCases, setActiveCases] = useState<any[]>([]);
  const [committeeRoster, setCommitteeRoster] = useState<any[]>([]);
  const [loading, setLoading] = useState<boolean>(true);
  const [errorMsg, setErrorMsg] = useState<string | null>(null);

  // Assignment Modal
  const [assignModalCase, setAssignModalCase] = useState<any | null>(null);
  const [selectedProctorUser, setSelectedProctorUser] = useState<string>('');
  const [assignHearingDate, setAssignHearingDate] = useState<string>('');
  const [assignNotes, setAssignNotes] = useState<string>('');
  const [assignLoading, setAssignLoading] = useState<boolean>(false);

  // Committee Modal
  const [committeeModalCase, setCommitteeModalCase] = useState<any | null>(null);
  const [existingAssignments, setExistingAssignments] = useState<any[]>([]);
  const [targetMemberId, setTargetMemberId] = useState<string>('');
  const [targetRole, setTargetRole] = useState<string>('member');
  const [targetCommitteeName, setTargetCommitteeName] = useState<string>('Campus Inquiry Committee');
  const [committeeLoading, setCommitteeLoading] = useState<boolean>(false);

  useEffect(() => {
    fetchData();
  }, [activeTab]);

  const fetchData = async () => {
    setLoading(true);
    setErrorMsg(null);
    try {
      if (activeTab === 'triage') {
        const res = await getChiefTriageQueue();
        setTriageCases(res.cases || []);
      } else if (activeTab === 'active_cases') {
        const res = await listCampusCases();
        setActiveCases(res.cases || []);
      }
      const rosterRes = await getInstitutionCommitteeRoster();
      setCommitteeRoster(rosterRes.roster || []);
    } catch (err: any) {
      console.error('Error fetching chief proctor data', err);
      setErrorMsg(err.response?.data?.detail || 'Failed to load Chief Proctor workspace data.');
    } finally {
      setLoading(false);
    }
  };

  const openAssignModal = (c: any) => {
    setAssignModalCase(c);
    setSelectedProctorUser(c.assigned_proctor_user_id || '');
    setAssignHearingDate(c.hearing_date || '');
    setAssignNotes(c.proctor_notes || '');
  };

  const handleProctorAssignment = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!assignModalCase || !selectedProctorUser) return;
    setAssignLoading(true);
    try {
      const selectedMember = committeeRoster.find(m => m.user_id === selectedProctorUser);
      await updateCampusCase({
        case_id: assignModalCase.case_id,
        new_status: 'UNDER_INQUIRY',
        proctor_notes: assignNotes || `Assigned to ${selectedMember?.full_name || 'Inquiry Officer'} by Chief Proctor.`,
        assigned_proctor_user_id: selectedProctorUser,
        hearing_date: assignHearingDate || undefined
      });
      setAssignModalCase(null);
      await fetchData();
    } catch (err: any) {
      alert(err.response?.data?.detail || 'Failed to assign proctor');
    } finally {
      setAssignLoading(false);
    }
  };

  const openCommitteeModal = async (c: any) => {
    setCommitteeModalCase(c);
    setCommitteeLoading(true);
    try {
      const res = await getCaseCommitteeAssignments(c.case_id);
      setExistingAssignments(res.assignments || []);
    } catch (err) {
      console.error('Failed to load assignments', err);
    } finally {
      setCommitteeLoading(false);
    }
  };

  const handleAppointCommittee = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!committeeModalCase || !targetMemberId) return;
    setCommitteeLoading(true);
    try {
      await assignCaseCommitteeMember({
        case_id: committeeModalCase.case_id,
        target_user_id: targetMemberId,
        role: targetRole,
        committee_name: targetCommitteeName
      });
      const res = await getCaseCommitteeAssignments(committeeModalCase.case_id);
      setExistingAssignments(res.assignments || []);
      setTargetMemberId('');
    } catch (err: any) {
      alert(err.response?.data?.detail || 'Failed to appoint committee member');
    } finally {
      setCommitteeLoading(false);
    }
  };

  const handleRevokeCommittee = async (targetUserId: string) => {
    if (!committeeModalCase) return;
    if (!confirm('Are you sure you want to revoke this committee appointment?')) return;
    setCommitteeLoading(true);
    try {
      await revokeCaseCommitteeMember({
        case_id: committeeModalCase.case_id,
        target_user_id: targetUserId
      });
      const res = await getCaseCommitteeAssignments(committeeModalCase.case_id);
      setExistingAssignments(res.assignments || []);
    } catch (err: any) {
      alert(err.response?.data?.detail || 'Failed to revoke committee assignment');
    } finally {
      setCommitteeLoading(false);
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
              <span className="p-2.5 bg-amber-50 border border-amber-100 rounded-xl text-amber-700">
                <ShieldCheck className="w-6 h-6" />
              </span>
              <div>
                <div className="flex items-center gap-2">
                  <h1 className="text-2xl font-black text-slate-900 tracking-tight">
                    Chief Proctor & Ombudsman Workspace
                  </h1>
                  <span className="text-xs font-bold px-2.5 py-0.5 rounded-full bg-amber-100 text-amber-800 border border-amber-200">
                    CHIEF PROCTOR
                  </span>
                </div>
                <p className="text-sm text-slate-500 mt-0.5">
                  Triage Unassigned Grievances, Form Inquiry Committees & Coordinate Hearings
                </p>
              </div>
            </div>

            <div className="flex items-center gap-2">
              <Link
                href="/institution/dashboard"
                className="px-3.5 py-2 text-xs font-semibold text-slate-700 bg-slate-100 hover:bg-slate-200 rounded-lg transition-colors flex items-center gap-1.5"
              >
                <Building className="w-4 h-4 text-slate-500" />
                Institution Admin
              </Link>
              <button
                onClick={fetchData}
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
                <p className="font-semibold">Access Notice</p>
                <p className="text-xs text-amber-700 mt-0.5">{errorMsg}</p>
              </div>
            </div>
          )}
        </div>

        {/* Tab Selection */}
        <div className="flex border-b border-slate-200 mb-6 gap-2">
          <button
            onClick={() => setActiveTab('triage')}
            className={`pb-3 px-4 text-sm font-bold border-b-2 transition-colors flex items-center gap-2 cursor-pointer ${
              activeTab === 'triage'
                ? 'border-amber-600 text-amber-700'
                : 'border-transparent text-slate-500 hover:text-slate-800'
            }`}
          >
            <Clock className="w-4 h-4" />
            Triage Queue ({triageCases.length})
          </button>
          <button
            onClick={() => setActiveTab('active_cases')}
            className={`pb-3 px-4 text-sm font-bold border-b-2 transition-colors flex items-center gap-2 cursor-pointer ${
              activeTab === 'active_cases'
                ? 'border-amber-600 text-amber-700'
                : 'border-transparent text-slate-500 hover:text-slate-800'
            }`}
          >
            <ShieldCheck className="w-4 h-4" />
            Active Institutional Inquiries ({activeCases.length})
          </button>
        </div>

        {/* Tab 1: Triage Queue */}
        {activeTab === 'triage' && (
          <div className="bg-white border border-slate-200 rounded-2xl shadow-sm p-6">
            <div className="mb-4">
              <h2 className="text-lg font-bold text-slate-900">Unassigned Grievances Requiring Triage</h2>
              <p className="text-xs text-slate-500">
                Assign an inquiry proctor or form a special investigation committee to initiate proceedings
              </p>
            </div>

            {loading ? (
              <div className="py-16 text-center text-slate-400 text-sm">Loading unassigned queue...</div>
            ) : triageCases.length === 0 ? (
              <div className="py-16 text-center text-slate-500 text-sm">
                No unassigned grievances currently in the triage queue.
              </div>
            ) : (
              <div className="overflow-x-auto">
                <table className="w-full text-left text-sm text-slate-600">
                  <thead className="bg-slate-50 border-y border-slate-200 text-xs font-bold text-slate-500 uppercase">
                    <tr>
                      <th className="py-3 px-4">Case Ref</th>
                      <th className="py-3 px-4">Complainant & Subject</th>
                      <th className="py-3 px-4">Category</th>
                      <th className="py-3 px-4">Severity</th>
                      <th className="py-3 px-4">Filing Date</th>
                      <th className="py-3 px-4 text-right">Triage Actions</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-slate-100">
                    {triageCases.map((c) => (
                      <tr key={c.case_id} className="hover:bg-slate-50/60">
                        <td className="py-3 px-4 font-mono font-bold text-slate-900">{c.case_id}</td>
                        <td className="py-3 px-4 max-w-sm">
                          <div className="font-semibold text-slate-900">{c.subject}</div>
                          <div className="text-xs text-slate-500">
                            {c.is_anonymous ? 'Anonymous / Protected' : c.student_name}
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
                            'bg-blue-100 text-blue-800'
                          }`}>
                            {c.severity}
                          </span>
                        </td>
                        <td className="py-3 px-4 text-xs text-slate-500">
                          {c.created_at ? new Date(c.created_at).toLocaleDateString() : ''}
                        </td>
                        <td className="py-3 px-4 text-right">
                          <div className="flex items-center justify-end gap-2">
                            <button
                              onClick={() => openAssignModal(c)}
                              className="px-3 py-1.5 text-xs font-bold text-amber-800 bg-amber-50 hover:bg-amber-100 rounded-lg transition-colors cursor-pointer"
                            >
                              Assign Proctor
                            </button>
                            <button
                              onClick={() => openCommitteeModal(c)}
                              className="px-3 py-1.5 text-xs font-bold text-indigo-700 bg-indigo-50 hover:bg-indigo-100 rounded-lg transition-colors cursor-pointer"
                            >
                              Form Committee
                            </button>
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

        {/* Tab 2: Active Institutional Inquiries */}
        {activeTab === 'active_cases' && (
          <div className="bg-white border border-slate-200 rounded-2xl shadow-sm p-6">
            <div className="mb-4">
              <h2 className="text-lg font-bold text-slate-900">Institutional Inquiries Oversight</h2>
              <p className="text-xs text-slate-500">
                Monitor investigation progress, hearing schedules, and committee composition
              </p>
            </div>

            {loading ? (
              <div className="py-16 text-center text-slate-400 text-sm">Loading active inquiries...</div>
            ) : activeCases.length === 0 ? (
              <div className="py-16 text-center text-slate-500 text-sm">No active campus cases.</div>
            ) : (
              <div className="overflow-x-auto">
                <table className="w-full text-left text-sm text-slate-600">
                  <thead className="bg-slate-50 border-y border-slate-200 text-xs font-bold text-slate-500 uppercase">
                    <tr>
                      <th className="py-3 px-4">Case Ref</th>
                      <th className="py-3 px-4">Subject</th>
                      <th className="py-3 px-4">Status</th>
                      <th className="py-3 px-4">Assigned Proctor</th>
                      <th className="py-3 px-4">Hearing Date</th>
                      <th className="py-3 px-4 text-right">Actions</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-slate-100">
                    {activeCases.map((c) => (
                      <tr key={c.case_id} className="hover:bg-slate-50/60">
                        <td className="py-3 px-4 font-mono font-bold text-slate-900">{c.case_id}</td>
                        <td className="py-3 px-4 font-medium text-slate-900 max-w-xs truncate">{c.subject}</td>
                        <td className="py-3 px-4">
                          <span className={`text-[11px] font-bold px-2.5 py-0.5 rounded-full ${
                            c.status === 'RESOLVED' || c.status === 'CLOSED' ? 'bg-emerald-100 text-emerald-800' :
                            c.status === 'HEARING_SCHEDULED' ? 'bg-purple-100 text-purple-800' :
                            'bg-blue-100 text-blue-800'
                          }`}>
                            {c.status}
                          </span>
                        </td>
                        <td className="py-3 px-4 text-xs font-medium text-slate-800">
                          {c.assigned_proctor || <span className="text-amber-600 italic">Unassigned</span>}
                        </td>
                        <td className="py-3 px-4 text-xs text-slate-500">
                          {c.hearing_date || 'None'}
                        </td>
                        <td className="py-3 px-4 text-right">
                          <button
                            onClick={() => openCommitteeModal(c)}
                            className="px-3 py-1.5 text-xs font-bold text-indigo-700 bg-indigo-50 hover:bg-indigo-100 rounded-lg cursor-pointer"
                          >
                            Committee ({c.assigned_committee ? 'Active' : 'Configure'})
                          </button>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </div>
        )}
      </main>

      {/* Proctor Assignment Modal */}
      {assignModalCase && (
        <div className="fixed inset-0 z-50 bg-slate-900/40 backdrop-blur-sm flex items-center justify-center p-4">
          <form onSubmit={handleProctorAssignment} className="bg-white rounded-2xl max-w-lg w-full p-6 shadow-xl border border-slate-200">
            <h3 className="text-lg font-bold text-slate-900 mb-1">Assign Presiding Proctor</h3>
            <p className="text-xs text-slate-500 mb-4 font-mono">Case: {assignModalCase.case_id} — {assignModalCase.subject}</p>

            <div className="space-y-4 text-xs">
              <div>
                <label className="font-bold text-slate-700 block mb-1">Select Inquiry Proctor</label>
                <select
                  required
                  value={selectedProctorUser}
                  onChange={(e) => setSelectedProctorUser(e.target.value)}
                  className="w-full p-2.5 border border-slate-200 rounded-xl focus:ring-2 focus:ring-amber-500"
                >
                  <option value="">Choose an eligible officer...</option>
                  {committeeRoster.map(m => (
                    <option key={m.user_id} value={m.user_id}>
                      {m.full_name} ({m.role.toUpperCase()})
                    </option>
                  ))}
                </select>
              </div>

              <div>
                <label className="font-bold text-slate-700 block mb-1">Schedule Hearing Date (Optional)</label>
                <input
                  type="date"
                  value={assignHearingDate}
                  onChange={(e) => setAssignHearingDate(e.target.value)}
                  className="w-full p-2.5 border border-slate-200 rounded-xl"
                />
              </div>

              <div>
                <label className="font-bold text-slate-700 block mb-1">Directive / Initial Proctor Notes</label>
                <textarea
                  rows={3}
                  value={assignNotes}
                  onChange={(e) => setAssignNotes(e.target.value)}
                  placeholder="Enter initial inquiry instructions..."
                  className="w-full p-2.5 border border-slate-200 rounded-xl"
                />
              </div>
            </div>

            <div className="mt-6 flex justify-end gap-2">
              <button
                type="button"
                onClick={() => setAssignModalCase(null)}
                className="px-4 py-2 bg-slate-100 hover:bg-slate-200 text-slate-700 font-bold text-xs rounded-xl cursor-pointer"
              >
                Cancel
              </button>
              <button
                type="submit"
                disabled={assignLoading || !selectedProctorUser}
                className="px-4 py-2 bg-amber-600 hover:bg-amber-700 text-white font-bold text-xs rounded-xl disabled:opacity-50 cursor-pointer"
              >
                {assignLoading ? 'Assigning...' : 'Confirm Assignment'}
              </button>
            </div>
          </form>
        </div>
      )}

      {/* Committee Formation & Revocation Modal */}
      {committeeModalCase && (
        <div className="fixed inset-0 z-50 bg-slate-900/40 backdrop-blur-sm flex items-center justify-center p-4">
          <div className="bg-white rounded-2xl max-w-xl w-full p-6 shadow-xl border border-slate-200 max-h-[85vh] overflow-y-auto">
            <div className="flex justify-between items-start mb-4">
              <div>
                <h3 className="text-lg font-bold text-slate-900">Inquiry Committee Appointments</h3>
                <p className="text-xs text-slate-500 font-mono">Case: {committeeModalCase.case_id}</p>
              </div>
              <button
                onClick={() => setCommitteeModalCase(null)}
                className="text-slate-400 hover:text-slate-600 font-bold cursor-pointer"
              >
                ✕
              </button>
            </div>

            {/* Existing Committee Members */}
            <div className="mb-6">
              <h4 className="text-xs font-bold text-slate-700 uppercase mb-2">Active Committee Members</h4>
              {existingAssignments.filter(a => a.assignment_status === 'active').length === 0 ? (
                <p className="text-xs text-slate-400 italic p-3 bg-slate-50 rounded-xl">
                  No committee members currently appointed to this inquiry.
                </p>
              ) : (
                <div className="space-y-2">
                  {existingAssignments.filter(a => a.assignment_status === 'active').map((a) => (
                    <div key={a.id || a.user_id} className="flex items-center justify-between p-3 bg-slate-50 border border-slate-200 rounded-xl text-xs">
                      <div>
                        <div className="font-bold text-slate-900 font-mono">{a.user_id}</div>
                        <div className="text-[11px] text-slate-500">Role: <span className="font-semibold uppercase">{a.role}</span> | {a.committee_name || 'Inquiry Committee'}</div>
                      </div>
                      <button
                        onClick={() => handleRevokeCommittee(a.user_id)}
                        className="px-2.5 py-1 bg-rose-50 text-rose-700 hover:bg-rose-100 rounded text-xs font-bold cursor-pointer"
                      >
                        Revoke
                      </button>
                    </div>
                  ))}
                </div>
              )}
            </div>

            {/* Appoint New Member Form */}
            <form onSubmit={handleAppointCommittee} className="p-4 bg-indigo-50/50 border border-indigo-100 rounded-xl space-y-3 text-xs">
              <h4 className="font-bold text-indigo-950 uppercase tracking-wide">Appoint New Inquiry Member</h4>

              <div>
                <label className="font-semibold text-slate-700 block mb-1">Select Member from Roster</label>
                <select
                  required
                  value={targetMemberId}
                  onChange={(e) => setTargetMemberId(e.target.value)}
                  className="w-full p-2 border border-slate-200 rounded-lg bg-white"
                >
                  <option value="">Select an active member...</option>
                  {committeeRoster.map(m => (
                    <option key={m.user_id} value={m.user_id}>
                      {m.full_name} ({m.designation || m.role})
                    </option>
                  ))}
                </select>
              </div>

              <div className="grid grid-cols-2 gap-2">
                <div>
                  <label className="font-semibold text-slate-700 block mb-1">Inquiry Role</label>
                  <select
                    value={targetRole}
                    onChange={(e) => setTargetRole(e.target.value)}
                    className="w-full p-2 border border-slate-200 rounded-lg bg-white"
                  >
                    <option value="member">Committee Member</option>
                    <option value="chair">Committee Chair</option>
                    <option value="convenor">Convenor</option>
                    <option value="investigator">Lead Investigator</option>
                  </select>
                </div>
                <div>
                  <label className="font-semibold text-slate-700 block mb-1">Committee Title</label>
                  <input
                    type="text"
                    value={targetCommitteeName}
                    onChange={(e) => setTargetCommitteeName(e.target.value)}
                    className="w-full p-2 border border-slate-200 rounded-lg bg-white"
                  />
                </div>
              </div>

              <button
                type="submit"
                disabled={committeeLoading || !targetMemberId}
                className="w-full py-2 bg-indigo-600 hover:bg-indigo-700 text-white font-bold rounded-lg transition-colors cursor-pointer disabled:opacity-50"
              >
                {committeeLoading ? 'Appointing...' : 'Appoint to Case Inquiry'}
              </button>
            </form>
          </div>
        </div>
      )}
    </div>
  );
}
