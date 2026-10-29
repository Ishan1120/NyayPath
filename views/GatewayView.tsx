'use client';

import { useState } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import {
  ArrowRight,
  FileSearch,
  Loader2,
  KeyRound,
  Copy,
  Download,
  Lock,
  RefreshCw,
  FolderOpen,
  Check,
  ArrowLeft,
  Activity,
  Sparkles,
  ShieldCheck,
  Scale,
  Languages,
  CheckCircle2,
  FileText
} from 'lucide-react';
import { useRouter } from 'next/navigation';
import Link from 'next/link';
import useCaseStore from '@/store/caseStore';
import { initCase, getCase, classifyCase } from '@/lib/api';
import AudioRecorder from '@/components/dashboard/AudioRecorder';

interface PromptPreset {
  label: string;
  icon: string;
  category: string;
  text: string;
}

const SAMPLE_PROMPTS: PromptPreset[] = [
  {
    label: 'Road Potholes & PWD Tender',
    icon: '🛣️',
    category: 'RTI',
    text: 'Ward 12 main road carpeting was completed 3 months ago and already developed massive potholes. The contractor left work incomplete. I want certified copies of the tender agreement, measurement book entries, and third-party quality inspection audit reports.'
  },
  {
    label: 'Landlord Deposit Refusal',
    icon: '🏠',
    category: 'Grievance',
    text: 'My landlord withheld my ₹45,000 security deposit after I vacated the flat with 1 month prior notice. He has not provided any repair bills or receipts and is refusing to return my money.'
  },
  {
    label: 'Hospital Ayushman Cashless Denial',
    icon: '🏥',
    category: 'Grievance',
    text: 'A private empanelled hospital refused cashless admission for emergency surgery under Ayushman Bharat PM-JAY scheme and forced me to pay ₹1.2 lakhs out of pocket.'
  },
  {
    label: 'EPFO Pension Claim Hold',
    icon: '🏢',
    category: 'RTI',
    text: 'My EPS-95 pension claim filed 4 months ago has not been credited. Regional EPFO office rejected it without issuing any deficiency memo. I request certified copies of file movement notings and dealing officer records.'
  },
  {
    label: 'E-Commerce Return Refusal',
    icon: '📦',
    category: 'Consumer',
    text: 'E-commerce platform delivered a damaged laptop. The delivery package was torn. Customer support closed my return ticket within 24 hours without refund or replacement.'
  }
];

