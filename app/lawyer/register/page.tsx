'use client';

import React, { useState } from 'react';
import Link from 'next/link';
import { useRouter } from 'next/navigation';
import {
  Scale,
  ShieldCheck,
  CheckCircle2,
  AlertCircle,
  FileText,
  User,
  Building2,
  Clock,
  ArrowRight,
  Briefcase,
  Globe,
  Award,
  BookOpen
} from 'lucide-react';
import { registerLawyer } from '@/lib/api';

const AVAILABLE_SPECIALIZATIONS = [
  'Criminal Law',
  'Constitutional Law',
  'Civil Litigation',
  'Corporate Law',
  'Cyber Law',
  'Intellectual Property',
  'Family & Matrimonial',
  'Education & Student Rights',
  'Labor & Employment',
  'Consumer Protection',
  'Taxation Law',
  'Human Rights'
];

const AVAILABLE_COURTS = [
  'Supreme Court of India',
  'Delhi High Court',
  'Bombay High Court',
  'Allahabad High Court',
  'Calcutta High Court',
  'Madras High Court',
  'Karnataka High Court',
  'District & Sessions Courts',
  'National Company Law Tribunal (NCLT)',
  'Central Administrative Tribunal (CAT)'
];

const AVAILABLE_LANGUAGES = [
  'English',
  'Hindi',
  'Bengali',
  'Marathi',
  'Telugu',
  'Tamil',
  'Kannada',
  'Gujarati',
  'Malayalam',
  'Punjabi',
  'Urdu'
];

const INDIAN_STATES = [
  'Andhra Pradesh', 'Arunachal Pradesh', 'Assam', 'Bihar', 'Chhattisgarh',
  'Goa', 'Gujarat', 'Haryana', 'Himachal Pradesh', 'Jharkhand', 'Karnataka',
  'Kerala', 'Madhya Pradesh', 'Maharashtra', 'Manipur', 'Meghalaya', 'Mizoram',
  'Nagaland', 'Odisha', 'Punjab', 'Rajasthan', 'Sikkim', 'Tamil Nadu',
  'Telangana', 'Tripura', 'Uttar Pradesh', 'Uttarakhand', 'West Bengal',
  'Delhi (NCT)', 'Jammu & Kashmir', 'Ladakh', 'Chandigarh'
];

