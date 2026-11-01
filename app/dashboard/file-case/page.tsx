'use client';

import React, { useState, useEffect } from 'react';
import Link from 'next/link';
import { useRouter } from 'next/navigation';
import {
  ArrowLeft,
  ArrowRight,
  Briefcase,
  Building,
  Calendar,
  CheckCircle2,
  AlertTriangle,
  FileText,
  FolderOpen,
  Info,
  Lock,
  PlusCircle,
  RefreshCw,
  Scale,
  ShieldCheck,
  Trash2,
  Upload,
  User,
  GraduationCap,
  Copy,
  Check,
  ExternalLink,
  ChevronRight
} from 'lucide-react';
import { fileCitizenCase, uploadCaseDocument, getCitizenDashboardStats, loginCitizen, CaseFilingPayload } from '@/lib/api';

const CASE_CATEGORIES = [
  {
    id: 'CAMPUS_GRIEVANCE',
    title: 'Campus Grievance',
    badge: 'Proctorial Cell',
    description: 'Academic discrepancies, hostel amenities, ragging prevention, and campus proctorial inquiries.',
    icon: GraduationCap,
    subcategories: ['Academic Dispute', 'Hostel Amenities', 'Anti-Ragging / Harassment', 'Administrative / Fee Dispute', 'General Campus Grievance']
  },
  {
    id: 'RTI',
    title: 'RTI Application',
    badge: 'Statutory Act, 2005',
    description: 'Information requests submitted to designated Public Information Officers (PIOs).',
    icon: FileText,
    subcategories: ['Public Works & Contracts', 'Educational Institutions', 'Municipal / Urban Local Body', 'Public Recruitment & Exams', 'General Information Request']
  },
  {
    id: 'FIRST_APPEAL',
    title: 'First Appeal',
    badge: 'Appellate Authority',
    description: 'Appeals against rejected RTI queries, deemed refusals, or delayed administrative responses.',
    icon: Scale,
    subcategories: ['RTI First Appeal (Sec 19(1))', 'Service Matter Appeal', 'Administrative Delay Appeal', 'Grievance Redressal Appeal']
  },
  {
    id: 'CONSUMER_COMPLAINT',
    title: 'Consumer Dispute',
    badge: 'Consumer Protection Act',
    description: 'Deficiency in services, unfair trade practices, e-commerce fraud, and defective products.',
    icon: Briefcase,
    subcategories: ['E-Commerce & Online Orders', 'Banking & Financial Services', 'Telecom & Internet Services', 'Healthcare & Medical Negligence', 'Travel & Hospitality Services']
  },
  {
    id: 'GENERAL_GRIEVANCE',
    title: 'General Civic Grievance',
    badge: 'Public Redressal',
    description: 'Public utility complaints, municipal sanitation, road infrastructure, and local civic issues.',
    icon: Building,
    subcategories: ['Municipal Infrastructure', 'Sanitation & Health', 'Electricity & Water Supply', 'Public Transport & Roads', 'General Public Administration']
  }
];

