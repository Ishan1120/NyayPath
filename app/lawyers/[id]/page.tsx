'use client';

import React, { useState, useEffect } from 'react';
import Link from 'next/link';
import { useParams, useRouter } from 'next/navigation';
import { 
  ShieldCheck, 
  MapPin, 
  Scale, 
  Languages, 
  Calendar, 
  Clock, 
  ArrowLeft, 
  FileText, 
  CheckCircle2, 
  AlertCircle,
  Briefcase,
  ExternalLink,
  Send
} from 'lucide-react';
import Navbar from '@/app/Navbar';
import { getLawyerProfile, requestConsultation, LawyerProfile } from '@/lib/api';

export default function LawyerDetailPage() {
  const params = useParams();
  const router = useRouter();
  const lawyerId = params?.id as string;

  const [lawyer, setLawyer] = useState<LawyerProfile | null>(null);
  const [loading, setLoading] = useState<boolean>(true);
  const [errorMsg, setErrorMsg] = useState<string | null>(null);

  // Consultation Modal State
  const [modalOpen, setModalOpen] = useState<boolean>(false);
  const [legalIssue, setLegalIssue] = useState<string>('');
  const [description, setDescription] = useState<string>('');
  const [preferredMode, setPreferredMode] = useState<string>('ONLINE');
  const [caseId, setCaseId] = useState<string>('');
  const [submitting, setSubmitting] = useState<boolean>(false);
  const [successNotice, setSuccessNotice] = useState<boolean>(false);

  useEffect(() => {
    if (lawyerId) {
      fetchLawyer();
    }
  }, [lawyerId]);

  const fetchLawyer = async () => {
    setLoading(true);
    setErrorMsg(null);
    try {
      const data = await getLawyerProfile(lawyerId);
      setLawyer(data);
    } catch (err: any) {
      console.error('Failed to load lawyer profile', err);
      setErrorMsg(err.response?.data?.detail || 'Lawyer profile not found or currently unverified.');
    } finally {
      setLoading(false);
    }
  };

  const handleConsultationSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!legalIssue.trim() || !description.trim()) return;
    setSubmitting(true);
    try {
      await requestConsultation({
        lawyer_user_id: lawyerId,
        case_id: caseId.trim() || undefined,
        legal_issue: legalIssue.trim(),
        description: description.trim(),
        preferred_mode: preferredMode
      });
      setSuccessNotice(true);
      setModalOpen(false);
    } catch (err: any) {
      alert(err.response?.data?.detail || 'Failed to submit consultation request. Please ensure you are logged in as a Citizen.');
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div className="min-h-screen bg-slate-50 text-slate-900 font-sans">
      <Navbar />

      <main className="max-w-5xl mx-auto px-4 sm:px-6 lg:px-8 pt-24 pb-16">
        <Link
          href="/lawyers"
          className="inline-flex items-center gap-1.5 text-xs font-bold text-slate-500 hover:text-slate-800 transition-colors mb-6"
        >
          <ArrowLeft className="w-4 h-4" /> Back to Verified Directory
        </Link>

        {loading ? (
          <div className="py-24 text-center text-slate-400 text-sm">Loading advocate profile...</div>
        ) : errorMsg || !lawyer ? (
          <div className="bg-white border border-slate-200 rounded-3xl p-12 text-center text-slate-600 max-w-lg mx-auto space-y-4">
            <AlertCircle className="w-12 h-12 text-amber-500 mx-auto" />
            <h2 className="text-xl font-bold text-slate-900">Advocate Profile Unavailable</h2>
            <p className="text-xs text-slate-500 leading-relaxed">{errorMsg}</p>
            <Link
              href="/lawyers"
              className="inline-block px-4 py-2 bg-slate-100 hover:bg-slate-200 text-slate-800 font-bold text-xs rounded-xl"
            >
              Browse Verified Directory
            </Link>
          </div>
        ) : (
          <div className="space-y-6">
            {successNotice && (
              <div className="p-4 bg-emerald-50 border border-emerald-200 rounded-2xl flex items-start justify-between text-xs text-emerald-900">
                <div className="flex items-center gap-2.5">
                  <CheckCircle2 className="w-5 h-5 text-emerald-600 shrink-0" />
                  <div>
                    <p className="font-bold">Consultation Request Successfully Sent!</p>
                    <p className="text-emerald-700 mt-0.5">
                      Adv. {lawyer.full_name} has been notified. You can track this request under{' '}
                      <Link href="/dashboard/consultations" className="underline font-bold">My Consultations</Link>.
                    </p>
                  </div>
                </div>
                <button onClick={() => setSuccessNotice(false)} className="font-bold text-emerald-700">✕</button>
              </div>
            )}

            {/* Profile Header */}
            <div className="bg-white border border-slate-200 rounded-3xl p-6 sm:p-8 shadow-sm">
              <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-6">
                <div className="flex items-center gap-5">
                  <div className="w-20 h-20 rounded-2xl bg-slate-100 border border-slate-200 flex items-center justify-center font-bold text-slate-800 text-2xl overflow-hidden shrink-0">
                    {lawyer.photo_url ? (
                      <img src={lawyer.photo_url} alt={lawyer.full_name} className="w-full h-full object-cover" />
                    ) : (
                      lawyer.full_name.substring(0, 2).toUpperCase()
                    )}
                  </div>
                  <div>
                    <div className="flex items-center gap-2 flex-wrap">
                      <h1 className="text-2xl font-black text-slate-900">Adv. {lawyer.full_name}</h1>
                      <span className="inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full bg-emerald-50 text-emerald-700 text-xs font-bold border border-emerald-200">
                        <ShieldCheck className="w-3.5 h-3.5 text-emerald-600" /> BAR VERIFIED
                      </span>
                    </div>
                    <p className="text-xs text-slate-500 mt-1 flex items-center gap-1">
                      <MapPin className="w-3.5 h-3.5 text-slate-400" />
                      {lawyer.bar_council} ({lawyer.enrollment_state}) • {lawyer.years_of_practice} Years of Active Practice
                    </p>
                  </div>
                </div>

                <button
                  onClick={() => setModalOpen(true)}
                  className="w-full sm:w-auto px-6 py-3 bg-court-maroon hover:bg-rose-800 text-white font-bold text-xs uppercase tracking-wider rounded-xl transition-all shadow-md shadow-rose-950/20 cursor-pointer"
                >
                  Request Consultation
                </button>
              </div>
            </div>

            {/* Profile Details Grid */}
            <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
              {/* Left Column: Bio & Practice Details */}
              <div className="md:col-span-2 space-y-6">
                <div className="bg-white border border-slate-200 rounded-3xl p-6 sm:p-8 shadow-sm space-y-4">
                  <h2 className="text-base font-bold text-slate-900 uppercase tracking-wide">Professional Biography</h2>
                  <p className="text-xs text-slate-700 leading-relaxed whitespace-pre-line">
                    {lawyer.bio || 'Professional advocate practicing across civil, criminal, and constitutional matters.'}
                  </p>
                </div>

                <div className="bg-white border border-slate-200 rounded-3xl p-6 sm:p-8 shadow-sm space-y-4">
                  <h2 className="text-base font-bold text-slate-900 uppercase tracking-wide">Areas of Legal Specialization</h2>
                  <div className="flex flex-wrap gap-2">
                    {lawyer.specializations.map((spec, i) => (
                      <span key={i} className="px-3 py-1.5 bg-slate-100 text-slate-800 rounded-xl text-xs font-semibold">
                        {spec}
                      </span>
                    ))}
                  </div>
                </div>

                <div className="bg-white border border-slate-200 rounded-3xl p-6 sm:p-8 shadow-sm space-y-4">
                  <h2 className="text-base font-bold text-slate-900 uppercase tracking-wide">Practicing Courts & Tribunals</h2>
                  <div className="space-y-2">
                    {lawyer.courts.map((court, i) => (
                      <div key={i} className="flex items-center gap-2 text-xs text-slate-700 p-2.5 bg-slate-50 rounded-xl">
                        <Scale className="w-4 h-4 text-slate-500 shrink-0" />
                        <span>{court}</span>
                      </div>
                    ))}
                  </div>
                </div>
              </div>

              {/* Right Column: Preferences & Credentials */}
              <div className="space-y-6">
                <div className="bg-white border border-slate-200 rounded-3xl p-6 shadow-sm space-y-4">
                  <h3 className="text-xs font-bold text-slate-500 uppercase tracking-wider">Practice Information</h3>

                  <div className="space-y-3 text-xs">
                    <div>
                      <span className="text-slate-400 block mb-0.5">State Bar Council</span>
                      <span className="font-semibold text-slate-800">{lawyer.bar_council}</span>
                    </div>

                    <div>
                      <span className="text-slate-400 block mb-0.5">Jurisdiction</span>
                      <span className="font-semibold text-slate-800">{lawyer.enrollment_state}</span>
                    </div>

                    <div>
                      <span className="text-slate-400 block mb-0.5">Languages Spoken</span>
                      <span className="font-semibold text-slate-800">{lawyer.languages.join(', ')}</span>
                    </div>

                    <div>
                      <span className="text-slate-400 block mb-0.5">Consultation Modes</span>
                      <span className="font-semibold text-slate-800">
                        {lawyer.consultation_preferences?.modes?.join(', ') || 'Online / In-Person'}
                      </span>
                    </div>
                  </div>
                </div>

                <div className="bg-amber-50/80 border border-amber-200 rounded-3xl p-6 text-xs text-amber-900 space-y-2">
                  <p className="font-bold flex items-center gap-1.5">
                    <ShieldCheck className="w-4 h-4 text-amber-600 shrink-0" />
                    Verified Practitioner Notice
                  </p>
                  <p className="text-[11px] leading-relaxed text-amber-800">
                    NyayPath verifies Bar Council enrollment credentials upon onboarding. Private registration numbers are protected and never publicly broadcasted.
                  </p>
                </div>
              </div>
            </div>
          </div>
        )}
      </main>

      {/* Consultation Request Modal */}
      {modalOpen && lawyer && (
        <div className="fixed inset-0 z-50 bg-slate-900/40 backdrop-blur-sm flex items-center justify-center p-4">
          <form onSubmit={handleConsultationSubmit} className="bg-white rounded-3xl max-w-lg w-full p-6 sm:p-8 shadow-2xl border border-slate-200">
            <h3 className="text-lg font-bold text-slate-900 mb-1">Request Legal Consultation</h3>
            <p className="text-xs text-slate-500 mb-4">With Adv. {lawyer.full_name} ({lawyer.bar_council})</p>

            <div className="space-y-4 text-xs">
              <div>
                <label className="font-bold text-slate-700 block mb-1">Subject / Legal Matter</label>
                <input
                  type="text"
                  required
                  placeholder="e.g. Property boundary dispute, college disciplinary action, RTI refusal..."
                  value={legalIssue}
                  onChange={(e) => setLegalIssue(e.target.value)}
                  className="w-full p-2.5 border border-slate-200 rounded-xl focus:ring-2 focus:ring-rose-700"
                />
              </div>

              <div>
                <label className="font-bold text-slate-700 block mb-1">Detailed Grievance Summary</label>
                <textarea
                  required
                  rows={4}
                  placeholder="Summarize the core facts, dates, and what assistance you seek..."
                  value={description}
                  onChange={(e) => setDescription(e.target.value)}
                  className="w-full p-2.5 border border-slate-200 rounded-xl focus:ring-2 focus:ring-rose-700"
                />
              </div>

              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="font-bold text-slate-700 block mb-1">Consultation Mode</label>
                  <select
                    value={preferredMode}
                    onChange={(e) => setPreferredMode(e.target.value)}
                    className="w-full p-2.5 border border-slate-200 rounded-xl bg-white"
                  >
                    <option value="ONLINE">Online Virtual</option>
                    <option value="IN_PERSON">In-Person Chambers</option>
                    <option value="PHONE">Telephonic</option>
                  </select>
                </div>

                <div>
                  <label className="font-bold text-slate-700 block mb-1">Link NyayPath Case (Optional)</label>
                  <input
                    type="text"
                    placeholder="e.g. NP-2026-RTI-..."
                    value={caseId}
                    onChange={(e) => setCaseId(e.target.value)}
                    className="w-full p-2.5 border border-slate-200 rounded-xl font-mono uppercase"
                  />
                </div>
              </div>

              <p className="text-[11px] text-slate-400 italic">
                * Case documents are not automatically shared. You may grant or revoke document access explicitly after consultation acceptance.
              </p>
            </div>

            <div className="mt-6 flex justify-end gap-2.5">
              <button
                type="button"
                onClick={() => setModalOpen(false)}
                className="px-4 py-2 bg-slate-100 hover:bg-slate-200 text-slate-700 font-bold text-xs rounded-xl cursor-pointer"
              >
                Cancel
              </button>
              <button
                type="submit"
                disabled={submitting}
                className="px-5 py-2 bg-court-maroon hover:bg-rose-800 text-white font-bold text-xs rounded-xl disabled:opacity-50 cursor-pointer flex items-center gap-1.5 shadow-sm"
              >
                <Send className="w-3.5 h-3.5" />
                {submitting ? 'Submitting...' : 'Submit Request'}
              </button>
            </div>
          </form>
        </div>
      )}
    </div>
  );
}