export default function LawyerRegisterPage() {
  const router = useRouter();
  const [formData, setFormData] = useState({
    fullName: '',
    phone: '',
    barCouncil: 'Bar Council of Delhi',
    enrollmentState: 'Delhi (NCT)',
    enrollmentNumber: '',
    yearsOfPractice: 5,
    bio: '',
    photoUrl: ''
  });

  const [selectedSpecializations, setSelectedSpecializations] = useState<string[]>([
    'Constitutional Law',
    'Education & Student Rights'
  ]);
  const [selectedCourts, setSelectedCourts] = useState<string[]>([
    'Supreme Court of India',
    'Delhi High Court'
  ]);
  const [selectedLanguages, setSelectedLanguages] = useState<string[]>([
    'English',
    'Hindi'
  ]);

  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [successResult, setSuccessResult] = useState<any | null>(null);

  const toggleItem = (list: string[], setList: React.Dispatch<React.SetStateAction<string[]>>, item: string) => {
    if (list.includes(item)) {
      setList(list.filter((x) => x !== item));
    } else {
      setList([...list, item]);
    }
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);

    if (!formData.fullName.trim()) {
      setError('Full legal name is required.');
      return;
    }
    if (!formData.barCouncil.trim()) {
      setError('Bar Council affiliation is required.');
      return;
    }
    if (!formData.enrollmentNumber.trim()) {
      setError('Bar Council Enrollment Number is required (e.g. D/1234/2018).');
      return;
    }
    if (selectedSpecializations.length === 0) {
      setError('Please select at least one area of legal specialization.');
      return;
    }

    setLoading(true);
    try {
      const res = await registerLawyer({
        full_name: formData.fullName.trim(),
        phone: formData.phone.trim() || undefined,
        bar_council: formData.barCouncil.trim(),
        enrollment_state: formData.enrollmentState,
        enrollment_number: formData.enrollmentNumber.trim(),
        years_of_practice: Number(formData.yearsOfPractice) || 0,
        specializations: selectedSpecializations,
        courts: selectedCourts,
        languages: selectedLanguages,
        bio: formData.bio.trim() || undefined,
        photo_url: formData.photoUrl.trim() || undefined,
        consultation_preferences: {
          modes: ['ONLINE', 'IN_PERSON'],
          languages: selectedLanguages
        }
      });
      setSuccessResult(res);
    } catch (err: any) {
      setError(
        err?.response?.data?.detail ||
        err?.message ||
        'Registration failed. Please ensure you are logged in and your enrollment details are unique.'
      );
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="min-h-screen bg-slate-50 pt-24 pb-16 font-sans">
      <div className="max-w-4xl mx-auto px-4 sm:px-6">
        {/* Breadcrumb & Navigation */}
        <div className="mb-6 flex items-center justify-between text-xs text-slate-500">
          <div className="flex items-center gap-2">
            <Link href="/" className="hover:text-slate-800">Home</Link>
            <span>/</span>
            <Link href="/lawyers" className="hover:text-slate-800">Advocates</Link>
            <span>/</span>
            <span className="text-slate-700 font-semibold">Advocate Onboarding</span>
          </div>
          <Link
            href="/lawyer/dashboard"
            className="text-court-maroon hover:underline font-semibold flex items-center gap-1"
          >
            Go to Lawyer Desk <ArrowRight size={13} />
          </Link>
        </div>

        {/* Success Confirmation State */}
        {successResult ? (
          <div className="bg-white rounded-2xl shadow-xl border border-slate-200/80 p-8 text-center animate-in fade-in">
            <div className="w-16 h-16 bg-amber-50 rounded-2xl flex items-center justify-center mx-auto mb-5 border border-amber-200">
              <ShieldCheck className="w-8 h-8 text-amber-600" />
            </div>
            <span className="inline-flex items-center px-3 py-1 rounded-full text-xs font-bold uppercase tracking-wider bg-amber-100 text-amber-800 border border-amber-200 mb-3">
              Status: PENDING BAR VERIFICATION
            </span>
            <h2 className="text-2xl font-serif font-bold text-slate-900 mb-2">
              Registration Successfully Submitted
            </h2>
            <p className="text-sm text-slate-600 max-w-xl mx-auto mb-6 leading-relaxed">
              Advocate <strong className="text-slate-800">{successResult.profile?.full_name || formData.fullName}</strong>,
              your enrollment details (<span className="font-mono text-slate-700 font-semibold">{formData.enrollmentNumber}</span>) have been registered in NyayPath.
            </p>

            <div className="bg-slate-50 border border-slate-200 rounded-xl p-5 max-w-lg mx-auto text-left mb-6 space-y-2 text-xs text-slate-600">
              <div className="flex items-center gap-2 font-bold text-slate-800">
                <Clock className="w-4 h-4 text-amber-600" />
                <span>Next Verification Steps (24 - 48 Hours)</span>
              </div>
              <p>
                • Your Bar Council state roster credentials are currently undergoing statutory verification.
              </p>
              <p>
                • While pending, your profile remains hidden from the public advocate directory.
              </p>
              <p>
                • You can explore and configure your lawyer workspace, but cannot accept citizen consultation requests until verified.
              </p>
            </div>

            <div className="flex flex-col sm:flex-row gap-3 justify-center">
              <button
                onClick={() => router.push('/lawyer/dashboard')}
                className="px-6 py-2.5 bg-court-maroon hover:bg-rose-700 text-white rounded-xl text-xs font-bold uppercase tracking-wider transition-all shadow-md"
              >
                Access Lawyer Workspace
              </button>
              <button
                onClick={() => router.push('/lawyers')}
                className="px-6 py-2.5 bg-slate-100 hover:bg-slate-200 text-slate-700 rounded-xl text-xs font-bold uppercase tracking-wider transition-all"
              >
                View Public Directory
              </button>
            </div>
          </div>
        ) : (
          /* Registration Form */
          <div className="bg-white rounded-2xl shadow-xl border border-slate-200/80 overflow-hidden">
            {/* Header Banner */}
            <div className="bg-gradient-to-r from-slate-950 via-slate-900 to-court-maroon text-white p-6 sm:p-8">
              <div className="flex items-center gap-3 mb-2">
                <Scale className="w-8 h-8 text-amber-400" />
                <span className="text-xs font-bold uppercase tracking-widest text-amber-300">
                  Advocate Onboarding & Bar Verification
                </span>
              </div>
              <h1 className="text-2xl sm:text-3xl font-serif font-bold">
                Join the NyayPath Legal Network
              </h1>
              <p className="text-sm text-slate-300 mt-2 max-w-2xl leading-relaxed">
                Connect with citizens seeking justice, manage privileged case consultations, and provide legal representation under Bar Council standards.
              </p>
            </div>

            <form onSubmit={handleSubmit} className="p-6 sm:p-8 space-y-8">
              {error && (
                <div className="p-4 bg-rose-50 border border-rose-200 rounded-xl flex items-start gap-3 text-xs text-rose-800">
                  <AlertCircle className="w-5 h-5 text-rose-600 shrink-0 mt-0.5" />
                  <div className="flex-1">
                    <p className="font-bold">Registration Error</p>
                    <p className="mt-0.5">{error}</p>
                  </div>
                </div>
              )}

              {/* Section 1: Professional Identity */}
              <div>
                <h3 className="text-sm font-bold uppercase tracking-wider text-slate-800 flex items-center gap-2 mb-4 pb-2 border-b border-slate-100">
                  <User className="w-4 h-4 text-court-maroon" />
                  1. Advocate Identity & Credentials
                </h3>
                <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                  <div>
                    <label className="block text-xs font-semibold text-slate-700 mb-1">
                      Full Legal Name <span className="text-rose-600">*</span>
                    </label>
                    <input
                      type="text"
                      required
                      placeholder="Adv. Rajesh Kumar"
                      value={formData.fullName}
                      onChange={(e) => setFormData({ ...formData, fullName: e.target.value })}
                      className="w-full px-3.5 py-2.5 text-xs border border-slate-300 rounded-xl focus:ring-2 focus:ring-court-maroon/20 focus:border-court-maroon outline-none"
                    />
                  </div>

                  <div>
                    <label className="block text-xs font-semibold text-slate-700 mb-1">
                      Contact Phone (Confidential)
                    </label>
                    <input
                      type="tel"
                      placeholder="+91 98765 43210"
                      value={formData.phone}
                      onChange={(e) => setFormData({ ...formData, phone: e.target.value })}
                      className="w-full px-3.5 py-2.5 text-xs border border-slate-300 rounded-xl focus:ring-2 focus:ring-court-maroon/20 focus:border-court-maroon outline-none"
                    />
                  </div>

                  <div>
                    <label className="block text-xs font-semibold text-slate-700 mb-1">
                      Bar Council Affiliation <span className="text-rose-600">*</span>
                    </label>
                    <input
                      type="text"
                      required
                      placeholder="e.g. Bar Council of Delhi"
                      value={formData.barCouncil}
                      onChange={(e) => setFormData({ ...formData, barCouncil: e.target.value })}
                      className="w-full px-3.5 py-2.5 text-xs border border-slate-300 rounded-xl focus:ring-2 focus:ring-court-maroon/20 focus:border-court-maroon outline-none"
                    />
                  </div>

                  <div>
                    <label className="block text-xs font-semibold text-slate-700 mb-1">
                      Enrollment State <span className="text-rose-600">*</span>
                    </label>
                    <select
                      value={formData.enrollmentState}
                      onChange={(e) => setFormData({ ...formData, enrollmentState: e.target.value })}
                      className="w-full px-3.5 py-2.5 text-xs border border-slate-300 rounded-xl focus:ring-2 focus:ring-court-maroon/20 focus:border-court-maroon outline-none bg-white"
                    >
                      {INDIAN_STATES.map((st) => (
                        <option key={st} value={st}>{st}</option>
                      ))}
                    </select>
                  </div>

                  <div>
                    <label className="block text-xs font-semibold text-slate-700 mb-1">
                      Bar Council Enrollment Number <span className="text-rose-600">*</span>
                    </label>
                    <input
                      type="text"
                      required
                      placeholder="e.g. D/1234/2018"
                      value={formData.enrollmentNumber}
                      onChange={(e) => setFormData({ ...formData, enrollmentNumber: e.target.value })}
                      className="w-full px-3.5 py-2.5 text-xs font-mono border border-slate-300 rounded-xl focus:ring-2 focus:ring-court-maroon/20 focus:border-court-maroon outline-none"
                    />
                    <p className="text-[10px] text-slate-400 mt-1">
                      Strictly masked from public visitors; verified against Bar Council state registers.
                    </p>
                  </div>

                  <div>
                    <label className="block text-xs font-semibold text-slate-700 mb-1">
                      Years of Active Practice
                    </label>
                    <input
                      type="number"
                      min="0"
                      max="60"
                      value={formData.yearsOfPractice}
                      onChange={(e) => setFormData({ ...formData, yearsOfPractice: parseInt(e.target.value) || 0 })}
                      className="w-full px-3.5 py-2.5 text-xs border border-slate-300 rounded-xl focus:ring-2 focus:ring-court-maroon/20 focus:border-court-maroon outline-none"
                    />
                  </div>
                </div>
              </div>

              {/* Section 2: Specializations */}
              <div>
                <h3 className="text-sm font-bold uppercase tracking-wider text-slate-800 flex items-center gap-2 mb-2 pb-2 border-b border-slate-100">
                  <Briefcase className="w-4 h-4 text-court-maroon" />
                  2. Practice Areas & Specializations <span className="text-rose-600">*</span>
                </h3>
                <p className="text-xs text-slate-500 mb-3">Select the legal domains you handle:</p>
                <div className="flex flex-wrap gap-2">
                  {AVAILABLE_SPECIALIZATIONS.map((spec) => {
                    const selected = selectedSpecializations.includes(spec);
                    return (
                      <button
                        type="button"
                        key={spec}
                        onClick={() => toggleItem(selectedSpecializations, setSelectedSpecializations, spec)}
                        className={`px-3 py-1.5 rounded-lg text-xs font-medium transition-all ${
                          selected
                            ? 'bg-court-maroon text-white shadow-sm'
                            : 'bg-slate-100 text-slate-700 hover:bg-slate-200'
                        }`}
                      >
                        {selected && '✓ '} {spec}
                      </button>
                    );
                  })}
                </div>
              </div>

              {/* Section 3: Courts & Jurisdictions */}
              <div>
                <h3 className="text-sm font-bold uppercase tracking-wider text-slate-800 flex items-center gap-2 mb-2 pb-2 border-b border-slate-100">
                  <Building2 className="w-4 h-4 text-court-maroon" />
                  3. Courts & Tribunals
                </h3>
                <p className="text-xs text-slate-500 mb-3">Select forums where you actively practice:</p>
                <div className="flex flex-wrap gap-2">
                  {AVAILABLE_COURTS.map((court) => {
                    const selected = selectedCourts.includes(court);
                    return (
                      <button
                        type="button"
                        key={court}
                        onClick={() => toggleItem(selectedCourts, setSelectedCourts, court)}
                        className={`px-3 py-1.5 rounded-lg text-xs font-medium transition-all ${
                          selected
                            ? 'bg-slate-800 text-white shadow-sm'
                            : 'bg-slate-100 text-slate-700 hover:bg-slate-200'
                        }`}
                      >
                        {selected && '✓ '} {court}
                      </button>
                    );
                  })}
                </div>
              </div>

              {/* Section 4: Languages */}
              <div>
                <h3 className="text-sm font-bold uppercase tracking-wider text-slate-800 flex items-center gap-2 mb-2 pb-2 border-b border-slate-100">
                  <Globe className="w-4 h-4 text-court-maroon" />
                  4. Working Languages
                </h3>
                <div className="flex flex-wrap gap-2">
                  {AVAILABLE_LANGUAGES.map((lang) => {
                    const selected = selectedLanguages.includes(lang);
                    return (
                      <button
                        type="button"
                        key={lang}
                        onClick={() => toggleItem(selectedLanguages, setSelectedLanguages, lang)}
                        className={`px-3 py-1.5 rounded-lg text-xs font-medium transition-all ${
                          selected
                            ? 'bg-indigo-700 text-white shadow-sm'
                            : 'bg-slate-100 text-slate-700 hover:bg-slate-200'
                        }`}
                      >
                        {selected && '✓ '} {lang}
                      </button>
                    );
                  })}
                </div>
              </div>

              {/* Section 5: Professional Overview & Photo */}
              <div>
                <h3 className="text-sm font-bold uppercase tracking-wider text-slate-800 flex items-center gap-2 mb-4 pb-2 border-b border-slate-100">
                  <BookOpen className="w-4 h-4 text-court-maroon" />
                  5. Professional Bio & Public Details
                </h3>
                <div className="space-y-4">
                  <div>
                    <label className="block text-xs font-semibold text-slate-700 mb-1">
                      Professional Overview & Background
                    </label>
                    <textarea
                      rows={4}
                      placeholder="Briefly describe your legal career, key areas of advocacy, advisory focus, and client representation ethos..."
                      value={formData.bio}
                      onChange={(e) => setFormData({ ...formData, bio: e.target.value })}
                      className="w-full px-3.5 py-2.5 text-xs border border-slate-300 rounded-xl focus:ring-2 focus:ring-court-maroon/20 focus:border-court-maroon outline-none resize-none"
                    />
                  </div>

                  <div>
                    <label className="block text-xs font-semibold text-slate-700 mb-1">
                      Profile Photo URL (Optional)
                    </label>
                    <input
                      type="url"
                      placeholder="https://example.com/photo.jpg"
                      value={formData.photoUrl}
                      onChange={(e) => setFormData({ ...formData, photoUrl: e.target.value })}
                      className="w-full px-3.5 py-2.5 text-xs border border-slate-300 rounded-xl focus:ring-2 focus:ring-court-maroon/20 focus:border-court-maroon outline-none"
                    />
                  </div>
                </div>
              </div>

              {/* Verification Undertaking */}
              <div className="p-4 bg-slate-50 border border-slate-200 rounded-xl text-xs text-slate-600 space-y-2">
                <div className="flex items-center gap-2 font-bold text-slate-800">
                  <ShieldCheck className="w-4 h-4 text-court-maroon" />
                  <span>Advocate Statutory Undertaking</span>
                </div>
                <p>
                  I declare that I am an Advocate duly enrolled with the State Bar Council under the Advocates Act, 1961, and eligible to practice law in India. I understand that falsification of enrollment details leads to immediate disqualification and reporting to the appropriate Bar Council disciplinary committee.
                </p>
              </div>

              {/* Submit CTA */}
              <div className="flex items-center justify-end gap-3 pt-4 border-t border-slate-100">
                <Link
                  href="/lawyers"
                  className="px-5 py-2.5 text-xs font-bold text-slate-600 hover:text-slate-900 transition-colors"
                >
                  Cancel
                </Link>
                <button
                  type="submit"
                  disabled={loading}
                  className="px-6 py-2.5 bg-court-maroon hover:bg-rose-700 text-white rounded-xl text-xs font-bold uppercase tracking-wider transition-all shadow-md disabled:opacity-50 flex items-center gap-2 cursor-pointer"
                >
                  {loading ? (
                    <>
                      <span className="w-3.5 h-3.5 border-2 border-white/30 border-t-white rounded-full animate-spin" />
                      Submitting for Verification...
                    </>
                  ) : (
                    <>
                      Submit Advocate Registration
                      <ArrowRight size={14} />
                    </>
                  )}
                </button>
              </div>
            </form>
          </div>
        )}
      </div>
    </div>
  );
}
