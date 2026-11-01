'use client';

import React, { useState, useEffect, Suspense } from 'react';
import Link from 'next/link';
import { useRouter, useSearchParams } from 'next/navigation';
import {
  Scale,
  Search,
  Filter,
  ShieldCheck,
  CheckCircle2,
  Calendar,
  Building2,
  Globe,
  Briefcase,
  User,
  ArrowRight,
  ExternalLink,
  MessageSquare,
  AlertCircle,
  Clock,
  ChevronRight,
  X
} from 'lucide-react';
import {
  getVerifiedLawyers,
  requestConsultation,
  getCitizenCases,
  LawyerProfile
} from '@/lib/api';

const SPECIALIZATIONS = [
  'ALL',
  'Constitutional Law',
  'Education & Student Rights',
  'Criminal Law',
  'Civil Litigation',
  'Cyber Law',
  'Intellectual Property',
  'Family & Matrimonial',
  'Labor & Employment',
  'Consumer Protection'
];

const STATES = [
  'ALL',
  'Delhi (NCT)',
  'Maharashtra',
  'Karnataka',
  'Tamil Nadu',
  'Uttar Pradesh',
  'West Bengal',
  'Gujarat',
  'Rajasthan',
  'Telangana'
];

function FindLawyerContent() {
  const router = useRouter();
  const searchParams = useSearchParams();

  const preselectedLawyerId = searchParams.get('lawyer_id') || '';
  const preselectedCaseId = searchParams.get('case_id') || '';

  const [lawyers, setLawyers] = useState<LawyerProfile[]>([]);
  const [totalCount, setTotalCount] = useState(0);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  // Filters
  const [search, setSearch] = useState('');
  const [selectedSpec, setSelectedSpec] = useState('ALL');
  const [selectedState, setSelectedState] = useState('ALL');

  // Consultation Modal State
  const [selectedLawyer, setSelectedLawyer] = useState<LawyerProfile | null>(null);
  const [consultModalOpen, setConsultModalOpen] = useState(false);
  const [citizenCases, setCitizenCases] = useState<any[]>([]);
  const [loadingCases, setLoadingCases] = useState(false);

  // Form State
  const [legalIssue, setLegalIssue] = useState('');
  const [description, setDescription] = useState('');
  const [preferredMode, setPreferredMode] = useState<'ONLINE' | 'IN_PERSON' | 'PHONE'>('ONLINE');
  const [selectedCaseId, setSelectedCaseId] = useState(preselectedCaseId);
  const [submitting, setSubmitting] = useState(false);
  const [submitSuccess, setSubmitSuccess] = useState(false);
  const [submitError, setSubmitError] = useState<string | null>(null);

  const fetchLawyersList = async () => {
    setLoading(true);
    setError(null);
    try {
      const res = await getVerifiedLawyers({
        specialization: selectedSpec === 'ALL' ? undefined : selectedSpec,
        state: selectedState === 'ALL' ? undefined : selectedState,
        search: search.trim() || undefined,
        limit: 30
      });
      setLawyers(res.lawyers || []);
      setTotalCount(res.total || 0);

      // Auto-open modal if preselectedLawyerId
      if (preselectedLawyerId && res.lawyers) {
        const found = res.lawyers.find((l: LawyerProfile) => (l.user_id === preselectedLawyerId || l.lawyer_user_id === preselectedLawyerId || l.id === preselectedLawyerId));
        if (found) {
          handleOpenConsultModal(found);
        }
      }
    } catch (err: any) {
      setError(err?.response?.data?.detail || 'Failed to load advocate directory.');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchLawyersList();
  }, [selectedSpec, selectedState]);

  const handleOpenConsultModal = async (lawyer: LawyerProfile) => {
    setSelectedLawyer(lawyer);
    setConsultModalOpen(true);
    setSubmitSuccess(false);
    setSubmitError(null);

    // Fetch citizen's existing cases to link
    setLoadingCases(true);
    try {
      const casesRes = await getCitizenCases({ limit: 50 });
      setCitizenCases(casesRes.cases || []);
    } catch {
      // If unauthenticated or no cases, fail safely
      setCitizenCases([]);
    } finally {
      setLoadingCases(false);
    }
  };

  const handleConsultSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!selectedLawyer) return;

    if (!legalIssue.trim()) {
      setSubmitError('Please specify the primary legal issue.');
      return;
    }
    if (!description.trim()) {
      setSubmitError('Please provide a brief background description.');
      return;
    }

    setSubmitting(true);
    setSubmitError(null);

    try {
      await requestConsultation({
        lawyer_user_id: selectedLawyer.user_id || selectedLawyer.lawyer_user_id || selectedLawyer.id,
        case_id: selectedCaseId.trim() || undefined,
        legal_issue: legalIssue.trim(),
        description: description.trim(),
        preferred_mode: preferredMode
      });
      setSubmitSuccess(true);
    } catch (err: any) {
      setSubmitError(
        err?.response?.data?.detail ||
        'Failed to submit consultation request. Please ensure you are logged in as a citizen.'
      );
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div className="min-h-screen bg-slate-50 pt-24 pb-16 font-sans">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
        {/* Breadcrumb & Navigation */}
        <div className="mb-6 flex items-center justify-between text-xs text-slate-500">
          <div className="flex items-center gap-2">
            <Link href="/" className="hover:text-slate-800">Home</Link>
            <span>/</span>
            <Link href="/dashboard" className="hover:text-slate-800">Citizen Workspace</Link>
            <span>/</span>
            <span className="text-slate-700 font-semibold">Find Legal Counsel</span>
          </div>
          <Link
            href="/dashboard/consultations"
            className="text-court-maroon hover:underline font-semibold flex items-center gap-1"
          >
            My Consultations <ChevronRight size={13} />
          </Link>
        </div>

        {/* Hero Header */}
        <div className="bg-gradient-to-r from-slate-950 via-slate-900 to-court-maroon text-white rounded-3xl p-6 sm:p-10 shadow-xl mb-8 relative overflow-hidden">
          <div className="max-w-3xl relative z-10">
            <span className="inline-flex items-center gap-1.5 px-3 py-1 rounded-full text-xs font-bold uppercase tracking-wider bg-amber-400/20 text-amber-300 border border-amber-400/30 mb-3">
              <ShieldCheck className="w-3.5 h-3.5" />
              Verified Bar Council Advocates
            </span>
            <h1 className="text-2xl sm:text-4xl font-serif font-bold text-white tracking-tight">
              Connect with Qualified Legal Counsel
            </h1>
            <p className="text-xs sm:text-sm text-slate-300 mt-2 leading-relaxed">
              Find verified advocates across Indian jurisdictions. Request confidential legal advice, link your NyayPath case records, and share evidence securely under attorney-client privilege.
            </p>
          </div>
        </div>

        {/* Search & Filter Controls */}
        <div className="bg-white p-4 sm:p-6 rounded-2xl border border-slate-200/80 shadow-sm mb-8 space-y-4">
          <div className="flex flex-col md:flex-row gap-3">
            <div className="relative flex-1">
              <Search className="w-4 h-4 absolute left-3.5 top-1/2 -translate-y-1/2 text-slate-400" />
              <input
                type="text"
                placeholder="Search advocates by name, domain, court, or keywords..."
                value={search}
                onChange={(e) => setSearch(e.target.value)}
                onKeyDown={(e) => e.key === 'Enter' && fetchLawyersList()}
                className="w-full pl-10 pr-4 py-2.5 text-xs border border-slate-300 rounded-xl focus:ring-2 focus:ring-court-maroon/20 focus:border-court-maroon outline-none"
              />
            </div>
            <button
              onClick={fetchLawyersList}
              className="px-6 py-2.5 bg-court-maroon hover:bg-rose-700 text-white rounded-xl text-xs font-bold uppercase tracking-wider transition-all shadow-sm cursor-pointer"
            >
              Search
            </button>
          </div>

          <div className="flex flex-wrap items-center gap-4 pt-3 border-t border-slate-100 text-xs">
            <div className="flex items-center gap-2">
              <Filter className="w-3.5 h-3.5 text-slate-400" />
              <span className="font-semibold text-slate-700">Specialization:</span>
              <select
                value={selectedSpec}
                onChange={(e) => setSelectedSpec(e.target.value)}
                className="px-2.5 py-1.5 border border-slate-300 rounded-lg text-xs bg-white text-slate-800 outline-none"
              >
                {SPECIALIZATIONS.map((sp) => (
                  <option key={sp} value={sp}>{sp}</option>
                ))}
              </select>
            </div>

            <div className="flex items-center gap-2">
              <span className="font-semibold text-slate-700">State:</span>
              <select
                value={selectedState}
                onChange={(e) => setSelectedState(e.target.value)}
                className="px-2.5 py-1.5 border border-slate-300 rounded-lg text-xs bg-white text-slate-800 outline-none"
              >
                {STATES.map((st) => (
                  <option key={st} value={st}>{st}</option>
                ))}
              </select>
            </div>

            <span className="text-slate-400 ml-auto">
              Showing <strong>{lawyers.length}</strong> verified advocates
            </span>
          </div>
        </div>

        {/* Directory Grid */}
        {loading ? (
          <div className="py-20 text-center">
            <div className="w-8 h-8 border-3 border-court-maroon border-t-transparent rounded-full animate-spin mx-auto mb-3" />
            <p className="text-xs text-slate-500">Loading verified advocates...</p>
          </div>
        ) : error ? (
          <div className="p-6 bg-rose-50 border border-rose-200 rounded-2xl text-rose-800 text-xs">
            <p className="font-bold">Error loading directory</p>
            <p className="mt-1">{error}</p>
          </div>
        ) : lawyers.length === 0 ? (
          <div className="bg-white rounded-2xl border border-slate-200 p-12 text-center text-slate-500">
            <Scale className="w-10 h-10 text-slate-300 mx-auto mb-3" />
            <h3 className="font-serif font-bold text-base text-slate-700">No Advocates Found</h3>
            <p className="text-xs text-slate-400 mt-1 max-w-sm mx-auto">
              No verified advocates matched your filter criteria. Try choosing a different specialization or state.
            </p>
          </div>
        ) : (
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
            {lawyers.map((lawyer) => (
              <div
                key={lawyer.id}
                className="bg-white rounded-2xl border border-slate-200/80 hover:border-slate-300 shadow-sm hover:shadow-md transition-all p-6 flex flex-col justify-between"
              >
                <div>
                  <div className="flex items-start justify-between gap-3 mb-3">
                    <div className="flex items-center gap-3">
                      <div className="w-12 h-12 rounded-xl bg-slate-900 text-amber-300 flex items-center justify-center font-bold text-lg font-serif shrink-0 shadow-sm">
                        {lawyer.full_name ? lawyer.full_name.charAt(0) : 'A'}
                      </div>
                      <div>
                        <h3 className="font-serif font-bold text-slate-900 text-base leading-tight">
                          {lawyer.full_name}
                        </h3>
                        <p className="text-[11px] text-slate-500 mt-0.5">
                          {lawyer.bar_council || 'State Bar Council'} • {lawyer.enrollment_state}
                        </p>
                      </div>
                    </div>

                    <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-[10px] font-bold bg-emerald-50 text-emerald-700 border border-emerald-200 shrink-0">
                      <ShieldCheck className="w-3 h-3" />
                      VERIFIED
                    </span>
                  </div>

                  {lawyer.bio && (
                    <p className="text-xs text-slate-600 line-clamp-3 mb-4 leading-relaxed">
                      {lawyer.bio}
                    </p>
                  )}

                  {/* Specializations Chips */}
                  <div className="mb-4">
                    <span className="text-[10px] font-bold uppercase tracking-wider text-slate-400 block mb-1.5">
                      Practice Areas
                    </span>
                    <div className="flex flex-wrap gap-1.5">
                      {(lawyer.specializations || []).slice(0, 3).map((spec) => (
                        <span
                          key={spec}
                          className="px-2 py-0.5 rounded-md text-[10px] font-medium bg-slate-100 text-slate-700"
                        >
                          {spec}
                        </span>
                      ))}
                      {(lawyer.specializations || []).length > 3 && (
                        <span className="px-1.5 py-0.5 rounded-md text-[10px] text-slate-400">
                          +{(lawyer.specializations || []).length - 3} more
                        </span>
                      )}
                    </div>
                  </div>

                  {/* Meta details */}
                  <div className="pt-3 border-t border-slate-100 grid grid-cols-2 gap-2 text-[11px] text-slate-500 mb-4">
                    <div>
                      <span className="block text-[10px] text-slate-400">Experience</span>
                      <strong className="text-slate-800">{lawyer.years_of_practice || 0} Years</strong>
                    </div>
                    <div>
                      <span className="block text-[10px] text-slate-400">Primary Forum</span>
                      <strong className="text-slate-800 truncate block">
                        {(lawyer.courts && lawyer.courts[0]) || 'High Court'}
                      </strong>
                    </div>
                  </div>
                </div>

                <div className="flex items-center gap-2 pt-2">
                  <Link
                    href={`/lawyers/${encodeURIComponent(lawyer.id)}`}
                    className="flex-1 py-2 text-center bg-slate-100 hover:bg-slate-200 text-slate-700 rounded-xl text-xs font-bold transition-colors"
                  >
                    View Profile
                  </Link>
                  <button
                    onClick={() => handleOpenConsultModal(lawyer)}
                    className="flex-1 py-2 text-center bg-court-maroon hover:bg-rose-700 text-white rounded-xl text-xs font-bold uppercase tracking-wider transition-all shadow-sm cursor-pointer"
                  >
                    Consult
                  </button>
                </div>
              </div>
            ))}
          </div>
        )}

        {/* Consultation Request Modal */}
        {consultModalOpen && selectedLawyer && (
          <div className="fixed inset-0 z-50 bg-slate-900/60 backdrop-blur-sm flex items-center justify-center p-4">
            <div className="bg-white rounded-3xl max-w-xl w-full p-6 sm:p-8 shadow-2xl border border-slate-200 animate-in fade-in zoom-in-95 max-h-[90vh] overflow-y-auto">
              <div className="flex items-center justify-between pb-4 border-b border-slate-100 mb-6">
                <div className="flex items-center gap-2.5">
                  <Scale className="w-5 h-5 text-court-maroon" />
                  <div>
                    <h3 className="font-serif font-bold text-base sm:text-lg text-slate-900">
                      Request Legal Consultation
                    </h3>
                    <p className="text-xs text-slate-500">
                      With Adv. <strong className="text-slate-800">{selectedLawyer.full_name}</strong>
                    </p>
                  </div>
                </div>
                <button
                  onClick={() => setConsultModalOpen(false)}
                  className="p-1 rounded-lg text-slate-400 hover:text-slate-700 hover:bg-slate-100"
                >
                  <X size={18} />
                </button>
              </div>

              {submitSuccess ? (
                <div className="text-center py-8">
                  <div className="w-14 h-14 bg-emerald-50 rounded-2xl flex items-center justify-center mx-auto mb-4 border border-emerald-200">
                    <CheckCircle2 className="w-8 h-8 text-emerald-600" />
                  </div>
                  <h4 className="text-xl font-serif font-bold text-slate-900 mb-2">
                    Consultation Request Sent
                  </h4>
                  <p className="text-xs text-slate-600 max-w-md mx-auto mb-6 leading-relaxed">
                    Adv. {selectedLawyer.full_name} has received your inquiry. You will be notified in your Notification Center once the advocate reviews and responds.
                  </p>
                  <div className="flex flex-col sm:flex-row gap-2 justify-center">
                    <button
                      onClick={() => router.push('/dashboard/consultations')}
                      className="px-6 py-2.5 bg-court-maroon text-white rounded-xl text-xs font-bold uppercase tracking-wider hover:bg-rose-700 shadow-md"
                    >
                      Track My Consultations
                    </button>
                    <button
                      onClick={() => setConsultModalOpen(false)}
                      className="px-6 py-2.5 bg-slate-100 text-slate-700 rounded-xl text-xs font-bold uppercase tracking-wider hover:bg-slate-200"
                    >
                      Close
                    </button>
                  </div>
                </div>
              ) : (
                <form onSubmit={handleConsultSubmit} className="space-y-4">
                  {submitError && (
                    <div className="p-3 bg-rose-50 border border-rose-200 rounded-xl text-xs text-rose-800 flex items-start gap-2">
                      <AlertCircle className="w-4 h-4 text-rose-600 shrink-0 mt-0.5" />
                      <span>{submitError}</span>
                    </div>
                  )}

                  <div>
                    <label className="block text-xs font-semibold text-slate-700 mb-1">
                      Legal Issue Title <span className="text-rose-600">*</span>
                    </label>
                    <input
                      type="text"
                      required
                      placeholder="e.g., College Proctorial Board Appeal / Disciplinary Hearing"
                      value={legalIssue}
                      onChange={(e) => setLegalIssue(e.target.value)}
                      className="w-full px-3.5 py-2.5 text-xs border border-slate-300 rounded-xl focus:ring-2 focus:ring-court-maroon/20 focus:border-court-maroon outline-none"
                    />
                  </div>

                  <div>
                    <label className="block text-xs font-semibold text-slate-700 mb-1">
                      Detailed Narrative & Facts <span className="text-rose-600">*</span>
                    </label>
                    <textarea
                      rows={4}
                      required
                      placeholder="Provide a concise summary of the facts, timeline of events, and what legal assistance you are seeking..."
                      value={description}
                      onChange={(e) => setDescription(e.target.value)}
                      className="w-full px-3.5 py-2.5 text-xs border border-slate-300 rounded-xl focus:ring-2 focus:ring-court-maroon/20 focus:border-court-maroon outline-none resize-none"
                    />
                  </div>

                  <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                    <div>
                      <label className="block text-xs font-semibold text-slate-700 mb-1">
                        Preferred Consultation Mode
                      </label>
                      <select
                        value={preferredMode}
                        onChange={(e) => setPreferredMode(e.target.value as any)}
                        className="w-full px-3.5 py-2.5 text-xs border border-slate-300 rounded-xl focus:ring-2 focus:ring-court-maroon/20 focus:border-court-maroon outline-none bg-white"
                      >
                        <option value="ONLINE">Online Video / Chat</option>
                        <option value="IN_PERSON">In-Person Chamber Visit</option>
                        <option value="PHONE">Telephonic Consultation</option>
                      </select>
                    </div>

                    <div>
                      <label className="block text-xs font-semibold text-slate-700 mb-1">
                        Link Existing NyayPath Case (Optional)
                      </label>
                      <select
                        value={selectedCaseId}
                        onChange={(e) => setSelectedCaseId(e.target.value)}
                        className="w-full px-3.5 py-2.5 text-xs border border-slate-300 rounded-xl focus:ring-2 focus:ring-court-maroon/20 focus:border-court-maroon outline-none bg-white"
                      >
                        <option value="">-- No Case Linked --</option>
                        {citizenCases.map((c) => (
                          <option key={c.case_id} value={c.case_id}>
                            {c.case_id} — {c.title.substring(0, 30)}
                          </option>
                        ))}
                      </select>
                      <p className="text-[10px] text-slate-400 mt-1">
                        You can grant document access once the advocate accepts.
                      </p>
                    </div>
                  </div>

                  <div className="pt-4 border-t border-slate-100 flex items-center justify-end gap-2.5">
                    <button
                      type="button"
                      onClick={() => setConsultModalOpen(false)}
                      disabled={submitting}
                      className="px-4 py-2 text-xs font-bold text-slate-600 hover:text-slate-900 cursor-pointer"
                    >
                      Cancel
                    </button>
                    <button
                      type="submit"
                      disabled={submitting}
                      className="px-6 py-2.5 bg-court-maroon hover:bg-rose-700 text-white rounded-xl text-xs font-bold uppercase tracking-wider transition-all shadow-md disabled:opacity-50 flex items-center gap-2 cursor-pointer"
                    >
                      {submitting ? 'Sending Request...' : 'Send Consultation Request'}
                    </button>
                  </div>
                </form>
              )}
            </div>
          </div>
        )}
      </div>
    </div>
  );
}

export default function FindLawyerPage() {
  return (
    <Suspense fallback={<div className="min-h-screen pt-24 text-center text-xs text-slate-400">Loading Advocate Search...</div>}>
      <FindLawyerContent />
    </Suspense>
  );
}
