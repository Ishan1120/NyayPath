'use client';

import React, { useState, useEffect } from 'react';
import Link from 'next/link';
import { 
  GraduationCap, 
  ShieldCheck, 
  AlertTriangle, 
  CheckCircle2, 
  Clock, 
  FileText, 
  Users, 
  Building, 
  ArrowRight, 
  ArrowLeft, 
  Search, 
  Calendar, 
  Lock, 
  Send, 
  Copy, 
  Check, 
  Loader2, 
  Sparkles,
  Gavel,
  Eye,
  FileCheck2,
  RefreshCw,
  Key,
  LogOut,
  UserCheck,
  ShieldAlert
} from 'lucide-react';
import Navbar from '@/app/Navbar';
import { 
  submitCampusGrievance, 
  getCampusCase, 
  trackCampusGrievance,
  listCampusCases, 
  updateCampusCase, 
  getProctorNotice,
  loginProctor
} from '@/lib/api';

export default function CampusProctorPage() {
  const [activeTab, setActiveTab] = useState<'student' | 'proctor'>('student');

  // Student Intake Form State
  const [institutionId, setInstitutionId] = useState('INST_DEFAULT');
  const [studentName, setStudentName] = useState('');
  const [rollNumber, setRollNumber] = useState('');
  const [department, setDepartment] = useState('Computer Science & Engineering');
  const [year, setYear] = useState('3rd Year');
  const [category, setCategory] = useState('Hostel & Facilities');
  const [subject, setSubject] = useState('');
  const [description, setDescription] = useState('');
  const [incidentDate, setIncidentDate] = useState('');
  const [isAnonymous, setIsAnonymous] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const [submittedCase, setSubmittedCase] = useState<any | null>(null);

  // Student Case Lookup State
  const [lookupPasskey, setLookupPasskey] = useState('');
  const [lookupVerificationKey, setLookupVerificationKey] = useState('');
  const [trackedCase, setTrackedCase] = useState<any | null>(null);
  const [trackingLoading, setTrackingLoading] = useState(false);
  const [trackingError, setTrackingError] = useState<string | null>(null);

  // Proctor Authentication & Dashboard State
  const [proctorToken, setProctorToken] = useState<string | null>(null);
  const [proctorUser, setProctorUser] = useState<any | null>(null);
  const [loginInstitutionId, setLoginInstitutionId] = useState('INST_DEFAULT');
  const [loginAccessKey, setLoginAccessKey] = useState('');
  const [loginRole, setLoginRole] = useState('proctor');
  const [loginLoading, setLoginLoading] = useState(false);
  const [loginError, setLoginError] = useState<string | null>(null);

  const [proctorCases, setProctorCases] = useState<any[]>([]);
  const [proctorLoading, setProctorLoading] = useState(false);
  const [selectedCaseForAction, setSelectedCaseForAction] = useState<any | null>(null);
  const [newStatus, setNewStatus] = useState('UNDER_INQUIRY');
  const [proctorNotes, setProctorNotes] = useState('');
  const [hearingDate, setHearingDate] = useState('');
  const [actionTakenText, setActionTakenText] = useState('');
  const [updatingStatus, setUpdatingStatus] = useState(false);
  const [generatedNotice, setGeneratedNotice] = useState<string | null>(null);
  const [copiedNotice, setCopiedNotice] = useState(false);
  const [copiedPasskey, setCopiedPasskey] = useState(false);
  const [copiedVerificationKey, setCopiedVerificationKey] = useState(false);

  // Restore authenticated proctor session on mount
  useEffect(() => {
    if (typeof window !== 'undefined') {
      const savedToken = localStorage.getItem('nyaypath_proctor_token');
      const savedUser = localStorage.getItem('nyaypath_proctor_user');
      if (savedToken && savedUser) {
        try {
          setProctorToken(savedToken);
          setProctorUser(JSON.parse(savedUser));
        } catch {
          localStorage.removeItem('nyaypath_proctor_token');
          localStorage.removeItem('nyaypath_proctor_user');
        }
      }
    }
  }, []);

  useEffect(() => {
    if (activeTab === 'proctor' && proctorToken) {
      loadProctorCases();
    }
  }, [activeTab, proctorToken]);

  const loadProctorCases = () => {
    setProctorLoading(true);
    listCampusCases()
      .then((data) => {
        setProctorCases(data?.cases || []);
      })
      .catch((e) => {
        console.error('Failed to load campus cases', e);
        if (e?.response?.status === 401 || e?.response?.status === 403) {
          handleProctorLogout();
        }
      })
      .finally(() => setProctorLoading(false));
  };

  const handleProctorLogin = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!loginAccessKey.trim()) return;
    setLoginLoading(true);
    setLoginError(null);
    try {
      const res = await loginProctor({
        institution_id: loginInstitutionId.trim().toUpperCase(),
        access_key: loginAccessKey.trim(),
        role: loginRole
      });
      if (res?.token && res?.user) {
        setProctorToken(res.token);
        setProctorUser(res.user);
        localStorage.setItem('nyaypath_proctor_token', res.token);
        localStorage.setItem('nyaypath_proctor_user', JSON.stringify(res.user));
        loadProctorCases();
      } else {
        setLoginError('Authentication failed: Invalid credentials.');
      }
    } catch (err: any) {
      setLoginError(err?.response?.data?.detail || 'Invalid institutional credentials or unauthorized role requested.');
    } finally {
      setLoginLoading(false);
    }
  };

  const handleProctorLogout = () => {
    setProctorToken(null);
    setProctorUser(null);
    setProctorCases([]);
    setSelectedCaseForAction(null);
    localStorage.removeItem('nyaypath_proctor_token');
    localStorage.removeItem('nyaypath_proctor_user');
  };

  const handleStudentSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!subject.trim() || !description.trim()) return;

    setSubmitting(true);
    try {
      const res = await submitCampusGrievance({
        institution_id: institutionId,
        student_name: isAnonymous ? 'Confidential Student' : studentName,
        roll_number: isAnonymous ? 'Protected' : rollNumber,
        department,
        year,
        category,
        subject,
        description,
        incident_date: incidentDate || undefined,
        is_anonymous: isAnonymous
      });
      if (res?.case) {
        setSubmittedCase(res.case);
        setTrackedCase(res.case);
      }
    } catch (err) {
      console.error('Failed to submit grievance', err);
      alert('Grievance submission failed. Please check network connectivity.');
    } finally {
      setSubmitting(false);
    }
  };

  const handleTrackCase = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!lookupPasskey.trim()) return;

    setTrackingLoading(true);
    setTrackingError(null);
    try {
      // Use verification key tracking for confidentiality protection
      const res = await getCampusCase(lookupPasskey.trim(), lookupVerificationKey.trim() || undefined);
      if (res?.case) {
        setTrackedCase(res.case);
      } else {
        setTrackingError('No grievance found for this Campus ID.');
      }
    } catch (err: any) {
      if (err?.response?.status === 401 || err?.response?.status === 403) {
        setTrackingError('Access Denied: Case ID alone is insufficient. Please enter your secret Verification Key to view private grievance records.');
      } else {
        setTrackingError('Invalid Campus ID or grievance not found in registry.');
      }
    } finally {
      setTrackingLoading(false);
    }
  };

  const handleProctorUpdate = async () => {
    if (!selectedCaseForAction) return;
    setUpdatingStatus(true);
    try {
      const res = await updateCampusCase({
        case_id: selectedCaseForAction.case_id,
        new_status: newStatus,
        proctor_notes: proctorNotes,
        hearing_date: hearingDate || undefined,
        action_taken: actionTakenText || undefined
      });
      if (res?.case) {
        setSelectedCaseForAction(res.case);
        loadProctorCases();
        const noticeRes = await getProctorNotice(selectedCaseForAction.case_id);
        setGeneratedNotice(noticeRes?.notice_text || null);
      }
    } catch (e: any) {
      console.error('Failed to update case', e);
      alert(e?.response?.data?.detail || 'Failed to update case status.');
    } finally {
      setUpdatingStatus(false);
    }
  };

  return (
    <div className="min-h-screen bg-[#F8FAFC] text-slate-900 font-sans">
      <Navbar />

      <main className="max-w-6xl mx-auto px-4 sm:px-6 pt-28 pb-16">
        {/* Navigation Breadcrumb */}
        <div className="flex items-center justify-between mb-8">
          <Link
            href="/"
            className="inline-flex items-center gap-1.5 text-xs font-bold text-slate-600 hover:text-court-maroon transition-colors"
          >
            <ArrowLeft size={14} />
            <span>Back to Home</span>
          </Link>

          <div className="inline-flex items-center gap-1.5 px-3 py-1 rounded-full bg-blue-50 border border-blue-200 text-blue-800 text-xs font-semibold">
            <GraduationCap size={14} className="text-blue-600" />
            <span>UGC Mandated Student Grievance Redressal Committee (SGRC)</span>
          </div>
        </div>

        {/* Hero Section */}
        <div className="text-center max-w-3xl mx-auto mb-10">
          <div className="inline-flex items-center gap-2 px-3.5 py-1.5 rounded-full bg-rose-50 border border-rose-200 text-court-maroon text-xs font-bold mb-4 shadow-xs">
            <Gavel size={14} />
            <span>Campus Proctorial Governance &amp; Student Rights</span>
          </div>
          <h1 className="text-3xl sm:text-5xl font-black text-ashoka-navy tracking-tight mb-4">
            College Proctor &amp; Student Redressal
          </h1>
          <p className="text-sm sm:text-base text-slate-600 font-medium leading-relaxed">
            A transparent institutional bridge between college students and the Proctorial Grievance Cell. File campus grievances with zero fear of reprisal, track 15-day resolution SLAs, and generate formal Proctorial Inquiry Notices.
          </p>

          {/* Dual Perspective Switcher */}
          <div className="mt-8 inline-flex p-1.5 bg-slate-200/80 rounded-2xl shadow-inner border border-slate-300">
            <button
              onClick={() => setActiveTab('student')}
              className={`flex items-center gap-2 px-6 py-2.5 rounded-xl text-xs sm:text-sm font-bold transition-all cursor-pointer ${
                activeTab === 'student'
                  ? 'bg-white text-ashoka-navy shadow-md scale-100'
                  : 'text-slate-600 hover:text-slate-900'
              }`}
            >
              <Users size={16} className={activeTab === 'student' ? 'text-court-maroon' : 'text-slate-400'} />
              <span>Student Portal (File &amp; Track)</span>
            </button>

            <button
              onClick={() => setActiveTab('proctor')}
              className={`flex items-center gap-2 px-6 py-2.5 rounded-xl text-xs sm:text-sm font-bold transition-all cursor-pointer ${
                activeTab === 'proctor'
                  ? 'bg-ashoka-navy text-white shadow-md scale-100'
                  : 'text-slate-600 hover:text-slate-900'
              }`}
            >
              <ShieldCheck size={16} className={activeTab === 'proctor' ? 'text-amber-400' : 'text-slate-400'} />
              <span>Proctor / Committee Panel</span>
              {proctorToken && (
                <span className="w-2 h-2 rounded-full bg-emerald-400 animate-pulse ml-1" title="Authenticated" />
              )}
            </button>
          </div>
        </div>

        {/* ──────────────────────────────────────────────────────────────────
            TAB 1: STUDENT PORTAL
           ────────────────────────────────────────────────────────────────── */}
        {activeTab === 'student' && (
          <div className="grid grid-cols-1 lg:grid-cols-12 gap-8">
            {/* Left Column: File Grievance Form */}
            <div className="lg:col-span-7 bg-white p-6 sm:p-8 rounded-3xl border border-slate-200 shadow-sm">
              <div className="flex items-center justify-between pb-4 mb-6 border-b border-slate-100">
                <div className="flex items-center gap-2">
                  <div className="w-9 h-9 rounded-xl bg-rose-50 text-court-maroon flex items-center justify-center font-bold">
                    1
                  </div>
                  <div>
                    <h3 className="text-lg font-black text-ashoka-navy">File a Campus Grievance</h3>
                    <p className="text-xs text-slate-500 font-medium">Protected by the UGC Student Charter</p>
                  </div>
                </div>

                <div className="flex items-center gap-2 bg-slate-50 px-3 py-1 rounded-xl border border-slate-200">
                  <input
                    type="checkbox"
                    id="anon-check"
                    checked={isAnonymous}
                    onChange={(e) => setIsAnonymous(e.target.checked)}
                    className="w-4 h-4 text-court-maroon rounded border-slate-300 focus:ring-court-maroon cursor-pointer"
                  />
                  <label htmlFor="anon-check" className="text-xs font-bold text-slate-700 cursor-pointer select-none">
                    Confidential / Anonymous
                  </label>
                </div>
              </div>

              {submittedCase ? (
                <div className="bg-emerald-50 border border-emerald-200 rounded-3xl p-6 text-center animate-fade-in">
                  <div className="w-12 h-12 bg-emerald-100 text-emerald-700 rounded-full flex items-center justify-center mx-auto mb-3">
                    <CheckCircle2 size={24} />
                  </div>
                  <h4 className="text-xl font-black text-emerald-900 mb-1">
                    Grievance Successfully Registered!
                  </h4>
                  <p className="text-xs text-emerald-700 mb-5 font-medium">
                    Your issue has been routed to the Chief Proctor and Student Grievance Redressal Cell.
                  </p>

                  {/* Public Case ID & Secret Verification Key Card */}
                  <div className="bg-white p-5 rounded-2xl border border-emerald-200 mb-5 text-left shadow-xs space-y-4">
                    <div>
                      <span className="block text-[10px] font-bold text-slate-400 uppercase tracking-wider mb-1">
                        1. CAMPUS CASE ID (PUBLIC REFERENCE)
                      </span>
                      <div className="flex items-center justify-between bg-slate-50 p-2.5 rounded-xl border border-slate-200">
                        <span className="text-lg font-mono font-black text-court-maroon tracking-wider">
                          {submittedCase.case_id}
                        </span>
                        <button
                          onClick={() => {
                            navigator.clipboard.writeText(submittedCase.case_id);
                            setCopiedPasskey(true);
                            setTimeout(() => setCopiedPasskey(false), 2000);
                          }}
                          className="px-3 py-1 rounded-lg bg-slate-200 hover:bg-slate-300 text-slate-700 text-xs font-bold inline-flex items-center gap-1 cursor-pointer"
                        >
                          {copiedPasskey ? <Check size={12} className="text-emerald-600" /> : <Copy size={12} />}
                          <span>{copiedPasskey ? 'Copied' : 'Copy ID'}</span>
                        </button>
                      </div>
                    </div>

                    {submittedCase.verification_key && (
                      <div>
                        <div className="flex items-center justify-between mb-1">
                          <span className="text-[10px] font-bold text-rose-600 uppercase tracking-wider flex items-center gap-1">
                            <Key size={12} />
                            <span>2. SECRET VERIFICATION KEY (REQUIRED FOR TRACKING)</span>
                          </span>
                          <span className="text-[10px] font-bold text-rose-500 bg-rose-50 px-2 py-0.5 rounded">
                            Do Not Share
                          </span>
                        </div>
                        <div className="flex items-center justify-between bg-rose-50/70 p-2.5 rounded-xl border border-rose-200">
                          <span className="text-base font-mono font-black text-slate-900 tracking-wider">
                            {submittedCase.verification_key}
                          </span>
                          <button
                            onClick={() => {
                              navigator.clipboard.writeText(submittedCase.verification_key);
                              setCopiedVerificationKey(true);
                              setTimeout(() => setCopiedVerificationKey(false), 2000);
                            }}
                            className="px-3 py-1 rounded-lg bg-court-maroon hover:bg-rose-800 text-white text-xs font-bold inline-flex items-center gap-1 cursor-pointer"
                          >
                            {copiedVerificationKey ? <Check size={12} className="text-white" /> : <Copy size={12} />}
                            <span>{copiedVerificationKey ? 'Copied' : 'Copy Secret Key'}</span>
                          </button>
                        </div>
                        <p className="text-[11px] text-slate-500 mt-1.5 font-medium leading-relaxed">
                          🛡️ To protect student confidentiality, private case details cannot be opened without this Secret Verification Key.
                        </p>
                      </div>
                    )}
                  </div>

                  <div className="flex flex-col sm:flex-row gap-2 justify-center">
                    <button
                      onClick={() => setSubmittedCase(null)}
                      className="px-4 py-2 rounded-xl bg-emerald-600 hover:bg-emerald-700 text-white font-bold text-xs cursor-pointer shadow-sm"
                    >
                      File Another Grievance
                    </button>
                    <button
                      onClick={() => {
                        setLookupPasskey(submittedCase.case_id);
                        if (submittedCase.verification_key) {
                          setLookupVerificationKey(submittedCase.verification_key);
                        }
                        setSubmittedCase(null);
                      }}
                      className="px-4 py-2 rounded-xl bg-white text-slate-700 border border-slate-300 font-bold text-xs cursor-pointer hover:bg-slate-50"
                    >
                      View Live Case Status
                    </button>
                  </div>
                </div>
              ) : (
                <form onSubmit={handleStudentSubmit} className="space-y-4">
                  <div>
                    <label className="block text-xs font-bold text-slate-700 mb-1">College / Institution Identifier</label>
                    <select
                      value={institutionId}
                      onChange={(e) => setInstitutionId(e.target.value)}
                      className="w-full p-2.5 text-xs bg-slate-50 border border-slate-200 rounded-xl font-semibold text-slate-700"
                    >
                      <option value="INST_DEFAULT">National Institute of Technology (Default Campus)</option>
                      <option value="INST_UP_TECH">Uttar Pradesh Technical University (UP-TECH)</option>
                    </select>
                  </div>

                  {!isAnonymous && (
                    <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                      <div>
                        <label className="block text-xs font-bold text-slate-700 mb-1">Full Name</label>
                        <input
                          type="text"
                          value={studentName}
                          onChange={(e) => setStudentName(e.target.value)}
                          placeholder="e.g. Ishan Sharma"
                          className="w-full p-3 text-sm bg-slate-50 border border-slate-200 rounded-xl focus:outline-none focus:border-court-maroon font-medium"
                          required={!isAnonymous}
                        />
                      </div>
                      <div>
                        <label className="block text-xs font-bold text-slate-700 mb-1">Roll / Student ID</label>
                        <input
                          type="text"
                          value={rollNumber}
                          onChange={(e) => setRollNumber(e.target.value)}
                          placeholder="e.g. 22CS104"
                          className="w-full p-3 text-sm bg-slate-50 border border-slate-200 rounded-xl focus:outline-none focus:border-court-maroon font-medium"
                          required={!isAnonymous}
                        />
                      </div>
                    </div>
                  )}

                  <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
                    <div>
                      <label className="block text-xs font-bold text-slate-700 mb-1">Department</label>
                      <select
                        value={department}
                        onChange={(e) => setDepartment(e.target.value)}
                        className="w-full p-3 text-xs bg-slate-50 border border-slate-200 rounded-xl font-semibold text-slate-700"
                      >
                        <option>Computer Science & Engineering</option>
                        <option>Information Technology</option>
                        <option>Electronics & Communication</option>
                        <option>Mechanical Engineering</option>
                        <option>Civil Engineering</option>
                        <option>Management & Applied Sciences</option>
                      </select>
                    </div>

                    <div>
                      <label className="block text-xs font-bold text-slate-700 mb-1">Academic Year</label>
                      <select
                        value={year}
                        onChange={(e) => setYear(e.target.value)}
                        className="w-full p-3 text-xs bg-slate-50 border border-slate-200 rounded-xl font-semibold text-slate-700"
                      >
                        <option>1st Year</option>
                        <option>2nd Year</option>
                        <option>3rd Year</option>
                        <option>4th Year</option>
                        <option>Postgraduate / Research</option>
                      </select>
                    </div>

                    <div>
                      <label className="block text-xs font-bold text-slate-700 mb-1">Category</label>
                      <select
                        value={category}
                        onChange={(e) => setCategory(e.target.value)}
                        className="w-full p-3 text-xs bg-slate-50 border border-slate-200 rounded-xl font-semibold text-slate-700"
                      >
                        <option>Hostel & Facilities</option>
                        <option>Examination & Evaluation</option>
                        <option>Fee & Scholarship</option>
                        <option>Attendance & Disciplinary</option>
                        <option>Ragging / Harassment Cell</option>
                        <option>Library & Lab Infrastructure</option>
                      </select>
                    </div>
                  </div>

                  <div>
                    <label className="block text-xs font-bold text-slate-700 mb-1">Subject of Grievance</label>
                    <input
                      type="text"
                      value={subject}
                      onChange={(e) => setSubject(e.target.value)}
                      placeholder="e.g. Unclean drinking water in Boys Hostel Block B / Discrepancy in DBMS theory marks"
                      className="w-full p-3 text-sm bg-slate-50 border border-slate-200 rounded-xl focus:outline-none focus:border-court-maroon font-medium"
                      required
                    />
                  </div>

                  <div>
                    <label className="block text-xs font-bold text-slate-700 mb-1">
                      Detailed Factual Narrative &amp; Action Requested
                    </label>
                    <textarea
                      rows={4}
                      value={description}
                      onChange={(e) => setDescription(e.target.value)}
                      placeholder="State the facts clearly: date, location, persons involved, written requests ignored, and specific relief requested..."
                      className="w-full p-3 text-sm bg-slate-50 border border-slate-200 rounded-xl focus:outline-none focus:border-court-maroon font-medium"
                      required
                    />
                  </div>

                  <button
                    type="submit"
                    disabled={submitting || !subject.trim() || !description.trim()}
                    className="w-full py-3.5 rounded-xl bg-gradient-to-r from-court-maroon to-rose-700 hover:from-rose-700 hover:to-rose-800 text-white font-black text-sm tracking-tight shadow-md flex items-center justify-center gap-2 cursor-pointer disabled:opacity-40 transition-all"
                  >
                    {submitting ? <Loader2 size={16} className="animate-spin" /> : <Send size={16} />}
                    <span>Submit to Proctorial Grievance Cell</span>
                  </button>
                </form>
              )}
            </div>

            {/* Right Column: Track Existing Grievance */}
            <div className="lg:col-span-5 space-y-6">
              {/* Lookup Card */}
              <div className="bg-white p-6 rounded-3xl border border-slate-200 shadow-sm">
                <div className="flex items-center gap-2 mb-4 pb-3 border-b border-slate-100">
                  <div className="w-8 h-8 rounded-xl bg-blue-50 text-blue-700 flex items-center justify-center font-bold text-sm">
                    2
                  </div>
                  <div>
                    <h3 className="text-base font-black text-ashoka-navy">Track Status &amp; Hearing</h3>
                    <p className="text-[11px] text-slate-500 font-medium">Protected by Two-Factor Verification</p>
                  </div>
                </div>

                <form onSubmit={handleTrackCase} className="space-y-3 mb-4">
                  <div>
                    <label className="block text-[11px] font-bold text-slate-700 mb-1">Campus Case ID</label>
                    <input
                      type="text"
                      value={lookupPasskey}
                      onChange={(e) => setLookupPasskey(e.target.value.toUpperCase())}
                      placeholder="e.g. CAMPUS-E0B1-CO"
                      className="w-full p-2.5 text-xs font-mono font-bold bg-slate-50 border border-slate-200 rounded-xl focus:outline-none focus:border-court-maroon uppercase"
                      required
                    />
                  </div>

                  <div>
                    <label className="block text-[11px] font-bold text-slate-700 mb-1 flex items-center gap-1">
                      <Key size={12} className="text-court-maroon" />
                      <span>Secret Verification Key</span>
                    </label>
                    <input
                      type="text"
                      value={lookupVerificationKey}
                      onChange={(e) => setLookupVerificationKey(e.target.value.toUpperCase())}
                      placeholder="e.g. SEC-A8B9C1D2E3F4"
                      className="w-full p-2.5 text-xs font-mono font-bold bg-slate-50 border border-slate-200 rounded-xl focus:outline-none focus:border-court-maroon uppercase"
                      required
                    />
                    <span className="text-[10px] text-slate-400 block mt-1">
                      Required to verify ownership and prevent unauthorized access.
                    </span>
                  </div>

                  <button
                    type="submit"
                    disabled={trackingLoading || !lookupPasskey.trim() || !lookupVerificationKey.trim()}
                    className="w-full py-2.5 rounded-xl bg-slate-900 hover:bg-slate-800 text-white font-bold text-xs flex items-center justify-center gap-1.5 cursor-pointer disabled:opacity-40"
                  >
                    {trackingLoading ? <Loader2 size={13} className="animate-spin" /> : <Search size={13} />}
                    <span>Verify &amp; Track Status</span>
                  </button>
                </form>

                {trackingError && (
                  <p className="text-xs text-rose-600 font-medium p-2.5 bg-rose-50 rounded-xl border border-rose-200 flex items-start gap-1.5">
                    <ShieldAlert size={14} className="shrink-0 mt-0.5 text-rose-500" />
                    <span>{trackingError}</span>
                  </p>
                )}
              </div>

              {/* Tracked Case Details Card */}
              {trackedCase && (
                <div className="bg-white p-6 rounded-3xl border border-slate-200 shadow-sm space-y-4 animate-fade-in">
                  <div className="flex items-center justify-between">
                    <span className="font-mono text-xs font-black text-court-maroon">
                      {trackedCase.case_id}
                    </span>
                    <span className={`px-2.5 py-0.5 rounded-full text-[10px] font-bold ${
                      trackedCase.status === 'RESOLVED'
                        ? 'bg-emerald-100 text-emerald-800'
                        : trackedCase.status === 'HEARING_SCHEDULED'
                        ? 'bg-amber-100 text-amber-800 animate-pulse'
                        : 'bg-rose-100 text-rose-800'
                    }`}>
                      {trackedCase.status}
                    </span>
                  </div>

                  <h4 className="text-base font-black text-ashoka-navy leading-snug">
                    {trackedCase.subject}
                  </h4>

                  <div className="grid grid-cols-2 gap-2 text-xs bg-slate-50 p-3 rounded-xl">
                    <div>
                      <span className="text-slate-400 font-bold block text-[10px]">CATEGORY</span>
                      <span className="font-bold text-slate-700">{trackedCase.category}</span>
                    </div>
                    <div>
                      <span className="text-slate-400 font-bold block text-[10px]">SEVERITY</span>
                      <span className="font-bold text-rose-700">{trackedCase.severity}</span>
                    </div>
                  </div>

                  {/* Proctor's Live Note & Hearing */}
                  <div className="bg-rose-50/60 border border-rose-200 rounded-2xl p-3.5 space-y-2">
                    <div>
                      <span className="text-[10px] font-bold text-court-maroon uppercase tracking-wider block">
                        Chief Proctor Directive:
                      </span>
                      <p className="text-xs text-slate-800 font-medium leading-relaxed">
                        {trackedCase.proctor_notes || 'Grievance under initial administrative scrutiny.'}
                      </p>
                    </div>

                    {trackedCase.hearing_date && (
                      <div className="pt-2 border-t border-rose-200/60 flex items-center gap-1.5 text-xs text-rose-900 font-bold">
                        <Calendar size={13} className="text-court-maroon" />
                        <span>Hearing: {trackedCase.hearing_date}</span>
                      </div>
                    )}
                  </div>

                  {/* UGC 15-Day SLA Countdown Notice */}
                  <div className="flex items-center justify-between text-xs text-slate-500 pt-2 border-t border-slate-100">
                    <span className="flex items-center gap-1 font-medium">
                      <Clock size={12} />
                      <span>Resolution SLA Due: {trackedCase.resolution_deadline}</span>
                    </span>

                    <Link
                      href={`/dashboard`}
                      className="font-bold text-court-maroon hover:underline flex items-center gap-0.5"
                    >
                      <span>Escalate to RTI</span>
                      <ArrowRight size={11} />
                    </Link>
                  </div>
                </div>
              )}
            </div>
          </div>
        )}

        {/* ──────────────────────────────────────────────────────────────────
            TAB 2: PROCTOR / GRIEVANCE COMMITTEE DASHBOARD (AUTHENTICATED)
           ────────────────────────────────────────────────────────────────── */}
        {activeTab === 'proctor' && (
          <div className="space-y-8">
            {!proctorToken ? (
              /* PROCTOR AUTHENTICATION GATE */
              <div className="max-w-md mx-auto bg-white p-8 rounded-3xl border border-slate-200 shadow-md">
                <div className="w-12 h-12 bg-rose-50 text-court-maroon rounded-2xl flex items-center justify-center mx-auto mb-4">
                  <Lock size={22} />
                </div>
                <h3 className="text-xl font-black text-ashoka-navy text-center mb-1">
                  Proctorial Authority Access
                </h3>
                <p className="text-xs text-slate-500 text-center mb-6 font-medium">
                  Restricted to authorized Proctors, Grievance Committee Members, and Institutional Administrators.
                </p>

                <form onSubmit={handleProctorLogin} className="space-y-4">
                  <div>
                    <label className="block text-xs font-bold text-slate-700 mb-1">College / Institution ID</label>
                    <select
                      value={loginInstitutionId}
                      onChange={(e) => setLoginInstitutionId(e.target.value)}
                      className="w-full p-2.5 text-xs bg-slate-50 border border-slate-200 rounded-xl font-bold text-slate-700"
                    >
                      <option value="INST_DEFAULT">National Institute of Technology (INST_DEFAULT)</option>
                      <option value="INST_UP_TECH">UP Technical University (INST_UP_TECH)</option>
                    </select>
                  </div>

                  <div>
                    <label className="block text-xs font-bold text-slate-700 mb-1">Administrative Role</label>
                    <select
                      value={loginRole}
                      onChange={(e) => setLoginRole(e.target.value)}
                      className="w-full p-2.5 text-xs bg-slate-50 border border-slate-200 rounded-xl font-bold text-slate-700"
                    >
                      <option value="proctor">Chief Proctor / Deputy Proctor</option>
                      <option value="committee_member">Grievance Committee Member (SGRC)</option>
                      <option value="institution_admin">Institution Administrator</option>
                    </select>
                  </div>

                  <div>
                    <label className="block text-xs font-bold text-slate-700 mb-1">Institutional Access Key / Passkey</label>
                    <input
                      type="password"
                      value={loginAccessKey}
                      onChange={(e) => setLoginAccessKey(e.target.value)}
                      placeholder="Enter official institutional passkey"
                      className="w-full p-2.5 text-xs bg-slate-50 border border-slate-200 rounded-xl font-medium focus:border-court-maroon focus:outline-none"
                      required
                    />
                    <span className="text-[10px] text-slate-400 block mt-1">
                      Demo proctor key: <code className="bg-slate-100 px-1 py-0.5 rounded font-mono text-court-maroon font-bold">proctor-nyaypath-2026</code>
                    </span>
                  </div>

                  {loginError && (
                    <div className="p-2.5 bg-rose-50 border border-rose-200 rounded-xl text-xs text-rose-700 font-semibold flex items-center gap-1.5">
                      <ShieldAlert size={14} className="shrink-0 text-rose-600" />
                      <span>{loginError}</span>
                    </div>
                  )}

                  <button
                    type="submit"
                    disabled={loginLoading || !loginAccessKey.trim()}
                    className="w-full py-3 rounded-xl bg-ashoka-navy hover:bg-slate-900 text-white font-bold text-xs tracking-tight shadow-md flex items-center justify-center gap-2 cursor-pointer disabled:opacity-40 transition-all"
                  >
                    {loginLoading ? <Loader2 size={15} className="animate-spin" /> : <UserCheck size={15} />}
                    <span>Authenticate &amp; Enter Proctorial Panel</span>
                  </button>
                </form>
              </div>
            ) : (
              /* AUTHENTICATED PROCTOR PANEL */
              <>
                <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-4 bg-white p-5 rounded-3xl border border-slate-200 shadow-sm">
                  <div>
                    <div className="flex items-center gap-2 mb-1">
                      <span className="px-2.5 py-0.5 rounded-full text-[10px] font-black bg-emerald-50 text-emerald-800 border border-emerald-200 flex items-center gap-1">
                        <ShieldCheck size={12} className="text-emerald-600" />
                        <span>AUTHENTICATED: {proctorUser?.name || 'Chief Proctor'}</span>
                      </span>
                      <span className="text-xs font-mono font-bold text-slate-400">
                        [{proctorUser?.institution_id}]
                      </span>
                    </div>
                    <h3 className="text-xl font-black text-ashoka-navy">Proctorial Inquiries Queue</h3>
                    <p className="text-xs text-slate-500 font-medium">
                      Review grievances, issue hearing notices, and upload Action Taken Reports (ATRs)
                    </p>
                  </div>

                  <div className="flex items-center gap-2">
                    <button
                      onClick={loadProctorCases}
                      className="px-3 py-1.5 rounded-xl bg-slate-100 hover:bg-slate-200 text-slate-700 text-xs font-bold flex items-center gap-1.5 cursor-pointer"
                    >
                      <RefreshCw size={13} className={proctorLoading ? 'animate-spin' : ''} />
                      <span>Refresh Queue</span>
                    </button>

                    <button
                      onClick={handleProctorLogout}
                      className="px-3 py-1.5 rounded-xl bg-rose-50 hover:bg-rose-100 text-court-maroon text-xs font-bold flex items-center gap-1.5 cursor-pointer border border-rose-200"
                    >
                      <LogOut size={13} />
                      <span>Sign Out</span>
                    </button>
                  </div>
                </div>

                {/* Cases Queue Table */}
                <div className="bg-white rounded-3xl border border-slate-200 shadow-sm overflow-hidden">
                  <div className="overflow-x-auto">
                    <table className="w-full text-left text-xs">
                      <thead className="bg-slate-50 border-b border-slate-200 text-slate-600 font-bold uppercase tracking-wider">
                        <tr>
                          <th className="p-4">Case ID</th>
                          <th className="p-4">Complainant / Dept</th>
                          <th className="p-4">Category &amp; Subject</th>
                          <th className="p-4">Severity</th>
                          <th className="p-4">Status</th>
                          <th className="p-4 text-right">Action</th>
                        </tr>
                      </thead>
                      <tbody className="divide-y divide-slate-100 font-medium">
                        {proctorCases.length === 0 ? (
                          <tr>
                            <td colSpan={6} className="p-8 text-center text-slate-400">
                              No active grievances recorded in this institutional queue.
                            </td>
                          </tr>
                        ) : (
                          proctorCases.map((c) => (
                            <tr key={c.case_id} className="hover:bg-slate-50/70 transition-colors">
                              <td className="p-4 font-mono font-bold text-court-maroon">{c.case_id}</td>
                              <td className="p-4">
                                <span className="font-bold text-slate-800 block">{c.student_name}</span>
                                <span className="text-[11px] text-slate-400">{c.department}</span>
                              </td>
                              <td className="p-4 max-w-xs">
                                <span className="font-bold text-slate-800 block truncate">{c.subject}</span>
                                <span className="text-[11px] text-slate-500">{c.category}</span>
                              </td>
                              <td className="p-4">
                                <span className={`px-2 py-0.5 rounded-full text-[10px] font-bold ${
                                  c.severity === 'URGENT'
                                    ? 'bg-rose-100 text-rose-800'
                                    : c.severity === 'HIGH'
                                    ? 'bg-amber-100 text-amber-800'
                                    : 'bg-slate-100 text-slate-700'
                                }`}>
                                  {c.severity}
                                </span>
                              </td>
                              <td className="p-4">
                                <span className="px-2.5 py-0.5 rounded-full text-[10px] font-bold bg-blue-50 text-blue-800 border border-blue-200">
                                  {c.status}
                                </span>
                              </td>
                              <td className="p-4 text-right">
                                <button
                                  onClick={() => {
                                    setSelectedCaseForAction(c);
                                    setNewStatus(c.status);
                                    setProctorNotes(c.proctor_notes || '');
                                    setHearingDate(c.hearing_date || '');
                                    setActionTakenText(c.action_taken || '');
                                    setGeneratedNotice(null);
                                  }}
                                  className="px-3 py-1.5 rounded-xl bg-court-maroon hover:bg-rose-800 text-white font-bold text-xs cursor-pointer shadow-xs"
                                >
                                  Manage Case
                                </button>
                              </td>
                            </tr>
                          ))
                        )}
                      </tbody>
                    </table>
                  </div>
                </div>

                {/* Proctor Action Modal / Inspector */}
                {selectedCaseForAction && (
                  <div className="bg-white p-6 sm:p-8 rounded-3xl border-2 border-court-maroon/20 shadow-xl animate-fade-in">
                    <div className="flex items-center justify-between pb-4 mb-6 border-b border-slate-200">
                      <div>
                        <span className="text-xs font-mono font-black text-court-maroon block">
                          CASE PROCEEDINGS: {selectedCaseForAction.case_id}
                        </span>
                        <h3 className="text-xl font-black text-ashoka-navy">
                          {selectedCaseForAction.subject}
                        </h3>
                      </div>

                      <button
                        onClick={() => setSelectedCaseForAction(null)}
                        className="text-xs font-bold text-slate-400 hover:text-slate-700 px-3 py-1 rounded-lg border border-slate-200"
                      >
                        Close
                      </button>
                    </div>

                    <div className="grid grid-cols-1 md:grid-cols-3 gap-6 mb-6">
                      <div>
                        <label className="block text-xs font-bold text-slate-700 mb-1">Update Status</label>
                        <select
                          value={newStatus}
                          onChange={(e) => setNewStatus(e.target.value)}
                          className="w-full p-2.5 text-xs bg-slate-50 border border-slate-300 rounded-xl font-bold text-slate-800"
                        >
                          <option value="SUBMITTED">SUBMITTED</option>
                          <option value="UNDER_INQUIRY">UNDER_INQUIRY</option>
                          <option value="HEARING_SCHEDULED">HEARING_SCHEDULED</option>
                          <option value="ACTION_TAKEN">ACTION_TAKEN</option>
                          <option value="RESOLVED">RESOLVED</option>
                          <option value="CLOSED">CLOSED</option>
                        </select>
                      </div>

                      <div>
                        <label className="block text-xs font-bold text-slate-700 mb-1">Hearing Date &amp; Venue</label>
                        <input
                          type="text"
                          value={hearingDate}
                          onChange={(e) => setHearingDate(e.target.value)}
                          placeholder="e.g. 05-Nov-2026 at 11:30 AM (Room 102)"
                          className="w-full p-2.5 text-xs bg-slate-50 border border-slate-300 rounded-xl font-medium"
                        />
                      </div>

                      <div>
                        <label className="block text-xs font-bold text-slate-700 mb-1">Action Taken Summary</label>
                        <input
                          type="text"
                          value={actionTakenText}
                          onChange={(e) => setActionTakenText(e.target.value)}
                          placeholder="e.g. Filter replaced / Ledger audited"
                          className="w-full p-2.5 text-xs bg-slate-50 border border-slate-300 rounded-xl font-medium"
                        />
                      </div>
                    </div>

                    <div className="mb-6">
                      <label className="block text-xs font-bold text-slate-700 mb-1">
                        Official Proctorial Notes &amp; Committee Directive
                      </label>
                      <textarea
                        rows={3}
                        value={proctorNotes}
                        onChange={(e) => setProctorNotes(e.target.value)}
                        placeholder="Enter formal findings, summoned authorities, or administrative directives..."
                        className="w-full p-3 text-xs bg-slate-50 border border-slate-300 rounded-xl font-medium"
                      />
                    </div>

                    <div className="flex flex-wrap items-center gap-3">
                      <button
                        onClick={handleProctorUpdate}
                        disabled={updatingStatus}
                        className="px-6 py-3 rounded-xl bg-slate-900 hover:bg-slate-800 text-white font-bold text-xs flex items-center gap-2 shadow-sm cursor-pointer disabled:opacity-40"
                      >
                        {updatingStatus ? <Loader2 size={14} className="animate-spin" /> : <FileCheck2 size={14} />}
                        <span>Save Update &amp; Generate Formal Notice</span>
                      </button>

                      <button
                        onClick={async () => {
                          const res = await getProctorNotice(selectedCaseForAction.case_id);
                          setGeneratedNotice(res?.notice_text || null);
                        }}
                        className="px-4 py-3 rounded-xl bg-slate-100 hover:bg-slate-200 text-slate-700 font-bold text-xs flex items-center gap-1.5 cursor-pointer"
                      >
                        <FileText size={14} />
                        <span>View Notice Template</span>
                      </button>
                    </div>

                    {/* Generated Proctorial Notice Display */}
                    {generatedNotice && (
                      <div className="mt-6 bg-slate-950 text-emerald-400 p-6 rounded-2xl font-mono text-xs shadow-inner relative">
                        <div className="flex items-center justify-between mb-3 pb-2 border-b border-slate-800">
                          <span className="text-slate-400 font-bold">OFFICIAL PROCTORIAL NOTICE DOCUMENT:</span>
                          <button
                            onClick={() => {
                              navigator.clipboard.writeText(generatedNotice);
                              setCopiedNotice(true);
                              setTimeout(() => setCopiedNotice(false), 2000);
                            }}
                            className="px-3 py-1 bg-slate-800 hover:bg-slate-700 text-slate-200 rounded-lg text-[11px] font-bold flex items-center gap-1 cursor-pointer"
                          >
                            {copiedNotice ? <Check size={12} className="text-emerald-400" /> : <Copy size={12} />}
                            <span>{copiedNotice ? 'Notice Copied!' : 'Copy Notice'}</span>
                          </button>
                        </div>
                        <pre className="whitespace-pre-wrap leading-relaxed select-all">
                          {generatedNotice}
                        </pre>
                      </div>
                    )}
                  </div>
                )}
              </>
            )}
          </div>
        )}
      </main>
    </div>
  );
}