export default function FileCasePage() {
  const router = useRouter();

  // Wizard Step (1 to 6)
  const [currentStep, setCurrentStep] = useState<number>(1);

  // Authenticated User State
  const [userProfile, setUserProfile] = useState<{
    user_id: string;
    name: string;
    email: string;
    role: string;
    institution_id?: string;
  } | null>(null);
  const [loadingUser, setLoadingUser] = useState(true);
  const [authError, setAuthError] = useState<boolean>(false);
  const [demoLoginLoading, setDemoLoginLoading] = useState(false);

  // Form State
  const [category, setCategory] = useState<string>('CAMPUS_GRIEVANCE');
  const [subCategory, setSubCategory] = useState<string>('Academic Dispute');
  const [phone, setPhone] = useState<string>('');
  const [alternateEmail, setAlternateEmail] = useState<string>('');
  const [subject, setSubject] = useState<string>('');
  const [facts, setFacts] = useState<string>('');
  const [remedySought, setRemedySought] = useState<string>('');
  const [department, setDepartment] = useState<string>('');
  const [incidentDate, setIncidentDate] = useState<string>(() => {
    return new Date().toISOString().split('T')[0];
  });
  const [isConfidential, setIsConfidential] = useState<boolean>(false);

  // Documents
  const [documents, setDocuments] = useState<Array<{
    document_id?: string;
    file_name: string;
    storage_path: string;
    file_size_bytes?: number;
    mime_type?: string;
  }>>([]);
  const [uploadingDoc, setUploadingDoc] = useState(false);
  const [uploadError, setUploadError] = useState<string | null>(null);

  // Review & Affirmation
  const [declarationConfirmed, setDeclarationConfirmed] = useState<boolean>(false);
  const [submitting, setSubmitting] = useState(false);
  const [submissionError, setSubmissionError] = useState<string | null>(null);

  // Submission Result (Step 6)
  const [submissionResult, setSubmissionResult] = useState<{
    case_id: string;
    case_uuid?: string;
    verification_key: string;
    category: string;
    status: string;
    created_at: string;
  } | null>(null);

  const [copiedKey, setCopiedKey] = useState(false);
  const [copiedId, setCopiedId] = useState(false);

  // Check user session
  const verifySession = async () => {
    setLoadingUser(true);
    setAuthError(false);
    try {
      const res = await getCitizenDashboardStats();
      if (res?.user_profile) {
        setUserProfile(res.user_profile);
      }
    } catch (err: any) {
      if (err?.response?.status === 401 || err?.response?.status === 403) {
        setAuthError(true);
      }
    } finally {
      setLoadingUser(false);
    }
  };

  useEffect(() => {
    verifySession();
  }, []);

  // Update default subcategory when category changes
  const handleCategorySelect = (catId: string) => {
    setCategory(catId);
    const cat = CASE_CATEGORIES.find(c => c.id === catId);
    if (cat && cat.subcategories.length > 0) {
      setSubCategory(cat.subcategories[0]);
    }
  };

  // Demo Login Handler
  const handleDemoLogin = async (asStudent: boolean) => {
    setDemoLoginLoading(true);
    try {
      const email = asStudent ? 'student@nit.edu' : 'citizen@nyaypath.in';
      const res = await loginCitizen({ email });
      if (res?.token) {
        localStorage.setItem('auth_token', res.token);
        setAuthError(false);
        await verifySession();
      }
    } catch (err) {
      alert('Demo sign in failed. Please ensure local backend is reachable.');
    } finally {
      setDemoLoginLoading(false);
    }
  };

  // Document Upload Handler
  const handleFileUpload = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const files = e.target.files;
    if (!files || files.length === 0) return;

    const file = files[0];
    if (file.size > 10 * 1024 * 1024) {
      setUploadError('File exceeds maximum permissible limit of 10MB.');
      return;
    }

    const allowed = ['application/pdf', 'image/jpeg', 'image/png', 'image/webp'];
    if (!allowed.includes(file.type)) {
      setUploadError('Invalid file type. Allowed: PDF, JPEG, PNG, WebP.');
      return;
    }

    setUploadError(null);
    setUploadingDoc(true);

    try {
      const res = await uploadCaseDocument(file);
      if (res?.storage_path) {
        setDocuments(prev => [
          ...prev,
          {
            document_id: res.document_id,
            file_name: res.file_name,
            storage_path: res.storage_path,
            file_size_bytes: res.file_size_bytes,
            mime_type: res.mime_type
          }
        ]);
      }
    } catch (err: any) {
      setUploadError(err?.response?.data?.detail || 'Failed to upload document.');
    } finally {
      setUploadingDoc(false);
      // Reset input
      e.target.value = '';
    }
  };

  const handleRemoveDoc = (index: number) => {
    setDocuments(prev => prev.filter((_, idx) => idx !== index));
  };

  // Final Submission Handler
  const handleSubmitCase = async () => {
    if (!declarationConfirmed) {
      setSubmissionError('You must review and accept the statutory declaration before submitting.');
      return;
    }

    if (!subject.trim() || !facts.trim()) {
      setSubmissionError('Case subject and narrative facts are required.');
      return;
    }

    setSubmitting(true);
    setSubmissionError(null);

    const payload: CaseFilingPayload = {
      category,
      sub_category: subCategory,
      subject: subject.trim(),
      facts: facts.trim(),
      remedy_sought: remedySought.trim() || undefined,
      department: department.trim() || undefined,
      incident_date: incidentDate || undefined,
      is_confidential: isConfidential,
      supporting_documents: documents,
      declaration_confirmed: true
    };

    try {
      const res = await fileCitizenCase(payload);
      if (res?.case_id) {
        setSubmissionResult({
          case_id: res.case_id,
          case_uuid: res.case_uuid,
          verification_key: res.verification_key,
          category: res.category,
          status: res.status,
          created_at: res.created_at
        });
        setCurrentStep(6);
      } else {
        setSubmissionError('Case submission did not return a valid Case ID.');
      }
    } catch (err: any) {
      setSubmissionError(err?.response?.data?.detail || 'Case submission failed. Please try again.');
    } finally {
      setSubmitting(false);
    }
  };

  const copyToClipboard = (text: string, type: 'id' | 'key') => {
    navigator.clipboard.writeText(text);
    if (type === 'id') {
      setCopiedId(true);
      setTimeout(() => setCopiedId(false), 2000);
    } else {
      setCopiedKey(true);
      setTimeout(() => setCopiedKey(false), 2000);
    }
  };

  // Step Validation
  const canProceedFromStep = (step: number): boolean => {
    if (step === 1) return Boolean(category);
    if (step === 2) return Boolean(userProfile);
    if (step === 3) return subject.trim().length >= 3 && facts.trim().length >= 10;
    if (step === 4) return true; // Documents are optional
    if (step === 5) return declarationConfirmed && !submitting;
    return true;
  };

  const selectedCategoryObj = CASE_CATEGORIES.find(c => c.id === category);

  return (
    <div className="min-h-screen bg-slate-50 text-slate-800 pb-24">
      {/* Top Header */}
      <div className="bg-slate-900 border-b border-slate-800 text-white">
        <div className="max-w-6xl mx-auto px-4 sm:px-6 py-6">
          <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
            <div>
              <Link
                href="/dashboard"
                className="inline-flex items-center gap-1.5 text-xs text-slate-400 hover:text-white mb-2 transition-colors"
              >
                <ArrowLeft className="w-3.5 h-3.5" />
                <span>Return to Citizen Dashboard</span>
              </Link>
              <h1 className="text-xl sm:text-2xl font-bold flex items-center gap-2.5">
                <Scale className="w-6 h-6 text-court-maroon" />
                <span>Central Case Filing Wizard</span>
              </h1>
              <p className="text-xs text-slate-400 mt-1 max-w-2xl">
                Unified statutory intake portal across Institutional Proctorial Grievances, RTI Requests, Consumer Disputes, and Appellate Reviews.
              </p>
            </div>

            {userProfile && (
              <div className="px-4 py-2.5 rounded-2xl bg-slate-800/80 border border-slate-700/80 flex items-center gap-3 shrink-0">
                <div className="w-8 h-8 rounded-full bg-court-maroon/20 border border-court-maroon/40 flex items-center justify-center text-court-maroon text-xs font-bold">
                  {userProfile.name.charAt(0)}
                </div>
                <div>
                  <span className="text-xs font-bold text-white block">{userProfile.name}</span>
                  <span className="text-[11px] text-emerald-400 font-medium flex items-center gap-1">
                    <ShieldCheck className="w-3 h-3" />
                    Verified Identity
                  </span>
                </div>
              </div>
            )}
          </div>

          {/* 6-Step Indicator */}
          <div className="mt-8 pt-6 border-t border-slate-800 grid grid-cols-2 sm:grid-cols-6 gap-2 text-xs">
            {[
              { num: 1, label: 'Category' },
              { num: 2, label: 'Applicant' },
              { num: 3, label: 'Case Details' },
              { num: 4, label: 'Documents' },
              { num: 5, label: 'Affirmation' },
              { num: 6, label: 'Confirmation' }
            ].map(s => {
              const isActive = currentStep === s.num;
              const isPast = currentStep > s.num;
              return (
                <div
                  key={s.num}
                  className={`flex items-center gap-2 p-2 rounded-xl transition-all ${
                    isActive
                      ? 'bg-court-maroon text-white font-bold shadow-md'
                      : isPast
                      ? 'text-emerald-400 bg-emerald-950/20'
                      : 'text-slate-500 bg-slate-800/40'
                  }`}
                >
                  <div
                    className={`w-5 h-5 rounded-full flex items-center justify-center text-[10px] font-bold ${
                      isActive
                        ? 'bg-white text-slate-900'
                        : isPast
                        ? 'bg-emerald-500 text-white'
                        : 'bg-slate-700 text-slate-300'
                    }`}
                  >
                    {isPast ? <Check className="w-3 h-3" /> : s.num}
                  </div>
                  <span className="truncate">{s.label}</span>
                </div>
              );
            })}
          </div>
        </div>
      </div>

      <div className="max-w-4xl mx-auto px-4 sm:px-6 py-8">
        {/* Unauthenticated Alert */}
        {authError && (
          <div className="mb-8 p-6 rounded-3xl bg-amber-50 border border-amber-200 text-amber-900 shadow-sm space-y-4">
            <div className="flex items-start gap-3">
              <AlertTriangle className="w-5 h-5 text-amber-600 shrink-0 mt-0.5" />
              <div>
                <h3 className="font-bold text-sm">Authentication Required for Case Filing</h3>
                <p className="text-xs text-amber-700 mt-1 leading-relaxed">
                  Under statutory rules and institutional policies, legal filings require an authenticated account session to guarantee identity attribution and prevent fraudulent submissions.
                </p>
              </div>
            </div>

            <div className="flex flex-wrap items-center gap-3 pt-2">
              <button
                onClick={() => handleDemoLogin(true)}
                disabled={demoLoginLoading}
                className="px-4 py-2 rounded-xl bg-court-maroon text-white font-bold text-xs hover:bg-rose-900 transition-colors shadow-sm cursor-pointer disabled:opacity-50"
              >
                Sign in as Student (Aarav Sharma)
              </button>
              <button
                onClick={() => handleDemoLogin(false)}
                disabled={demoLoginLoading}
                className="px-4 py-2 rounded-xl bg-slate-900 text-white font-bold text-xs hover:bg-slate-800 transition-colors shadow-sm cursor-pointer disabled:opacity-50"
              >
                Sign in as Citizen (Priya Patel)
              </button>
            </div>
          </div>
        )}

        {/* =================================================================== */}
        {/* Step 1: Select Case Category */}
        {/* =================================================================== */}
        {currentStep === 1 && (
          <div className="space-y-6">
            <div className="p-6 rounded-3xl bg-white border border-slate-200 shadow-sm space-y-2">
              <h2 className="text-lg font-bold text-slate-900">Step 1: Select Filing Jurisdiction & Category</h2>
              <p className="text-xs text-slate-500 leading-relaxed">
                Choose the statutory forum or grievance category matching your legal issue. Your case will be routed to the designated institutional redressal cell or authority.
              </p>
            </div>

            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              {CASE_CATEGORIES.map(cat => {
                const IconComponent = cat.icon;
                const isSelected = category === cat.id;
                return (
                  <div
                    key={cat.id}
                    onClick={() => handleCategorySelect(cat.id)}
                    className={`p-5 rounded-3xl border transition-all cursor-pointer relative ${
                      isSelected
                        ? 'border-court-maroon bg-rose-50/20 shadow-md ring-2 ring-court-maroon/20'
                        : 'border-slate-200 bg-white hover:border-slate-300 hover:shadow-sm'
                    }`}
                  >
                    <div className="flex items-start justify-between gap-3 mb-3">
                      <div
                        className={`p-3 rounded-2xl ${
                          isSelected ? 'bg-court-maroon text-white' : 'bg-slate-100 text-slate-700'
                        }`}
                      >
                        <IconComponent className="w-5 h-5" />
                      </div>
                      <span className="text-[10px] uppercase font-bold tracking-wider px-2.5 py-1 rounded-full bg-slate-100 text-slate-600 border border-slate-200">
                        {cat.badge}
                      </span>
                    </div>

                    <h3 className="font-bold text-sm text-slate-900 mb-1">{cat.title}</h3>
                    <p className="text-xs text-slate-500 leading-relaxed">{cat.description}</p>

                    <div className="mt-4 pt-3 border-t border-slate-100 flex items-center justify-between text-xs">
                      <span className="text-slate-400 font-medium">Select to proceed</span>
                      <div
                        className={`w-5 h-5 rounded-full border flex items-center justify-center ${
                          isSelected ? 'border-court-maroon bg-court-maroon text-white' : 'border-slate-300'
                        }`}
                      >
                        {isSelected && <Check className="w-3 h-3" />}
                      </div>
                    </div>
                  </div>
                );
              })}
            </div>

            {/* Sub-Category Selection */}
            {selectedCategoryObj && (
              <div className="p-6 rounded-3xl bg-white border border-slate-200 shadow-sm space-y-4">
                <label className="block text-xs font-bold text-slate-700 uppercase tracking-wider">
                  Specific Matter / Sub-Category
                </label>
                <div className="grid grid-cols-1 sm:grid-cols-2 gap-2.5">
                  {selectedCategoryObj.subcategories.map(sub => (
                    <button
                      key={sub}
                      type="button"
                      onClick={() => setSubCategory(sub)}
                      className={`p-3 rounded-2xl text-xs font-medium text-left border transition-all cursor-pointer flex items-center justify-between ${
                        subCategory === sub
                          ? 'border-court-maroon bg-rose-50/50 text-court-maroon font-bold'
                          : 'border-slate-200 bg-slate-50/50 text-slate-700 hover:bg-slate-100'
                      }`}
                    >
                      <span>{sub}</span>
                      {subCategory === sub && <CheckCircle2 className="w-4 h-4 text-court-maroon shrink-0" />}
                    </button>
                  ))}
                </div>
              </div>
            )}
          </div>
        )}

        {/* =================================================================== */}
        {/* Step 2: Applicant Information */}
        {/* =================================================================== */}
        {currentStep === 2 && (
          <div className="space-y-6">
            <div className="p-6 rounded-3xl bg-white border border-slate-200 shadow-sm space-y-2">
              <h2 className="text-lg font-bold text-slate-900">Step 2: Applicant Information & Authentication</h2>
              <p className="text-xs text-slate-500 leading-relaxed">
                Cases are authoritatively linked to your verified account identity. This prevents identity forgery and guarantees that only you can manage your case.
              </p>
            </div>

            {userProfile ? (
              <div className="p-6 rounded-3xl bg-white border border-slate-200 shadow-sm space-y-6">
                <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                  <div className="p-4 rounded-2xl bg-slate-50 border border-slate-200">
                    <span className="text-[11px] font-bold text-slate-400 uppercase tracking-wider block mb-1">
                      Full Legal Name
                    </span>
                    <span className="text-sm font-bold text-slate-900">{userProfile.name}</span>
                    <span className="mt-1 block text-[10px] text-emerald-600 font-bold flex items-center gap-1">
                      <ShieldCheck className="w-3 h-3" /> Authoritative Identity
                    </span>
                  </div>

                  <div className="p-4 rounded-2xl bg-slate-50 border border-slate-200">
                    <span className="text-[11px] font-bold text-slate-400 uppercase tracking-wider block mb-1">
                      Registered Email Address
                    </span>
                    <span className="text-sm font-bold text-slate-900">{userProfile.email}</span>
                    <span className="mt-1 block text-[10px] text-slate-400">Notifications recipient</span>
                  </div>

                  <div className="p-4 rounded-2xl bg-slate-50 border border-slate-200">
                    <span className="text-[11px] font-bold text-slate-400 uppercase tracking-wider block mb-1">
                      Role & Designation
                    </span>
                    <span className="text-sm font-bold text-slate-900 uppercase">{userProfile.role}</span>
                    <span className="mt-1 block text-[10px] text-slate-400">
                      Institution: {userProfile.institution_id || 'National Jurisdiction'}
                    </span>
                  </div>

                  <div className="p-4 rounded-2xl bg-slate-50 border border-slate-200">
                    <span className="text-[11px] font-bold text-slate-400 uppercase tracking-wider block mb-1">
                      Server-Verified UID (auth.uid())
                    </span>
                    <code className="text-xs font-mono text-slate-700 block truncate">{userProfile.user_id}</code>
                    <span className="mt-1 block text-[10px] text-slate-400">Unforgeable cryptographic identity</span>
                  </div>
                </div>

                <div className="pt-4 border-t border-slate-100 space-y-4">
                  <h4 className="text-xs font-bold text-slate-800 uppercase tracking-wider">
                    Supplementary Contact Info (Optional)
                  </h4>
                  <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                    <div>
                      <label className="block text-xs font-medium text-slate-600 mb-1">
                        Mobile Phone / WhatsApp (For Hearing SMS)
                      </label>
                      <input
                        type="tel"
                        value={phone}
                        onChange={e => setPhone(e.target.value)}
                        placeholder="+91 98765 43210"
                        className="w-full px-4 py-2.5 rounded-xl border border-slate-200 bg-white text-xs text-slate-800 focus:outline-none focus:ring-2 focus:ring-court-maroon/20 focus:border-court-maroon"
                      />
                    </div>
                    <div>
                      <label className="block text-xs font-medium text-slate-600 mb-1">
                        Alternate Email Address
                      </label>
                      <input
                        type="email"
                        value={alternateEmail}
                        onChange={e => setAlternateEmail(e.target.value)}
                        placeholder="alternate@email.com"
                        className="w-full px-4 py-2.5 rounded-xl border border-slate-200 bg-white text-xs text-slate-800 focus:outline-none focus:ring-2 focus:ring-court-maroon/20 focus:border-court-maroon"
                      />
                    </div>
                  </div>
                </div>
              </div>
            ) : (
              <div className="p-8 rounded-3xl bg-white border border-slate-200 text-center space-y-3">
                <RefreshCw className="w-6 h-6 animate-spin text-court-maroon mx-auto" />
                <p className="text-xs text-slate-500">Checking authenticated account session...</p>
              </div>
            )}
          </div>
        )}

        {/* =================================================================== */}
        {/* Step 3: Case Information */}
        {/* =================================================================== */}
        {currentStep === 3 && (
          <div className="space-y-6">
            <div className="p-6 rounded-3xl bg-white border border-slate-200 shadow-sm space-y-2">
              <h2 className="text-lg font-bold text-slate-900">Step 3: Narrative Facts & Relief Sought</h2>
              <p className="text-xs text-slate-500 leading-relaxed">
                Provide clear, chronological particulars of the grievance or application. Factual clarity expedites official inquiry.
              </p>
            </div>

            <div className="p-6 rounded-3xl bg-white border border-slate-200 shadow-sm space-y-5">
              {/* Subject / Title */}
              <div>
                <label className="block text-xs font-bold text-slate-700 uppercase tracking-wider mb-1.5">
                  Case Subject / Title <span className="text-rose-600">*</span>
                </label>
                <input
                  type="text"
                  value={subject}
                  onChange={e => setSubject(e.target.value)}
                  placeholder="e.g. Unfair withholding of semester transcript despite no dues clearance"
                  className="w-full px-4 py-2.5 rounded-xl border border-slate-200 bg-white text-xs text-slate-800 focus:outline-none focus:ring-2 focus:ring-court-maroon/20 focus:border-court-maroon font-medium"
                />
                <span className="text-[11px] text-slate-400 mt-1 block">
                  A concise, informative one-line summary of your matter.
                </span>
              </div>

              {/* Department / Respondent */}
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                <div>
                  <label className="block text-xs font-bold text-slate-700 uppercase tracking-wider mb-1.5">
                    Target Department / Public Authority
                  </label>
                  <input
                    type="text"
                    value={department}
                    onChange={e => setDepartment(e.target.value)}
                    placeholder="e.g. Academic Examination Section / Municipal Ward Office"
                    className="w-full px-4 py-2.5 rounded-xl border border-slate-200 bg-white text-xs text-slate-800 focus:outline-none focus:ring-2 focus:ring-court-maroon/20 focus:border-court-maroon"
                  />
                </div>

                <div>
                  <label className="block text-xs font-bold text-slate-700 uppercase tracking-wider mb-1.5">
                    Date of Occurrence / Incident
                  </label>
                  <input
                    type="date"
                    value={incidentDate}
                    onChange={e => setIncidentDate(e.target.value)}
                    className="w-full px-4 py-2.5 rounded-xl border border-slate-200 bg-white text-xs text-slate-800 focus:outline-none focus:ring-2 focus:ring-court-maroon/20 focus:border-court-maroon"
                  />
                </div>
              </div>

              {/* Factual Narrative */}
              <div>
                <label className="block text-xs font-bold text-slate-700 uppercase tracking-wider mb-1.5">
                  Chronological Statement of Facts <span className="text-rose-600">*</span>
                </label>
                <textarea
                  rows={6}
                  value={facts}
                  onChange={e => setFacts(e.target.value)}
                  placeholder="Detail the factual background, dates of communication, prior representations made, and reasons why the grievance remains unresolved..."
                  className="w-full px-4 py-3 rounded-2xl border border-slate-200 bg-white text-xs text-slate-800 focus:outline-none focus:ring-2 focus:ring-court-maroon/20 focus:border-court-maroon leading-relaxed"
                />
                <div className="flex items-center justify-between mt-1 text-[11px] text-slate-400">
                  <span>Minimum 10 characters required.</span>
                  <span>{facts.length} characters</span>
                </div>
              </div>

              {/* Specific Remedy Sought */}
              <div>
                <label className="block text-xs font-bold text-slate-700 uppercase tracking-wider mb-1.5">
                  Specific Relief / Remedy Sought
                </label>
                <textarea
                  rows={3}
                  value={remedySought}
                  onChange={e => setRemedySought(e.target.value)}
                  placeholder="Specify the exact redress requested (e.g. issuance of official grade certificate, refund of erroneous penalty fee, inspection of records)..."
                  className="w-full px-4 py-2.5 rounded-xl border border-slate-200 bg-white text-xs text-slate-800 focus:outline-none focus:ring-2 focus:ring-court-maroon/20 focus:border-court-maroon leading-relaxed"
                />
              </div>

              {/* Confidentiality Option */}
              <div className="pt-3 border-t border-slate-100">
                <label className="p-4 rounded-2xl border border-slate-200 bg-slate-50/50 hover:bg-slate-50 transition-colors flex items-start gap-3 cursor-pointer">
                  <input
                    type="checkbox"
                    checked={isConfidential}
                    onChange={e => setIsConfidential(e.target.checked)}
                    className="mt-1 w-4 h-4 rounded text-court-maroon focus:ring-court-maroon"
                  />
                  <div>
                    <span className="text-xs font-bold text-slate-800 block flex items-center gap-1.5">
                      <Lock className="w-3.5 h-3.5 text-amber-600" />
                      Mark as Restricted Confidential Case
                    </span>
                    <span className="text-[11px] text-slate-500 leading-relaxed block mt-0.5">
                      Restricts case documents and details strictly to designated proctorial / inquiry officers. Prevents public directory listing or institutional disclosure.
                    </span>
                  </div>
                </label>
              </div>
            </div>
          </div>
        )}

        {/* =================================================================== */}
        {/* Step 4: Supporting Documents */}
        {/* =================================================================== */}
        {currentStep === 4 && (
          <div className="space-y-6">
            <div className="p-6 rounded-3xl bg-white border border-slate-200 shadow-sm space-y-2">
              <h2 className="text-lg font-bold text-slate-900">Step 4: Supporting Documents & Exhibits</h2>
              <p className="text-xs text-slate-500 leading-relaxed">
                Attach receipts, previous representations, email correspondence, or official notices.
              </p>
            </div>

            {/* Privacy Sanitizer Notice */}
            <div className="p-4 rounded-2xl bg-emerald-50 border border-emerald-200 text-emerald-900 text-xs flex items-start gap-3">
              <ShieldCheck className="w-5 h-5 text-emerald-600 shrink-0 mt-0.5" />
              <div>
                <span className="font-bold block">Automated Media Sanitization Enabled</span>
                <span className="text-emerald-700 leading-relaxed block mt-0.5">
                  NyayPath automatically scrubs PDF metadata dictionaries, author tags, and camera EXIF GPS tags from all uploads before storing them in private buckets.
                </span>
              </div>
            </div>

            {/* Upload Box */}
            <div className="p-8 rounded-3xl bg-white border-2 border-dashed border-slate-300 hover:border-court-maroon transition-colors text-center space-y-3">
              <div className="w-12 h-12 rounded-2xl bg-rose-50 text-court-maroon flex items-center justify-center mx-auto">
                <Upload className="w-6 h-6" />
              </div>
              <div>
                <h3 className="font-bold text-sm text-slate-900">Select files to upload</h3>
                <p className="text-xs text-slate-500 mt-1">
                  Supported: PDF, JPEG, PNG, WebP • Maximum 10MB per file
                </p>
              </div>

              <label className="inline-block px-5 py-2.5 rounded-xl bg-slate-900 hover:bg-slate-800 text-white font-bold text-xs cursor-pointer shadow-sm transition-colors">
                Browse Files
                <input
                  type="file"
                  onChange={handleFileUpload}
                  disabled={uploadingDoc}
                  accept=".pdf,image/jpeg,image/png,image/webp"
                  className="hidden"
                />
              </label>

              {uploadingDoc && (
                <div className="flex items-center justify-center gap-2 text-xs text-court-maroon font-bold pt-2">
                  <RefreshCw className="w-4 h-4 animate-spin" />
                  <span>Sanitizing & uploading document...</span>
                </div>
              )}

              {uploadError && (
                <div className="p-3 rounded-xl bg-rose-50 border border-rose-200 text-rose-700 text-xs font-medium">
                  {uploadError}
                </div>
              )}
            </div>

            {/* Uploaded Documents List */}
            <div className="p-6 rounded-3xl bg-white border border-slate-200 shadow-sm space-y-4">
              <div className="flex items-center justify-between">
                <h4 className="text-xs font-bold text-slate-900 uppercase tracking-wider flex items-center gap-2">
                  <FolderOpen className="w-4 h-4 text-court-maroon" />
                  <span>Attached Exhibits ({documents.length})</span>
                </h4>
                <span className="text-xs text-slate-400">Optional</span>
              </div>

              {documents.length > 0 ? (
                <div className="space-y-2.5">
                  {documents.map((doc, idx) => (
                    <div
                      key={doc.storage_path || idx}
                      className="p-3.5 rounded-2xl bg-slate-50 border border-slate-200 flex items-center justify-between gap-3"
                    >
                      <div className="flex items-center gap-3">
                        <div className="p-2 rounded-xl bg-white border border-slate-200 text-court-maroon">
                          <FileText className="w-4 h-4" />
                        </div>
                        <div>
                          <span className="text-xs font-bold text-slate-800 block truncate max-w-xs sm:max-w-md">
                            {doc.file_name}
                          </span>
                          <span className="text-[11px] text-slate-400 flex items-center gap-2">
                            <span>{doc.file_size_bytes ? `${Math.round(doc.file_size_bytes / 1024)} KB` : 'Attached'}</span>
                            <span>•</span>
                            <span className="text-emerald-600 font-medium">Sanitized & Encrypted</span>
                          </span>
                        </div>
                      </div>

                      <button
                        type="button"
                        onClick={() => handleRemoveDoc(idx)}
                        className="p-2 text-slate-400 hover:text-rose-600 hover:bg-rose-50 rounded-xl transition-colors cursor-pointer"
                        title="Remove exhibit"
                      >
                        <Trash2 className="w-4 h-4" />
                      </button>
                    </div>
                  ))}
                </div>
              ) : (
                <p className="text-xs text-slate-400 italic text-center py-4">
                  No documents attached yet. You can submit without documents or attach them later.
                </p>
              )}
            </div>
          </div>
        )}

        {/* =================================================================== */}
        {/* Step 5: Review & Statutory Affirmation */}
        {/* =================================================================== */}
        {currentStep === 5 && (
          <div className="space-y-6">
            <div className="p-6 rounded-3xl bg-white border border-slate-200 shadow-sm space-y-2">
              <h2 className="text-lg font-bold text-slate-900">Step 5: Review Before Submission</h2>
              <p className="text-xs text-slate-500 leading-relaxed">
                Please verify all entered details. Once submitted, your case will be registered on NyayPath Central Case Management and assigned a permanent Case ID.
              </p>
            </div>

            {/* Case Summary Card */}
            <div className="p-6 rounded-3xl bg-white border border-slate-200 shadow-sm space-y-4">
              <div className="flex items-center justify-between pb-3 border-b border-slate-100">
                <span className="text-xs font-bold uppercase tracking-wider text-slate-400">Jurisdiction</span>
                <span className="text-xs font-bold px-3 py-1 rounded-full bg-rose-50 text-court-maroon border border-rose-100">
                  {selectedCategoryObj?.title} ({subCategory})
                </span>
              </div>

              <div>
                <span className="text-[11px] font-bold text-slate-400 uppercase tracking-wider block mb-1">
                  Case Subject / Title
                </span>
                <span className="text-sm font-bold text-slate-900 block">{subject}</span>
              </div>

              <div className="grid grid-cols-1 sm:grid-cols-2 gap-4 text-xs">
                <div>
                  <span className="text-[11px] font-bold text-slate-400 uppercase tracking-wider block mb-1">
                    Department / Respondent
                  </span>
                  <span className="text-slate-800 font-medium">{department || 'General Administration'}</span>
                </div>
                <div>
                  <span className="text-[11px] font-bold text-slate-400 uppercase tracking-wider block mb-1">
                    Date of Occurrence
                  </span>
                  <span className="text-slate-800 font-medium">{incidentDate || 'Unspecified'}</span>
                </div>
              </div>

              <div>
                <span className="text-[11px] font-bold text-slate-400 uppercase tracking-wider block mb-1">
                  Narrative Facts
                </span>
                <p className="text-xs text-slate-700 leading-relaxed bg-slate-50 p-4 rounded-2xl border border-slate-200 whitespace-pre-wrap">
                  {facts}
                </p>
              </div>

              {remedySought && (
                <div>
                  <span className="text-[11px] font-bold text-slate-400 uppercase tracking-wider block mb-1">
                    Remedy Sought
                  </span>
                  <p className="text-xs text-slate-700 leading-relaxed bg-slate-50 p-3 rounded-xl border border-slate-200">
                    {remedySought}
                  </p>
                </div>
              )}

              <div className="flex items-center justify-between pt-2 text-xs">
                <span className="text-slate-500">Supporting Exhibits Attached:</span>
                <span className="font-bold text-slate-900">{documents.length} document(s)</span>
              </div>

              <div className="flex items-center justify-between text-xs">
                <span className="text-slate-500">Confidentiality Mode:</span>
                <span className={`font-bold ${isConfidential ? 'text-amber-700' : 'text-slate-700'}`}>
                  {isConfidential ? 'Confidential (Presiding Officer Only)' : 'Standard Redressal'}
                </span>
              </div>
            </div>

            {/* Legal Accuracy Notice & Platform Registration Disclaimer */}
            <div className="p-6 rounded-3xl bg-amber-50 border border-amber-200 text-amber-900 space-y-4">
              <div className="flex items-start gap-3">
                <Info className="w-5 h-5 text-amber-700 shrink-0 mt-0.5" />
                <div>
                  <h4 className="font-bold text-xs uppercase tracking-wider text-amber-900">
                    Statutory Notice & Platform Disclaimer
                  </h4>
                  <p className="text-xs text-amber-800 leading-relaxed mt-1">
                    Registration on NyayPath facilitates institutional grievance intake, administrative routing, and AI-assisted legal drafting. Submission here does not constitute formal appearance or electronic filing before the Supreme Court of India, High Courts, or District Courts.
                  </p>
                </div>
              </div>

              {/* Mandatory Affirmation Checkbox */}
              <label className="p-4 rounded-2xl bg-white border border-amber-300 flex items-start gap-3 cursor-pointer">
                <input
                  type="checkbox"
                  checked={declarationConfirmed}
                  onChange={e => setDeclarationConfirmed(e.target.checked)}
                  className="mt-1 w-4 h-4 rounded text-court-maroon focus:ring-court-maroon"
                />
                <span className="text-xs font-bold text-slate-800 leading-relaxed">
                  I solemnly affirm that the statements made above are true to the best of my knowledge and belief. I agree to proceed with case registration under the NyayPath terms of service.
                </span>
              </label>
            </div>

            {submissionError && (
              <div className="p-4 rounded-2xl bg-rose-50 border border-rose-200 text-rose-700 text-xs font-medium">
                {submissionError}
              </div>
            )}
          </div>
        )}

        {/* =================================================================== */}
        {/* Step 6: Confirmation & Case Credentials */}
        {/* =================================================================== */}
        {currentStep === 6 && submissionResult && (
          <div className="space-y-6">
            <div className="p-8 rounded-3xl bg-white border border-slate-200 shadow-sm text-center space-y-4">
              <div className="w-16 h-16 rounded-full bg-emerald-100 text-emerald-600 flex items-center justify-center mx-auto shadow-inner">
                <CheckCircle2 className="w-8 h-8" />
              </div>

              <div>
                <span className="text-xs font-bold text-emerald-600 uppercase tracking-wider block">
                  Case Successfully Registered
                </span>
                <h2 className="text-2xl font-black text-slate-900 mt-1">
                  {submissionResult.case_id}
                </h2>
                <p className="text-xs text-slate-500 mt-2 max-w-md mx-auto leading-relaxed">
                  Your case has been recorded on NyayPath Central Case Management. An initial activity milestone has been generated.
                </p>
              </div>

              {/* Case ID Copy */}
              <div className="max-w-md mx-auto p-4 rounded-2xl bg-slate-50 border border-slate-200 flex items-center justify-between gap-3">
                <div className="text-left">
                  <span className="text-[10px] font-bold text-slate-400 uppercase tracking-wider block">
                    Permanent Case Tracking ID
                  </span>
                  <span className="text-sm font-mono font-bold text-slate-900">
                    {submissionResult.case_id}
                  </span>
                </div>
                <button
                  type="button"
                  onClick={() => copyToClipboard(submissionResult.case_id, 'id')}
                  className="px-3 py-1.5 rounded-xl bg-white border border-slate-200 text-xs font-bold text-slate-700 hover:bg-slate-100 flex items-center gap-1.5 cursor-pointer shadow-sm transition-colors"
                >
                  {copiedId ? <Check className="w-3.5 h-3.5 text-emerald-600" /> : <Copy className="w-3.5 h-3.5" />}
                  <span>{copiedId ? 'Copied!' : 'Copy ID'}</span>
                </button>
              </div>

              {/* 128-bit Secret Verification Key */}
              <div className="max-w-md mx-auto p-4 rounded-2xl bg-amber-50 border border-amber-200 text-left space-y-2">
                <div className="flex items-center justify-between">
                  <span className="text-[10px] font-bold text-amber-900 uppercase tracking-wider flex items-center gap-1.5">
                    <Lock className="w-3.5 h-3.5 text-amber-700" />
                    128-Bit Secret Verification Key
                  </span>
                  <button
                    type="button"
                    onClick={() => copyToClipboard(submissionResult.verification_key, 'key')}
                    className="px-2.5 py-1 rounded-lg bg-white border border-amber-300 text-[11px] font-bold text-amber-900 hover:bg-amber-100/50 flex items-center gap-1 cursor-pointer"
                  >
                    {copiedKey ? <Check className="w-3 h-3 text-emerald-600" /> : <Copy className="w-3 h-3" />}
                    <span>{copiedKey ? 'Copied' : 'Copy Key'}</span>
                  </button>
                </div>
                <code className="text-xs font-mono font-bold text-amber-950 block break-all bg-white p-2.5 rounded-xl border border-amber-200">
                  {submissionResult.verification_key}
                </code>
                <p className="text-[11px] text-amber-700 leading-relaxed">
                  Important: Save this key. It allows you to verify identity and track progress publicly without logging in.
                </p>
              </div>

              {/* Action Buttons */}
              <div className="pt-4 flex flex-col sm:flex-row items-center justify-center gap-3">
                <Link
                  href={`/dashboard/my-cases/${encodeURIComponent(submissionResult.case_id)}`}
                  className="w-full sm:w-auto px-6 py-3 rounded-2xl bg-court-maroon hover:bg-rose-900 text-white font-bold text-xs shadow-md transition-colors flex items-center justify-center gap-2"
                >
                  <span>View Case Timeline & Documents</span>
                  <ChevronRight className="w-4 h-4" />
                </Link>

                <Link
                  href="/dashboard/my-cases"
                  className="w-full sm:w-auto px-6 py-3 rounded-2xl bg-slate-900 hover:bg-slate-800 text-white font-bold text-xs shadow-md transition-colors flex items-center justify-center gap-2"
                >
                  <span>Go to My Cases</span>
                </Link>

                <button
                  type="button"
                  onClick={() => {
                    setCurrentStep(1);
                    setSubject('');
                    setFacts('');
                    setRemedySought('');
                    setDepartment('');
                    setDocuments([]);
                    setDeclarationConfirmed(false);
                    setSubmissionResult(null);
                  }}
                  className="w-full sm:w-auto px-4 py-3 rounded-2xl bg-white border border-slate-200 text-slate-700 hover:bg-slate-50 font-bold text-xs transition-colors"
                >
                  File Another Case
                </button>
              </div>
            </div>
          </div>
        )}

        {/* =================================================================== */}
        {/* Navigation Controls (Steps 1 to 5) */}
        {/* =================================================================== */}
        {currentStep < 6 && (
          <div className="mt-8 pt-6 border-t border-slate-200 flex items-center justify-between">
            <button
              type="button"
              onClick={() => setCurrentStep(prev => Math.max(1, prev - 1))}
              disabled={currentStep === 1 || submitting}
              className="px-5 py-2.5 rounded-xl bg-white border border-slate-200 text-slate-700 hover:bg-slate-50 font-bold text-xs transition-colors flex items-center gap-2 cursor-pointer disabled:opacity-40 disabled:cursor-not-allowed shadow-sm"
            >
              <ArrowLeft className="w-4 h-4" />
              <span>Back</span>
            </button>

            {currentStep < 5 ? (
              <button
                type="button"
                onClick={() => setCurrentStep(prev => prev + 1)}
                disabled={!canProceedFromStep(currentStep)}
                className="px-6 py-2.5 rounded-xl bg-court-maroon hover:bg-rose-900 text-white font-bold text-xs transition-colors flex items-center gap-2 cursor-pointer disabled:opacity-40 disabled:cursor-not-allowed shadow-md"
              >
                <span>Continue</span>
                <ArrowRight className="w-4 h-4" />
              </button>
            ) : (
              <button
                type="button"
                onClick={handleSubmitCase}
                disabled={!canProceedFromStep(5) || submitting}
                className="px-8 py-3 rounded-xl bg-gradient-to-r from-court-maroon to-rose-700 hover:from-rose-700 hover:to-rose-800 text-white font-bold text-xs transition-all flex items-center gap-2 cursor-pointer disabled:opacity-50 disabled:cursor-not-allowed shadow-lg"
              >
                {submitting ? (
                  <>
                    <RefreshCw className="w-4 h-4 animate-spin" />
                    <span>Submitting to Registry...</span>
                  </>
                ) : (
                  <>
                    <CheckCircle2 className="w-4 h-4" />
                    <span>Submit & Register Case</span>
                  </>
                )}
              </button>
            )}
          </div>
        )}
      </div>
    </div>
  );
}

