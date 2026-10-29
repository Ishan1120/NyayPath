'use client';

import React, { useState, useEffect } from 'react';
import { 
  Sparkles, 
  HelpCircle, 
  CheckCircle2, 
  ArrowRight, 
  Loader2, 
  Scale, 
  Mic, 
  Square, 
  Volume2, 
  Briefcase,
  AlertCircle,
  Check,
  ChevronDown,
  Info
} from 'lucide-react';
import { getClarifyingQuestions, synthesizeDraft } from '@/lib/api';
import useCaseStore from '@/store/caseStore';
import { useRouter } from 'next/navigation';

interface ClarifyingQuestion {
  id: string;
  field_key: string;
  title: string;
  question: string;
  placeholder: string;
  suggestions: string[];
}

interface ClarifyingQuestionsViewProps {
  onComplete?: () => void;
  onSwitchToManualForm?: () => void;
}

export default function ClarifyingQuestionsView({ onComplete, onSwitchToManualForm }: ClarifyingQuestionsViewProps) {
  const router = useRouter();
  const { 
    caseId, 
    userProblem, 
    language, 
    setRtiDraft, 
    setGrievanceResult, 
    setStage,
    formData,
    setFormData
  } = useCaseStore();

  const [loading, setLoading] = useState(true);
  const [generating, setGenerating] = useState(false);
  const [recognizedIssue, setRecognizedIssue] = useState<string>('');
  const [category, setCategory] = useState<string>('');
  const [likelyRoute, setLikelyRoute] = useState<string>('RTI');
  const [targetAuthority, setTargetAuthority] = useState<string>('');
  const [statutoryAct, setStatutoryAct] = useState<string>('');
  const [questions, setQuestions] = useState<ClarifyingQuestion[]>([]);
  const [answers, setAnswers] = useState<Record<string, string>>({});
  const [activeVoiceIndex, setActiveVoiceIndex] = useState<number | null>(null);
  const [interimVoiceText, setInterimVoiceText] = useState<string>('');
  const [errorMsg, setErrorMsg] = useState<string | null>(null);

  // Load questions on mount based on user complaint
  useEffect(() => {
    let isMounted = true;

    async function loadQuestions() {
      if (!userProblem) return;
      try {
        setLoading(true);
        const res = await getClarifyingQuestions(userProblem, language || 'English');
        if (isMounted && res) {
          setRecognizedIssue(res.recognized_issue || 'Civic & Legal Grievance');
          setCategory(res.category || 'Public Administration');
          setLikelyRoute(res.likely_route || 'RTI');
          setTargetAuthority(res.target_authority || 'Competent Authority');
          setStatutoryAct(res.statutory_act || 'Right to Information Act, 2005');
          setQuestions(res.questions || []);

          // Pre-populate any existing answers or smart suggestions
          const initialAnswers: Record<string, string> = {};
          (res.questions || []).forEach((q: ClarifyingQuestion) => {
            if (formData && formData[q.field_key]) {
              initialAnswers[q.field_key] = formData[q.field_key];
            }
          });
          setAnswers(initialAnswers);
        }
      } catch (err: any) {
        console.error('Failed to load clarifying questions:', err);
      } finally {
        if (isMounted) setLoading(false);
      }
    }

    loadQuestions();
    return () => { isMounted = false; };
  }, [userProblem, language, formData]);

  const handleAnswerChange = (fieldKey: string, value: string) => {
    setAnswers((prev) => ({ ...prev, [fieldKey]: value }));
  };

  const handleSelectSuggestion = (fieldKey: string, suggestion: string) => {
    setAnswers((prev) => ({ ...prev, [fieldKey]: suggestion }));
  };

  const handleQuickFillDefaults = () => {
    const updated: Record<string, string> = { ...answers };
    questions.forEach((q) => {
      if (!updated[q.field_key] && q.suggestions && q.suggestions.length > 0) {
        updated[q.field_key] = q.suggestions[0];
      }
    });
    setAnswers(updated);
  };

  // Voice dictation for individual questions
  const handleVoiceToggle = (index: number, fieldKey: string) => {
    if (activeVoiceIndex === index) {
      // Stop
      setActiveVoiceIndex(null);
      setInterimVoiceText('');
      return;
    }

    const SpeechRecognition =
      (window as any).SpeechRecognition || (window as any).webkitSpeechRecognition;

    if (!SpeechRecognition) {
      alert('Voice dictation is not supported in this browser. Please type your answer.');
      return;
    }

    try {
      const recognition = new SpeechRecognition();
      recognition.continuous = false;
      recognition.interimResults = true;
      recognition.lang = language === 'Hindi' ? 'hi-IN' : 'en-IN';

      recognition.onstart = () => {
        setActiveVoiceIndex(index);
        setInterimVoiceText('');
      };

      recognition.onresult = (event: any) => {
        let transcript = '';
        for (let i = event.resultIndex; i < event.results.length; ++i) {
          transcript += event.results[i][0].transcript;
        }
        setInterimVoiceText(transcript);
        if (event.results[0].isFinal) {
          handleAnswerChange(fieldKey, transcript);
          setActiveVoiceIndex(null);
          setInterimVoiceText('');
        }
      };

      recognition.onerror = () => {
        setActiveVoiceIndex(null);
        setInterimVoiceText('');
      };

      recognition.onend = () => {
        setActiveVoiceIndex(null);
      };

      recognition.start();
    } catch (err) {
      console.warn('Speech error:', err);
      setActiveVoiceIndex(null);
    }
  };

  // Synthesize answers into a systematic legal draft
  const handleSynthesizeDraft = async () => {
    setGenerating(true);
    setErrorMsg(null);
    try {
      // Merge answered questions into formData store
      const mergedFormData = { ...formData, ...answers };
      setFormData(mergedFormData);

      const res = await synthesizeDraft({
        case_id: caseId || undefined,
        problem_text: userProblem,
        answers: answers,
        language: language || 'English',
        route: likelyRoute,
        applicant_name: mergedFormData.applicant_name || 'The Citizen / Complainant'
      });

      if (likelyRoute === 'RTI') {
        setRtiDraft(res.systematic_draft);
        setStage('PREDICTING');
        router.push('/dashboard/rti/result');
      } else {
        setGrievanceResult({
          demand_notice_draft: res.systematic_draft,
          lawyer_brief: res.lawyer_brief,
          violated_rights: [res.domain_name, 'Right to Fair Service & Redressal'],
          legal_explanation: `Systematically structured petition formulated under ${res.statutory_act}.`,
          target_portal_name: 'CPGRAMS / National Consumer Commission',
          target_portal_url: 'https://pgportal.gov.in'
        });
        setStage('GRIEVANCE_COMPLETED');
        router.push('/dashboard/grievance/result');
      }

      if (onComplete) onComplete();
    } catch (err: any) {
      console.error('Failed to synthesize systematic draft:', err);
      setErrorMsg('Failed to generate systematic draft. You can proceed with the standard form below.');
    } finally {
      setGenerating(false);
    }
  };

  const answeredCount = questions.filter((q) => answers[q.field_key]?.trim()).length;
  const progressPercent = questions.length ? Math.round((answeredCount / questions.length) * 100) : 0;

  if (loading) {
    return (
      <div className="bg-white/95 backdrop-blur-md rounded-3xl p-8 border border-slate-200 shadow-xl text-center space-y-4">
        <Loader2 className="animate-spin text-court-maroon mx-auto" size={38} />
        <h3 className="text-lg font-black text-slate-900 tracking-tight">
          Recognizing Complaint &amp; Formulating Clarifying Questions...
        </h3>
        <p className="text-xs text-slate-500 font-medium max-w-md mx-auto">
          Our legal engine is scanning statutory precedents to determine what specific facts will make your draft court-admissible.
        </p>
      </div>
    );
  }

  return (
    <div className="bg-white/95 backdrop-blur-md rounded-3xl p-6 sm:p-8 border border-slate-200 shadow-xl space-y-6 text-left">
      {/* Recognized Complaint Header */}
      <div className="bg-gradient-to-r from-slate-900 via-slate-800 to-slate-900 text-white rounded-2xl p-5 border border-slate-700/60 shadow-md">
        <div className="flex flex-wrap items-center justify-between gap-3 mb-2">
          <div className="inline-flex items-center gap-1.5 px-3 py-1 bg-amber-400/20 text-amber-300 border border-amber-400/30 rounded-full text-xs font-bold">
            <Sparkles size={13} className="text-amber-400" />
            <span>AI Complaint Recognition Active</span>
          </div>
          <span className="text-[11px] font-mono text-slate-300 bg-white/10 px-2.5 py-1 rounded-lg">
            Statutory Route: {likelyRoute === 'RTI' ? 'RTI Act 2005' : 'Consumer / Grievance'}
          </span>
        </div>

        <h3 className="text-lg sm:text-xl font-black text-white tracking-tight">
          {recognizedIssue}
        </h3>
        <p className="text-xs text-slate-300 mt-1 font-medium leading-relaxed">
          Target Authority: <strong className="text-amber-200">{targetAuthority}</strong> • Statutory Basis: <strong className="text-emerald-300">{statutoryAct}</strong>
        </p>

        {/* Live Fact Progress Bar */}
        <div className="mt-4 pt-3 border-t border-slate-700/60 flex items-center justify-between text-xs font-semibold">
          <span className="text-slate-300">
            Factual Standing: <strong className="text-white">{answeredCount} of {questions.length} facts collected</strong>
          </span>
          <span className="text-amber-300 font-bold">{progressPercent}% Ready</span>
        </div>
        <div className="w-full bg-slate-700 rounded-full h-1.5 mt-1.5 overflow-hidden">
          <div
            className="bg-gradient-to-r from-amber-400 to-emerald-400 h-full rounded-full transition-all duration-300"
            style={{ width: `${progressPercent}%` }}
          />
        </div>
      </div>

      {/* Purpose Description */}
      <div className="bg-rose-50/60 border border-rose-200/80 rounded-2xl p-4 flex items-start gap-3">
        <Scale size={18} className="text-court-maroon shrink-0 mt-0.5" />
        <div className="text-xs text-slate-700 leading-relaxed font-medium">
          <strong className="text-court-maroon block font-bold mb-0.5">Why these clarifying questions?</strong>
          Raw complaints often get dismissed due to missing dates, unquantified loss, or vague relief. Answering these 4 quick questions allows the AI to draft a <strong>systematic, numbered legal petition</strong> with chronological facts that can be filed directly or forwarded to an advocate.
        </div>
      </div>

      {/* Quick Auto-Fill Action */}
      <div className="flex items-center justify-between">
        <span className="text-xs font-bold uppercase tracking-wider text-slate-500">
          Clarifying Questions ({questions.length})
        </span>
        <button
          type="button"
          onClick={handleQuickFillDefaults}
          className="text-xs font-bold text-court-maroon hover:text-rose-800 transition-colors cursor-pointer flex items-center gap-1"
        >
          <span>⚡ Auto-fill recommended defaults</span>
        </button>
      </div>

      {/* Questions List */}
      <div className="space-y-5">
        {questions.map((q, idx) => {
          const isAnswered = !!answers[q.field_key]?.trim();
          const isVoiceActive = activeVoiceIndex === idx;

          return (
            <div
              key={q.id}
              className={`p-5 rounded-2xl border transition-all duration-200 ${
                isAnswered
                  ? 'bg-slate-50/80 border-slate-300 shadow-xs'
                  : 'bg-white border-slate-300/80 hover:border-court-maroon/40 shadow-sm'
              }`}
            >
              <div className="flex items-start justify-between gap-3 mb-2">
                <div className="flex items-center gap-2">
                  <span className={`w-6 h-6 rounded-full flex items-center justify-center text-xs font-bold shrink-0 ${
                    isAnswered ? 'bg-emerald-600 text-white' : 'bg-slate-200 text-slate-700'
                  }`}>
                    {isAnswered ? '✓' : idx + 1}
                  </span>
                  <h4 className="text-sm font-black text-slate-900 tracking-tight">
                    {q.title}
                  </h4>
                </div>

                {/* Voice Dictation Button for this question */}
                <button
                  type="button"
                  onClick={() => handleVoiceToggle(idx, q.field_key)}
                  className={`inline-flex items-center gap-1.5 px-3 py-1 rounded-full text-xs font-bold transition-all cursor-pointer select-none ${
                    isVoiceActive
                      ? 'bg-red-600 text-white animate-pulse shadow-md'
                      : 'bg-slate-100 hover:bg-slate-200 text-slate-700 border border-slate-300'
                  }`}
                  title="Speak answer via microphone"
                >
                  {isVoiceActive ? (
                    <>
                      <Square size={11} className="fill-current text-white animate-bounce" />
                      <span>Listening...</span>
                    </>
                  ) : (
                    <>
                      <Mic size={12} className="text-court-maroon" />
                      <span>Speak</span>
                    </>
                  )}
                </button>
              </div>

              <p className="text-xs text-slate-600 font-medium mb-3 pl-8">
                {q.question}
              </p>

              {/* Voice Interim Feedback */}
              {isVoiceActive && interimVoiceText && (
                <div className="ml-8 mb-2 flex items-center gap-2 p-2 bg-rose-50 border border-rose-200 rounded-xl text-xs text-rose-800 font-medium">
                  <Volume2 size={13} className="text-rose-600 animate-pulse" />
                  <span className="italic truncate">&quot;{interimVoiceText}&quot;</span>
                </div>
              )}

              {/* Text Input */}
              <div className="ml-8">
                <input
                  type="text"
                  value={answers[q.field_key] || ''}
                  onChange={(e) => handleAnswerChange(q.field_key, e.target.value)}
                  placeholder={q.placeholder}
                  className="w-full bg-white border border-slate-300 rounded-xl px-3.5 py-2.5 text-xs text-slate-900 font-medium focus:outline-none focus:border-court-maroon focus:ring-1 focus:ring-court-maroon transition-all shadow-inner"
                />

                {/* Smart Suggestion Chips */}
                {q.suggestions && q.suggestions.length > 0 && (
                  <div className="flex flex-wrap items-center gap-1.5 mt-2.5">
                    <span className="text-[10px] font-bold text-slate-400 uppercase tracking-wider mr-1">
                      Quick select:
                    </span>
                    {q.suggestions.map((sug, sIdx) => {
                      const isSelected = answers[q.field_key] === sug;
                      return (
                        <button
                          key={sIdx}
                          type="button"
                          onClick={() => handleSelectSuggestion(q.field_key, sug)}
                          className={`text-[11px] px-2.5 py-1 rounded-lg font-medium transition-all cursor-pointer border ${
                            isSelected
                              ? 'bg-court-maroon text-white border-court-maroon font-bold shadow-xs'
                              : 'bg-slate-100 hover:bg-slate-200 text-slate-700 border-slate-200'
                          }`}
                        >
                          {isSelected && <span className="mr-1">✓</span>}
                          {sug}
                        </button>
                      );
                    })}
                  </div>
                )}
              </div>
            </div>
          );
        })}
      </div>

      {errorMsg && (
        <div className="p-3 bg-red-50 text-red-700 text-xs rounded-xl border border-red-200 font-medium flex items-center gap-2">
          <AlertCircle size={15} className="shrink-0 text-red-600" />
          <span>{errorMsg}</span>
        </div>
      )}

      {/* Action CTA Bar */}
      <div className="pt-4 border-t border-slate-200 flex flex-col sm:flex-row items-center justify-between gap-3">
        {onSwitchToManualForm && (
          <button
            type="button"
            onClick={onSwitchToManualForm}
            className="text-xs text-slate-500 hover:text-slate-800 font-semibold underline cursor-pointer transition-colors"
          >
            Switch to manual standard form
          </button>
        )}

        <button
          type="button"
          onClick={handleSynthesizeDraft}
          disabled={generating}
          className="w-full sm:w-auto ml-auto px-8 py-3.5 bg-gradient-to-r from-court-maroon via-rose-700 to-court-maroon hover:from-rose-700 hover:to-rose-800 text-white rounded-xl font-bold text-sm tracking-tight shadow-md hover:shadow-xl transition-all cursor-pointer flex items-center justify-center gap-2 disabled:opacity-50"
        >
          {generating ? (
            <>
              <Loader2 size={16} className="animate-spin text-amber-300" />
              <span>Synthesizing Systematic Legal Draft...</span>
            </>
          ) : (
            <>
              <span>⚡ Synthesize Systematic Legal Draft</span>
              <ArrowRight size={16} />
            </>
          )}
        </button>
      </div>
    </div>
  );
}