export default function GatewayView() {
  const router = useRouter();
  const [text, setText] = useState('');
  const [passkey, setPasskey] = useState('');
  const [resumeMode, setResumeMode] = useState(false);
  const [localErr, setLocalErr] = useState<string | null>(null);

  const [isResumeNavigating, setIsResumeNavigating] = useState(false);
  const [showPasskeyModal, setShowPasskeyModal] = useState(false);
  const [copied, setCopied] = useState(false);
  const [hasAgreed, setHasAgreed] = useState(false);

  const {
    stage,
    setStage,
    caseId,
    setCaseId,
    setUserProblem,
    language,
    setLanguage,
    hydrateState,
    reset
  } = useCaseStore();

  const isProcessing = stage === 'INITIALIZING' || showPasskeyModal || isResumeNavigating;

  const handleStartCase = async () => {
    if (!text.trim() || isProcessing) return;
    setLocalErr(null);
    setHasAgreed(false);
    try {
      const currentText = text.trim();
      const currentLang = language || 'English';

      reset();
      sessionStorage.removeItem('nyaypath_problem');
      sessionStorage.removeItem('janadhikar_problem');

      setLanguage(currentLang);
      setStage('INITIALIZING');
      const { case_id } = await initCase();
      setCaseId(case_id);
      setUserProblem(currentText);
      setStage('IDLE');
      setShowPasskeyModal(true);

      classifyCase(case_id, currentText, currentLang).catch(() => {});
    } catch (err: any) {
      setLocalErr(err?.response?.data?.detail || err.message || 'Something went wrong.');
      setStage('IDLE');
    }
  };

  const handleProceedToIntake = () => {
    if (!hasAgreed) return;
    setShowPasskeyModal(false);
    setLocalErr(null);
    router.push('/dashboard/intake');
  };

  const handleCopyId = () => {
    if (caseId) {
      navigator.clipboard.writeText(caseId);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    }
  };

  const handleDownloadTxt = () => {
    if (!caseId) return;
    const element = document.createElement('a');
    const file = new Blob(
      [`NyayPath Private Case ID: ${caseId}\nKeep this passkey safe to resume your case anytime at http://localhost:3000/dashboard`],
      { type: 'text/plain' }
    );
    element.href = URL.createObjectURL(file);
    element.download = `${caseId}-Passkey.txt`;
    document.body.appendChild(element);
    element.click();
    document.body.removeChild(element);
  };

  const handleResume = async () => {
    if (!passkey.trim() || isProcessing) return;
    setLocalErr(null);
    setStage('INITIALIZING');
    try {
      const res = await getCase(passkey.trim().toUpperCase());
      if (!res || !res.case_id) throw new Error('Case not found.');

      setIsResumeNavigating(true);
      hydrateState(res.case_id, res.data || {});
      const st = res.computed_status || res.data?.status || 'FILED';
      const rt = res.data?.route || res.route;

      if (st === 'rti_completed' || st === 'rti_predicted' || st === 'rti_drafted') {
        router.push('/dashboard/rti/result');
      } else if (st === 'grievance_completed') {
        router.push('/dashboard/grievance/result');
      } else if (rt === 'RTI' || rt === 'Rights/Grievance' || st === 'classified' || st === 'initialized' || st === 'FILED' || st === 'ACTIVE') {
        router.push('/dashboard/intake');
      } else {
        router.push(`/track?case_id=${res.case_id}`);
      }
    } catch (err) {
      setIsResumeNavigating(false);
      setLocalErr('Invalid Case ID or expired session. Please verify your passkey.');
      setStage('IDLE');
    }
  };

  return (
    <div className="min-h-screen flex flex-col items-center justify-center p-4 sm:p-6 lg:p-8 relative overflow-hidden bg-gradient-to-br from-[#0A0F1D] via-[#0F172A] to-[#1E1B4B] text-slate-100 font-sans">
      {/* Decorative ambient gradient orbs */}
      <div className="absolute top-[-15%] left-[-10%] w-[50vw] h-[50vw] rounded-full bg-court-maroon/20 blur-[140px] pointer-events-none" />
      <div className="absolute bottom-[-15%] right-[-10%] w-[50vw] h-[50vw] rounded-full bg-amber-600/15 blur-[150px] pointer-events-none" />

      {/* Top Navbar items */}
      <div className="absolute top-5 left-5 z-20">
        <Link
          className="inline-flex items-center gap-2 px-3.5 py-2 rounded-full bg-white/10 hover:bg-white/15 backdrop-blur-md border border-white/15 text-slate-200 text-xs font-semibold shadow-sm hover:text-white transition-all cursor-pointer"
          href="/"
        >
          <ArrowLeft size={14} />
          <span>Back to Landing</span>
        </Link>
      </div>

      <div className="absolute top-5 right-5 z-20 hidden sm:flex items-center gap-2 px-3.5 py-1.5 rounded-full bg-emerald-500/10 border border-emerald-500/20 text-emerald-400 text-xs font-semibold">
        <span className="w-2 h-2 rounded-full bg-emerald-400 animate-pulse" />
        <span>Legal Engine v2.6 Active</span>
      </div>

      {/* Passkey Modal */}
      <AnimatePresence>
        {showPasskeyModal && (
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            className="fixed inset-0 z-50 flex items-center justify-center bg-black/70 backdrop-blur-md p-4"
          >
            <motion.div
              initial={{ scale: 0.95, y: 20 }}
              animate={{ scale: 1, y: 0 }}
              exit={{ scale: 0.95, y: 20 }}
              className="bg-white rounded-3xl shadow-2xl max-w-lg w-full p-6 sm:p-8 border border-slate-200 relative overflow-hidden text-center text-slate-900"
            >
              <div className="absolute top-0 left-0 w-full h-1.5 bg-gradient-to-r from-court-maroon via-rose-600 to-amber-500" />

              <div className="inline-flex items-center gap-1.5 px-3 py-1 bg-rose-50 text-court-maroon border border-rose-200 rounded-full text-xs font-bold mb-4">
                <KeyRound size={13} />
                <span>Case Passkey Generated</span>
              </div>

              <h2 className="text-2xl sm:text-3xl font-black text-ashoka-navy mb-2 tracking-tight">
                Save Your Case ID
              </h2>
              <p className="text-xs sm:text-sm text-slate-600 mb-6 max-w-sm mx-auto font-medium">
                This 12-character token is the <strong>only key</strong> to reopen and track your case. Zero email or phone required.
              </p>

              <div className="bg-slate-900 border border-slate-800 rounded-2xl p-5 shadow-inner mb-5 text-center">
                <span className="block text-[10px] font-bold text-slate-400 uppercase tracking-widest mb-2">
                  CRYPTOGRAPHIC CASE PASSKEY
                </span>
                <div className="text-2xl sm:text-3xl font-mono font-black text-amber-400 tracking-wider mb-4 drop-shadow-sm select-all">
                  {caseId}
                </div>

                <div className="flex flex-col sm:flex-row items-center justify-center gap-2">
                  <button
                    onClick={handleCopyId}
                    className="w-full sm:w-auto flex-1 bg-gradient-to-r from-court-maroon to-rose-700 hover:from-rose-700 hover:to-rose-800 text-white font-bold py-2.5 px-4 rounded-xl transition-all shadow-md flex items-center justify-center gap-2 text-xs cursor-pointer"
                  >
                    {copied ? <Check size={14} className="text-emerald-300" /> : <Copy size={14} />}
                    <span>{copied ? 'Copied to Clipboard!' : 'Copy Case ID'}</span>
                  </button>

                  <button
                    onClick={handleDownloadTxt}
                    className="w-full sm:w-auto flex-1 bg-slate-800 hover:bg-slate-700 text-slate-200 border border-slate-700 font-bold py-2.5 px-4 rounded-xl transition-all shadow-sm flex items-center justify-center gap-2 text-xs cursor-pointer"
                  >
                    <Download size={14} className="text-amber-400" />
                    <span>Download .txt Key</span>
                  </button>
                </div>
              </div>

              <div className="bg-amber-50 border border-amber-200 rounded-xl p-3 text-left flex items-start gap-2.5 mb-4">
                <Lock size={15} className="text-amber-700 mt-0.5 shrink-0" />
                <p className="text-[11px] text-amber-900 leading-relaxed font-medium">
                  <strong>Zero-Account Guarantee:</strong> We do not store your name, email, or password. Keep this key safe.
                </p>
              </div>

              <div className="flex items-start gap-2.5 mb-5 bg-slate-50 p-3 rounded-xl border border-slate-200 text-left">
                <input
                  type="checkbox"
                  id="modal-agreement"
                  checked={hasAgreed}
                  onChange={(e) => setHasAgreed(e.target.checked)}
                  className="mt-0.5 w-4 h-4 text-court-maroon bg-white border-slate-300 rounded focus:ring-court-maroon cursor-pointer shrink-0"
                />
                <label
                  htmlFor="modal-agreement"
                  className="text-xs text-slate-700 font-medium cursor-pointer leading-relaxed select-none"
                >
                  I have copied or downloaded my Passkey and understand it is required to resume my case.
                </label>
              </div>

              {localErr && (
                <div className="p-3 bg-red-50 text-red-700 text-xs rounded-xl mb-4 text-left border border-red-200 font-medium">
                  {localErr}
                </div>
              )}

              <button
                onClick={handleProceedToIntake}
                disabled={!hasAgreed}
                className="w-full justify-center text-sm py-3.5 cursor-pointer disabled:opacity-40 disabled:cursor-not-allowed bg-gradient-to-r from-court-maroon via-rose-700 to-court-maroon hover:from-rose-700 hover:to-rose-800 text-white rounded-xl flex items-center gap-2 font-bold tracking-tight shadow-lg shadow-rose-950/30 transition-all"
              >
                <span>Proceed to Legal Intake Form</span>
                <ArrowRight size={16} />
              </button>
            </motion.div>
          </motion.div>
        )}
      </AnimatePresence>

      {/* Main View */}
      <AnimatePresence mode="wait">
        {!resumeMode && !isResumeNavigating ? (
          <motion.div
            key="main"
            initial={{ opacity: 0, y: 15 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, y: -15 }}
            className="w-full max-w-3xl text-center z-10"
          >
            {/* Header Badge */}
            <div className="inline-flex items-center gap-2 px-4 py-1.5 rounded-full bg-white/10 backdrop-blur-md border border-white/15 text-amber-300 text-xs font-semibold mb-4 shadow-sm">
              <Scale size={14} className="text-amber-400" />
              <span>AI-Powered Citizen Legal &amp; RTI Filing Engine</span>
            </div>

            <h1 className="text-3xl sm:text-5xl font-black text-white mb-3 tracking-tight drop-shadow-md">
              What is your legal issue?
            </h1>
            <p className="text-sm sm:text-base text-slate-300 mb-6 max-w-xl mx-auto font-medium leading-relaxed">
              Speak or write in plain <strong>English, Hindi, or Hinglish</strong>. Our AI legal triage engine classifies the issue, resolves jurisdiction, and drafts statutory documents.
            </p>

            {/* Language Selection Pills */}
            <div className="flex items-center justify-center gap-2 mb-4">
              <span className="text-xs text-slate-400 font-semibold flex items-center gap-1 mr-1">
                <Languages size={13} /> Language:
              </span>
              {[
                { code: 'English', label: 'English' },
                { code: 'Hindi', label: 'हिन्दी (Hindi)' },
                { code: 'Hinglish', label: 'Hinglish' }
              ].map((lang) => (
                <button
                  key={lang.code}
                  type="button"
                  onClick={() => setLanguage(lang.code)}
                  className={`px-3 py-1 rounded-full text-xs font-bold transition-all cursor-pointer ${
                    language === lang.code
                      ? 'bg-amber-400 text-slate-950 shadow-md shadow-amber-500/20 scale-105'
                      : 'bg-white/10 text-slate-300 hover:bg-white/20 hover:text-white border border-white/10'
                  }`}
                >
                  {lang.label}
                </button>
              ))}
            </div>

            {/* Problem Input Card */}
            <div className="bg-white/95 backdrop-blur-xl border border-white/20 rounded-3xl shadow-2xl mb-4 text-left overflow-hidden ring-1 ring-black/5">
              <textarea
                rows={5}
                value={text}
                onChange={(e) => setText(e.target.value)}
                disabled={stage === 'INITIALIZING'}
                placeholder={`Describe your civic grievance or request in detail...\n\ne.g. "The main road in Gomti Nagar was laid 3 months ago and already developed huge potholes. Municipal corporation closed my complaint unsolved. I want copies of the tender, contractor agreement, and inspection reports."`}
                className="w-full bg-transparent p-5 sm:p-6 text-base sm:text-lg text-slate-900 font-medium placeholder-slate-400 focus:outline-none resize-none leading-relaxed"
              />

              {/* Bottom bar with Voice Dictation */}
              <div className="flex flex-wrap items-center justify-between gap-3 px-5 sm:px-6 py-4 bg-slate-50/80 border-t border-slate-200">
                <AudioRecorder
                  language={language}
                  onTranscription={(transcribedText) => {
                    setText((prev) => (prev ? `${prev.trim()} ${transcribedText}` : transcribedText));
                  }}
                />

                <div className="flex items-center gap-2">
                  {text.trim().length > 0 && (
                    <button
                      type="button"
                      onClick={() => setText('')}
                      className="text-xs text-slate-400 hover:text-slate-600 transition-colors font-medium px-2 py-1"
                    >
                      Clear
                    </button>
                  )}
                  <span className="text-xs text-slate-500 font-medium">
                    {text.length} characters
                  </span>
                </div>
              </div>
            </div>

            {/* Quick 1-Click Interactive Example Chips */}
            <div className="mb-6 text-left">
              <span className="block text-[11px] font-bold text-slate-400 uppercase tracking-wider mb-2 text-center sm:text-left">
                ⚡ Or click an example to test instantly:
              </span>
              <div className="flex flex-wrap gap-2 justify-center sm:justify-start">
                {SAMPLE_PROMPTS.map((sample, idx) => (
                  <button
                    key={idx}
                    type="button"
                    onClick={() => setText(sample.text)}
                    className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-xl bg-white/10 hover:bg-white/20 border border-white/10 text-slate-200 hover:text-white text-xs font-semibold transition-all cursor-pointer shadow-xs active:scale-95"
                  >
                    <span>{sample.icon}</span>
                    <span>{sample.label}</span>
                    <span className="text-[10px] px-1.5 py-0.5 rounded-md bg-white/10 text-amber-300 font-mono">
                      {sample.category}
                    </span>
                  </button>
                ))}
              </div>
            </div>

            {localErr && (
              <div className="p-3.5 bg-rose-500/20 border border-rose-500/40 text-rose-200 text-xs sm:text-sm rounded-2xl mb-4 text-left font-medium">
                {localErr}
              </div>
            )}

            {/* Main Submit Button */}
            <button
              onClick={handleStartCase}
              disabled={!text.trim() || stage === 'INITIALIZING'}
              className="w-full justify-center text-base sm:text-lg py-4 cursor-pointer disabled:opacity-40 disabled:cursor-not-allowed bg-gradient-to-r from-court-maroon via-rose-700 to-court-maroon hover:from-rose-700 hover:to-rose-800 text-white rounded-2xl font-black tracking-tight shadow-xl shadow-rose-950/50 flex items-center gap-2.5 transition-all hover:scale-[1.01] active:scale-[0.99]"
            >
              {stage === 'INITIALIZING' ? (
                <>
                  <Loader2 className="animate-spin" size={20} />
                  <span>Generating Case Passkey...</span>
                </>
              ) : (
                <>
                  <span>Analyze Problem &amp; Generate Filing Draft</span>
                  <ArrowRight size={20} />
                </>
              )}
            </button>

            {/* Footer Navigation Shortcuts */}
            <div className="mt-8 flex flex-col sm:flex-row items-center justify-center gap-4 sm:gap-6 px-2 text-xs font-semibold">
              <button
                onClick={() => setResumeMode(true)}
                className="text-slate-300 hover:text-white transition-colors cursor-pointer flex items-center gap-1.5"
              >
                <FolderOpen size={15} className="text-amber-400" />
                <span>Resume Saved Case</span>
              </button>
              <span className="hidden sm:block text-slate-600">•</span>
              <Link
                className="text-slate-300 hover:text-emerald-300 transition-colors cursor-pointer flex items-center gap-1.5"
                href="/track"
              >
                <Activity size={15} className="text-emerald-400" />
                <span>Track 30-Day SLA &amp; Penalty</span>
              </Link>
              <span className="hidden sm:block text-slate-600">•</span>
              <button
                onClick={() => {
                  reset();
                  setText('');
                  setPasskey('');
                  sessionStorage.removeItem('nyaypath_problem');
      sessionStorage.removeItem('janadhikar_problem');
                }}
                className="text-slate-400 hover:text-slate-200 transition-colors cursor-pointer flex items-center gap-1.5"
              >
                <RefreshCw size={14} />
                <span>Reset Form</span>
              </button>
            </div>
          </motion.div>
        ) : (
          /* Resume Case View */
          <motion.div
            key="resume"
            initial={{ opacity: 0, scale: 0.98 }}
            animate={{ opacity: 1, scale: 1 }}
            exit={{ opacity: 0, scale: 0.98 }}
            className="w-full max-w-lg bg-white/95 backdrop-blur-xl p-8 rounded-3xl shadow-2xl border border-white/20 text-center z-10 text-slate-900"
          >
            <div className="w-14 h-14 bg-rose-50 text-court-maroon rounded-2xl flex items-center justify-center mx-auto mb-5 border border-rose-100 shadow-sm">
              <FolderOpen size={26} />
            </div>
            <h2 className="text-2xl sm:text-3xl font-black text-ashoka-navy mb-2 tracking-tight">
              Resume Your Case
            </h2>
            <p className="text-slate-600 mb-6 text-xs sm:text-sm font-medium">
              Enter your 12-character Passkey to restore your drafts, risk score, and SLA status.
            </p>

            <input
              type="text"
              value={passkey}
              onChange={(e) => setPasskey(e.target.value.toUpperCase())}
              placeholder="e.g. CR-XXXX-XXXX"
              maxLength={12}
              className="w-full text-center bg-slate-50 border border-slate-300 rounded-2xl p-4 text-xl font-mono font-black text-ashoka-navy tracking-widest uppercase mb-5 placeholder-slate-400 focus:ring-2 focus:ring-court-maroon/20 focus:border-court-maroon focus:outline-none shadow-inner"
            />

            {localErr && (
              <div className="p-3 bg-red-50 text-red-700 text-xs rounded-xl mb-4 text-left border border-red-200 font-medium">
                {localErr}
              </div>
            )}

            <button
              onClick={handleResume}
              disabled={!passkey.trim() || stage === 'INITIALIZING' || isResumeNavigating}
              className="w-full justify-center text-base py-3.5 mb-6 shadow-lg cursor-pointer bg-gradient-to-r from-court-maroon to-rose-700 hover:from-rose-700 hover:to-rose-800 text-white rounded-xl font-bold tracking-tight flex items-center gap-2 transition-all"
            >
              {stage === 'INITIALIZING' || isResumeNavigating ? (
                <>
                  <Loader2 className="animate-spin" size={18} />
                  <span>Retrieving Case Data...</span>
                </>
              ) : (
                <>
                  <span>Open Saved Case</span>
                  <ArrowRight size={18} />
                </>
              )}
            </button>

            <div className="flex items-center justify-between border-t border-slate-200 pt-5 text-xs font-semibold">
              <button
                onClick={() => setResumeMode(false)}
                className="text-slate-600 hover:text-court-maroon transition-colors cursor-pointer"
              >
                Start a new case instead
              </button>
              <button
                onClick={() => {
                  reset();
                  setText('');
                  setPasskey('');
                }}
                className="text-slate-400 hover:text-slate-600 transition-colors cursor-pointer flex items-center gap-1"
              >
                <RefreshCw size={13} />
                <span>Clear</span>
              </button>
            </div>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
}
