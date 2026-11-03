'use client';

import React, { useState, useEffect, useRef, useMemo } from 'react';
import Link from 'next/link';
import { motion, AnimatePresence } from 'framer-motion';
import {
  ArrowRight,
  Copy,
  Download,
  CheckCheck,
  FileText,
  Printer,
  Loader2,
  Globe,
  Scale,
  Briefcase,
  Check,
  Save,
  CloudCheck,
  CloudOff,
  Edit3,
  Trash2,
  FolderOpen,
  X,
  Search,
  Filter,
  ShieldCheck,
  CheckCircle2,
  UserCheck
} from 'lucide-react';
import {
  downloadGenericPdf,
  downloadRtiPdf,
  translateDocument,
  createLegalDraft,
  updateLegalDraft,
  listLegalDrafts,
  deleteLegalDraft,
  getLawyers,
  requestConsultation,
  LegalDraft,
  LawyerProfile
} from '@/lib/api';
import useCaseStore from '@/store/caseStore';

interface DraftViewerProps {
  title?: string;
  draft?: string;
  lawyerBrief?: string;
  caseId?: string;
  initialDraftId?: string;
}

export default function DraftViewer({
  title = 'Generated Legal Document',
  draft,
  lawyerBrief: propLawyerBrief,
  caseId,
  initialDraftId
}: DraftViewerProps) {
  const storeLawyerBrief = useCaseStore((s) => s.lawyerBrief);
  const activeLawyerBrief = propLawyerBrief || storeLawyerBrief || null;
  const citedPrecedents = useCaseStore((s) => s.citedPrecedents || []);
  const removePrecedentCitation = useCaseStore((s) => s.removePrecedentCitation);

  const [activeTab, setActiveTab] = useState<'draft' | 'lawyer'>('draft');
  const [copied, setCopied] = useState(false);
  const [copiedLawyer, setCopiedLawyer] = useState(false);
  const [downloading, setDownloading] = useState(false);
  const [displayDraft, setDisplayDraft] = useState(draft || '');
  const [translating, setTranslating] = useState(false);
  const [selectedLang, setSelectedLang] = useState('English');

  // Persistence & Edit state
  const [draftId, setDraftId] = useState<string | null>(initialDraftId || null);
  const [draftVersion, setDraftVersion] = useState<number>(1);
  const [draftTitle, setDraftTitle] = useState(title);
  const [isEditing, setIsEditing] = useState(false);
  const [editableContent, setEditableContent] = useState('');
  const [saveStatus, setSaveStatus] = useState<'IDLE' | 'SAVING' | 'SAVED' | 'ERROR'>('IDLE');
  const [lastSavedAt, setLastSavedAt] = useState<Date | null>(null);
  const [saveErrorMsg, setSaveErrorMsg] = useState<string | null>(null);
  const autosaveTimerRef = useRef<NodeJS.Timeout | null>(null);
  const isSavingRef = useRef(false);
  const pendingSaveRef = useRef<{ content: string; title: string } | null>(null);
  const latestVersionRef = useRef(draftVersion);
  const latestDraftIdRef = useRef(draftId);

  useEffect(() => {
    latestVersionRef.current = draftVersion;
  }, [draftVersion]);

  useEffect(() => {
    latestDraftIdRef.current = draftId;
  }, [draftId]);

  // Saved Drafts Drawer
  const [savedDraftsList, setSavedDraftsList] = useState<LegalDraft[]>([]);
  const [isDrawerOpen, setIsDrawerOpen] = useState(false);
  const [loadingDrafts, setLoadingDrafts] = useState(false);

  // Lawyer Connect Modal
  const [isLawyerModalOpen, setIsLawyerModalOpen] = useState(false);
  const [lawyers, setLawyers] = useState<LawyerProfile[]>([]);
  const [loadingLawyers, setLoadingLawyers] = useState(false);
  const [selectedLawyer, setSelectedLawyer] = useState<LawyerProfile | null>(null);
  const [specializationFilter, setSpecializationFilter] = useState('');
  const [consultationSubmitting, setConsultationSubmitting] = useState(false);
  const [consultationSuccess, setConsultationSuccess] = useState<string | null>(null);
  const [consultationForm, setConsultationForm] = useState({
    legal_issue: '',
    description: '',
    preferred_mode: 'ONLINE',
    shareDraftWithLawyer: true
  });

  useEffect(() => {
    setDisplayDraft(draft || '');
    setEditableContent((draft || '').replace(/\*\*(.*?)\*\*/g, '$1').replace(/#{1,6}\s?/g, ''));
    setSelectedLang('English');
  }, [draft]);

  if (!draft && !editableContent) return null;

  const cleanDraftText = editableContent;
  const cleanLawyerBrief = (activeLawyerBrief || '').replace(/\*\*(.*?)\*\*/g, '$1');
  const currentContent = activeTab === 'draft' ? cleanDraftText : (cleanLawyerBrief || cleanDraftText);

  const citationsBlock = citedPrecedents.length > 0 
    ? `\n\n==================================================\nBINDING JUDICIAL PRECEDENTS RELIED UPON:\n` +
      citedPrecedents.map((cp: any, i: number) => `${i + 1}. ${cp.title} [${cp.citation}]\n   Citation: "${cp.how_to_cite}"\n   Ratio: "${cp.ratio}"`).join('\n\n')
    : '';

  // -------------------------------------------------------------
  // Persistent Save Implementation with Optimistic Concurrency
  // -------------------------------------------------------------
  const executeSave = async (contentToSave: string, titleToSave: string) => {
    if (isSavingRef.current) {
      pendingSaveRef.current = { content: contentToSave, title: titleToSave };
      return;
    }
    isSavingRef.current = true;
    setSaveStatus('SAVING');
    setSaveErrorMsg(null);
    try {
      const activeId = latestDraftIdRef.current;
      const activeVer = latestVersionRef.current;
      if (!activeId) {
        // Create new draft
        const created = await createLegalDraft({
          case_id: caseId,
          title: titleToSave,
          document_type: caseId && caseId.includes('RTI') ? 'RTI' : 'LEGAL_PETITION',
          draft_content: contentToSave,
          lawyer_brief: activeLawyerBrief || undefined
        });
        setDraftId(created.id);
        setDraftVersion(created.version || 1);
        latestDraftIdRef.current = created.id;
        latestVersionRef.current = created.version || 1;
        setSaveStatus('SAVED');
        setLastSavedAt(new Date());
      } else {
        // Update existing draft with expected_version
        const updated = await updateLegalDraft(activeId, {
          title: titleToSave,
          draft_content: contentToSave,
          lawyer_brief: activeLawyerBrief || undefined,
          expected_version: activeVer
        });
        setDraftVersion(updated.version);
        latestVersionRef.current = updated.version;
        setSaveStatus('SAVED');
        setLastSavedAt(new Date());
      }
    } catch (err: any) {
      console.error('Failed to save draft:', err);
      setSaveStatus('ERROR');
      if (err?.response?.status === 409) {
        setSaveErrorMsg('Version conflict: Draft was updated elsewhere. Unsaved edits remain in editor.');
      } else {
        setSaveErrorMsg(err?.response?.data?.detail || err?.message || 'Save failed. Unsaved edits remain in editor.');
      }
    } finally {
      isSavingRef.current = false;
      if (pendingSaveRef.current) {
        const next = pendingSaveRef.current;
        pendingSaveRef.current = null;
        executeSave(next.content, next.title);
      }
    }
  };

  const handleManualSave = () => {
    if (autosaveTimerRef.current) clearTimeout(autosaveTimerRef.current);
    executeSave(editableContent, draftTitle);
  };

  const handleContentChange = (newText: string) => {
    setEditableContent(newText);
    setSaveStatus('SAVING');

    // Debounced autosave (1500ms)
    if (autosaveTimerRef.current) clearTimeout(autosaveTimerRef.current);
    autosaveTimerRef.current = setTimeout(() => {
      executeSave(newText, draftTitle);
    }, 1500);
  };

  // -------------------------------------------------------------
  // Saved Drafts Management
  // -------------------------------------------------------------
  const handleOpenSavedDrafts = async () => {
    setIsDrawerOpen(true);
    setLoadingDrafts(true);
    try {
      const res = await listLegalDrafts();
      setSavedDraftsList(res.drafts || []);
    } catch (err) {
      console.error('Failed to load saved drafts:', err);
    } finally {
      setLoadingDrafts(false);
    }
  };

  const handleSelectSavedDraft = (d: LegalDraft) => {
    setDraftId(d.id);
    setDraftVersion(d.version);
    setDraftTitle(d.title);
    setEditableContent(d.draft_content);
    setDisplayDraft(d.draft_content);
    setIsDrawerOpen(false);
    setSaveStatus('SAVED');
    setLastSavedAt(new Date(d.updated_at));
  };

  const handleDeleteDraft = async (dId: string) => {
    if (!confirm('Are you sure you want to delete this saved draft?')) return;
    try {
      await deleteLegalDraft(dId);
      setSavedDraftsList((prev) => prev.filter((d) => d.id !== dId));
      if (draftId === dId) {
        setDraftId(null);
        setDraftVersion(1);
        setSaveStatus('IDLE');
      }
    } catch (err) {
      console.error('Failed to delete draft:', err);
      alert('Failed to delete draft.');
    }
  };

  // -------------------------------------------------------------
  // Connect with a Lawyer Workflow
  // -------------------------------------------------------------
  const handleOpenLawyerModal = async () => {
    setIsLawyerModalOpen(true);
    setLoadingLawyers(true);
    setConsultationSuccess(null);
    setSelectedLawyer(null);
    setConsultationForm({
      legal_issue: `Representation regarding ${draftTitle}`,
      description: `I have prepared a statutory legal draft and seek legal counsel review.`,
      preferred_mode: 'ONLINE',
      shareDraftWithLawyer: true
    });

    try {
      const res = await getLawyers({ limit: 12 });
      setLawyers(res.lawyers || []);
    } catch (err) {
      console.error('Failed to fetch lawyers:', err);
    } finally {
      setLoadingLawyers(false);
    }
  };

  const handleSelectLawyerForConsultation = (lawyer: LawyerProfile) => {
    setSelectedLawyer(lawyer);
  };

  const handleSubmitConsultationRequest = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!selectedLawyer) return;

    let effectiveDraftId = draftId;
    if (!effectiveDraftId) {
      try {
        const created = await createLegalDraft({
          case_id: caseId,
          title: draftTitle,
          document_type: caseId && caseId.includes('RTI') ? 'RTI' : 'LEGAL_PETITION',
          draft_content: editableContent,
          lawyer_brief: activeLawyerBrief || undefined
        });
        effectiveDraftId = created.id;
        setDraftId(created.id);
        setDraftVersion(created.version || 1);
      } catch (saveErr) {
        console.error('Autosave before consultation failed:', saveErr);
      }
    }

    let cleanCaseId = caseId && typeof caseId === 'string' ? caseId.trim() : undefined;
    if (cleanCaseId && (cleanCaseId.startsWith('CR-GRV') || cleanCaseId.startsWith('DRAFT'))) {
      cleanCaseId = undefined;
    }

    setConsultationSubmitting(true);
    try {
      await requestConsultation({
        lawyer_user_id: selectedLawyer.id,
        case_id: cleanCaseId,
        legal_issue: consultationForm.legal_issue,
        description: consultationForm.description,
        preferred_mode: consultationForm.preferred_mode,
        draft_id: consultationForm.shareDraftWithLawyer && effectiveDraftId ? effectiveDraftId : undefined,
        include_draft: consultationForm.shareDraftWithLawyer
      });

      setConsultationSuccess(
        `Consultation request successfully submitted to Advocate ${selectedLawyer.full_name}. ${
          consultationForm.shareDraftWithLawyer
            ? 'Your legal draft has been shared with the selected lawyer for consultation review.'
            : 'Draft sharing was withheld as requested.'
        }`
      );
      setTimeout(() => {
        setIsLawyerModalOpen(false);
        setConsultationSuccess(null);
      }, 7000);
    } catch (err: any) {
      console.error('Failed to submit consultation request:', err);
      alert(err?.response?.data?.detail || err?.message || 'Failed to submit consultation request.');
    } finally {
      setConsultationSubmitting(false);
    }
  };

  const handleCopy = () => {
    navigator.clipboard.writeText(cleanDraftText + citationsBlock);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  const handleCopyForLawyer = () => {
    const textToCopy = cleanLawyerBrief 
      ? `${cleanLawyerBrief}\n\nATTACHED STATUTORY PETITION DRAFT:\n${cleanDraftText}${citationsBlock}` 
      : `${cleanDraftText}${citationsBlock}`;
    navigator.clipboard.writeText(textToCopy);
    setCopiedLawyer(true);
    setTimeout(() => setCopiedLawyer(false), 2500);
  };

  const handleDownloadPdf = async () => {
    setDownloading(true);
    try {
      let blob;
      let filename = `${caseId ? `Application_${caseId}` : 'Legal_Notice'}.pdf`;

      if (selectedLang !== 'English' || activeTab === 'lawyer') {
        blob = new Blob([currentContent], { type: 'text/plain;charset=utf-8' });
        filename = `${caseId ? `Case_${caseId}` : 'Legal_Case'}_${activeTab === 'lawyer' ? 'Lawyer_Brief' : selectedLang}.txt`;
      } else {
        if (caseId && title.toLowerCase().includes('rti')) {
          blob = await downloadRtiPdf(caseId);
        } else {
          blob = await downloadGenericPdf(draftTitle, cleanDraftText);
        }
        blob = new Blob([blob], { type: 'application/pdf' });
      }
      
      const url = URL.createObjectURL(blob);
      const link = document.createElement('a');
      link.href = url;
      link.download = filename;
      document.body.appendChild(link);
      link.click();
      
      setTimeout(() => {
        if (link.parentNode) link.parentNode.removeChild(link);
        URL.revokeObjectURL(url);
      }, 5000);
    } catch (err) {
      console.error('Failed to download document:', err);
      alert('Failed to generate document file. Please try again.');
    } finally {
      setDownloading(false);
    }
  };

  const handlePrint = () => {
    const iframe = document.createElement('iframe');
    iframe.style.position = 'fixed';
    iframe.style.right = '0';
    iframe.style.bottom = '0';
    iframe.style.width = '0';
    iframe.style.height = '0';
    iframe.style.border = '0';
    document.body.appendChild(iframe);
    
    const content = `
      <html>
        <head>
          <title>${draftTitle} - ${activeTab === 'lawyer' ? 'Lawyer Brief' : selectedLang}</title>
          <style>
            body { font-family: Arial, sans-serif; font-size: 14px; line-height: 1.6; padding: 40px; color: #000; }
            pre { white-space: pre-wrap; font-family: inherit; margin: 0; }
          </style>
        </head>
        <body>
          <h2>${draftTitle} ${activeTab === 'lawyer' ? '(Advocate Case Brief)' : `(${selectedLang})`}</h2>
          <pre>${currentContent.replace(/</g, '&lt;').replace(/>/g, '&gt;')}</pre>
        </body>
      </html>
    `;
    
    if (iframe.contentWindow) {
      iframe.contentWindow.document.open();
      iframe.contentWindow.document.write(content);
      iframe.contentWindow.document.close();
      iframe.contentWindow.focus();
      setTimeout(() => {
        if (iframe.contentWindow) {
          iframe.contentWindow.print();
        }
        setTimeout(() => {
          if (document.body.contains(iframe)) {
            document.body.removeChild(iframe);
          }
        }, 1000);
      }, 250);
    }
  };

  const filteredLawyers = useMemo(() => {
    if (!specializationFilter) return lawyers;
    return lawyers.filter((l) =>
      (l.specializations || []).some((s) => s.toLowerCase().includes(specializationFilter.toLowerCase()))
    );
  }, [lawyers, specializationFilter]);

  return (
    <motion.div
      initial={{ opacity: 0, y: 16 }}
      animate={{ opacity: 1, y: 0 }}
      className="bg-white/95 backdrop-blur-sm border border-slate-300 rounded-3xl overflow-hidden shadow-xl"
    >
      {/* Top Action Bar with Tabs, Persistence Status, and Action Buttons */}
      <div className="flex flex-col md:flex-row items-center justify-between px-5 py-3 border-b border-slate-200 bg-[#F8FAFC] gap-3">
        <div className="flex flex-wrap items-center gap-2">
          {/* Tab 1: Statutory Draft */}
          <button
            type="button"
            onClick={() => setActiveTab('draft')}
            className={`inline-flex items-center gap-1.5 px-3.5 py-1.5 rounded-xl text-xs font-bold transition-all cursor-pointer ${
              activeTab === 'draft'
                ? 'bg-court-maroon text-white shadow-xs'
                : 'bg-white text-slate-700 hover:bg-slate-100 border border-slate-200'
            }`}
          >
            <FileText size={14} />
            <span>Statutory Petition Draft</span>
          </button>

          {/* Tab 2: Lawyer Brief */}
          <button
            type="button"
            onClick={() => setActiveTab('lawyer')}
            className={`inline-flex items-center gap-1.5 px-3.5 py-1.5 rounded-xl text-xs font-bold transition-all cursor-pointer ${
              activeTab === 'lawyer'
                ? 'bg-slate-900 text-white shadow-xs'
                : 'bg-white text-slate-700 hover:bg-slate-100 border border-slate-200'
            }`}
          >
            <Briefcase size={14} className="text-amber-400" />
            <span>Advocate Case Brief</span>
            <span className="text-[10px] px-1.5 py-0.2 rounded bg-amber-400/20 text-amber-800 font-bold ml-0.5">
              Lawyer Ready
            </span>
          </button>

          {/* Persistence Indicators */}
          <div className="flex items-center gap-1.5 ml-2 text-xs font-medium">
            {saveStatus === 'SAVING' && (
              <span className="inline-flex items-center gap-1 text-amber-600 bg-amber-50 px-2 py-0.5 rounded-md border border-amber-200">
                <Loader2 size={12} className="animate-spin" /> Saving...
              </span>
            )}
            {saveStatus === 'SAVED' && (
              <span className="inline-flex items-center gap-1 text-emerald-700 bg-emerald-50 px-2 py-0.5 rounded-md border border-emerald-200">
                <CloudCheck size={12} /> Saved (v{draftVersion})
              </span>
            )}
            {saveStatus === 'ERROR' && (
              <span className="inline-flex items-center gap-1 text-rose-700 bg-rose-50 px-2 py-0.5 rounded-md border border-rose-200">
                <CloudOff size={12} /> Save Failed
              </span>
            )}
          </div>
        </div>

        {/* Action Controls */}
        <div className="flex flex-wrap items-center gap-2 w-full md:w-auto">
          {/* Connect with Lawyer Action Button */}
          <button
            type="button"
            onClick={handleOpenLawyerModal}
            className="inline-flex items-center gap-1.5 px-3.5 py-1.5 rounded-xl text-xs font-bold bg-gradient-to-r from-amber-600 to-amber-700 hover:from-amber-700 hover:to-amber-800 text-white shadow-sm transition cursor-pointer"
            title="Browse verified advocates and request a consultation with this draft"
          >
            <Scale size={14} className="text-amber-200" />
            <span>Connect with a Lawyer</span>
          </button>

          {/* Save Draft Button */}
          <button
            type="button"
            onClick={handleManualSave}
            disabled={saveStatus === 'SAVING'}
            className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-xl text-xs font-bold bg-white border border-slate-200 text-slate-700 hover:bg-slate-50 transition cursor-pointer"
            title="Explicitly save draft to your secure database profile"
          >
            <Save size={13} className="text-court-maroon" />
            <span>Save Draft</span>
          </button>

          {/* Saved Drafts Browser */}
          <button
            type="button"
            onClick={handleOpenSavedDrafts}
            className="inline-flex items-center gap-1.5 px-2.5 py-1.5 rounded-xl text-xs font-bold bg-white border border-slate-200 text-slate-600 hover:bg-slate-50 transition cursor-pointer"
            title="Browse your saved legal drafts"
          >
            <FolderOpen size={13} />
            <span className="hidden sm:inline">My Drafts</span>
          </button>

          {/* Copy, Download, Print Controls */}
          <div className="flex items-center gap-1.5">
            <button
              onClick={handleCopy}
              className="btn-ghost text-xs py-1.5 px-3 gap-1.5 bg-white border border-slate-200 text-slate-600 hover:text-ashoka-navy hover:bg-slate-50 cursor-pointer"
            >
              {copied ? <><CheckCheck size={13} className="text-emerald-500" /> Copied</> : <><Copy size={13} /> Copy</>}
            </button>
            <button
              onClick={handleDownloadPdf}
              disabled={downloading}
              className="btn-ghost text-xs py-1.5 px-3 gap-1.5 bg-white border border-slate-200 text-slate-600 hover:text-ashoka-navy hover:bg-slate-50 disabled:opacity-50 cursor-pointer"
            >
              {downloading ? <><Loader2 size={13} className="animate-spin" /> Gen...</> : <><Download size={13} /> PDF</>}
            </button>
            <button
              onClick={handlePrint}
              className="btn-ghost text-xs py-1.5 px-2.5 gap-1.5 bg-white border border-slate-200 text-slate-600 hover:bg-slate-50 cursor-pointer"
            >
              <Printer size={13} />
            </button>
          </div>
        </div>
      </div>

      {/* Editor & Content Area */}
      <div className="p-5 sm:p-6 space-y-4">
        {/* Title & Edit Toggle Bar */}
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2 pb-2 border-b border-slate-100">
          <div className="flex items-center gap-2 flex-1">
            <input
              type="text"
              value={draftTitle}
              onChange={(e) => {
                setDraftTitle(e.target.value);
                if (autosaveTimerRef.current) clearTimeout(autosaveTimerRef.current);
                autosaveTimerRef.current = setTimeout(() => {
                  executeSave(editableContent, e.target.value);
                }, 1500);
              }}
              className="text-sm font-bold text-slate-900 bg-transparent border-b border-transparent hover:border-slate-300 focus:border-court-maroon focus:outline-none px-1 py-0.5 w-full max-w-md transition"
              placeholder="Draft Title"
            />
          </div>

          <div className="flex items-center gap-2">
            <button
              type="button"
              onClick={() => setIsEditing(!isEditing)}
              className={`text-xs font-bold px-3 py-1 rounded-lg border transition cursor-pointer flex items-center gap-1 ${
                isEditing
                  ? 'bg-amber-50 text-amber-900 border-amber-300'
                  : 'bg-white text-slate-600 border-slate-200 hover:bg-slate-50'
              }`}
            >
              <Edit3 size={12} />
              <span>{isEditing ? 'Viewing Mode' : 'Edit Mode'}</span>
            </button>
          </div>
        </div>

        {/* Content Box */}
        <div className="relative bg-[#F8FAFC] border border-slate-200 rounded-2xl p-5 sm:p-6 shadow-inner min-h-[320px] max-h-[560px] overflow-y-auto">
          {isEditing && activeTab === 'draft' ? (
            <textarea
              value={editableContent}
              onChange={(e) => handleContentChange(e.target.value)}
              className="w-full h-full min-h-[300px] bg-transparent text-xs sm:text-sm text-ashoka-navy font-mono font-medium leading-relaxed focus:outline-none resize-none"
              placeholder="Edit your petition draft here..."
            />
          ) : (
            <pre className="text-xs sm:text-sm text-ashoka-navy font-mono font-medium leading-relaxed whitespace-pre-wrap break-words">
              {currentContent}
            </pre>
          )}
        </div>

        {/* Cited Judicial Precedents Box */}
        {citedPrecedents.length > 0 && (
          <div className="p-4 sm:p-5 bg-amber-50/70 border border-amber-200/80 rounded-2xl text-left">
            <div className="flex items-center justify-between mb-3">
              <span className="text-xs font-black text-amber-950 uppercase tracking-wider flex items-center gap-1.5">
                <Scale size={14} className="text-court-maroon" />
                <span>Binding Judicial Precedents Relied Upon ({citedPrecedents.length}):</span>
              </span>
              <span className="text-[11px] text-amber-800 font-bold bg-amber-100 px-2 py-0.5 rounded-md border border-amber-300">
                Auto-Attached to Petition
              </span>
            </div>

            <div className="space-y-2.5">
              {citedPrecedents.map((cp: any, idx: number) => (
                <div key={cp.id || idx} className="bg-white/90 p-3 rounded-xl border border-amber-200/60 shadow-2xs">
                  <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-1 mb-1">
                    <span className="text-xs font-black text-ashoka-navy">
                      {idx + 1}. {cp.title}
                    </span>
                    <span className="text-[10px] font-mono font-bold text-rose-800 bg-rose-50 px-2 py-0.5 rounded">
                      {cp.citation}
                    </span>
                  </div>
                  <p className="text-[11px] text-slate-700 font-mono leading-relaxed">
                    &quot;{cp.how_to_cite}&quot;
                  </p>
                </div>
              ))}
            </div>
          </div>
        )}
      </div>

      {/* ============================================================= */}
      {/* Modal: Connect with a Lawyer & Consultation Request Flow     */}
      {/* ============================================================= */}
      <AnimatePresence>
        {isLawyerModalOpen && (
          <div className="fixed inset-0 z-50 bg-slate-900/60 backdrop-blur-sm flex items-center justify-center p-4">
            <motion.div
              initial={{ opacity: 0, scale: 0.95 }}
              animate={{ opacity: 1, scale: 1 }}
              exit={{ opacity: 0, scale: 0.95 }}
              className="bg-white rounded-3xl max-w-2xl w-full p-6 shadow-2xl border border-slate-200 max-h-[90vh] overflow-y-auto space-y-5"
            >
              <div className="flex items-center justify-between border-b border-slate-100 pb-3">
                <div className="flex items-center gap-2">
                  <Scale size={20} className="text-court-maroon" />
                  <h3 className="font-bold text-base text-slate-900">
                    Connect with a Verified Advocate
                  </h3>
                </div>
                <button
                  type="button"
                  onClick={() => setIsLawyerModalOpen(false)}
                  className="p-1 rounded-lg text-slate-400 hover:text-slate-600 hover:bg-slate-100"
                >
                  <X size={18} />
                </button>
              </div>

              {consultationSuccess ? (
                <div className="p-5 bg-emerald-50 border border-emerald-200 rounded-2xl text-emerald-900 space-y-3">
                  <div className="flex items-center gap-2 font-bold text-sm">
                    <CheckCircle2 size={18} className="text-emerald-600" />
                    <span>Consultation Request Registered!</span>
                  </div>
                  <p className="text-xs leading-relaxed">{consultationSuccess}</p>
                  <div className="pt-2 flex items-center gap-2.5">
                    <Link
                      href="/dashboard/consultations"
                      className="px-4 py-2 bg-court-maroon hover:bg-rose-700 text-white rounded-xl text-xs font-bold transition-all shadow-sm flex items-center gap-1.5 cursor-pointer"
                    >
                      <span>Track in Consultations</span>
                      <ArrowRight size={13} />
                    </Link>
                    <button
                      type="button"
                      onClick={() => {
                        setIsLawyerModalOpen(false);
                        setConsultationSuccess(null);
                      }}
                      className="px-3 py-2 text-xs text-slate-600 hover:text-slate-900 font-medium cursor-pointer"
                    >
                      Close
                    </button>
                  </div>
                </div>
              ) : selectedLawyer ? (
                // Step 2: Form to confirm consultation & explicit draft sharing consent
                <form onSubmit={handleSubmitConsultationRequest} className="space-y-4">
                  <div className="p-4 bg-slate-50 border border-slate-200 rounded-2xl flex items-center justify-between">
                    <div>
                      <div className="flex items-center gap-2">
                        <span className="font-bold text-sm text-slate-900">{selectedLawyer.full_name}</span>
                        <span className="text-[10px] font-bold text-emerald-800 bg-emerald-100 px-2 py-0.5 rounded-full">
                          Verified Counsel
                        </span>
                      </div>
                      <span className="text-xs text-slate-500">
                        {selectedLawyer.bar_council} | {selectedLawyer.years_of_practice} yrs practice
                      </span>
                    </div>
                    <button
                      type="button"
                      onClick={() => setSelectedLawyer(null)}
                      className="text-xs text-court-maroon font-bold underline"
                    >
                      Change Advocate
                    </button>
                  </div>

                  <div>
                    <label className="block text-xs font-bold text-slate-700 mb-1">
                      Legal Issue Subject
                    </label>
                    <input
                      type="text"
                      required
                      value={consultationForm.legal_issue}
                      onChange={(e) => setConsultationForm({ ...consultationForm, legal_issue: e.target.value })}
                      className="w-full px-3.5 py-2 text-xs border border-slate-300 rounded-xl focus:outline-none focus:border-court-maroon"
                    />
                  </div>

                  <div>
                    <label className="block text-xs font-bold text-slate-700 mb-1">
                      Consultation Brief / Questions for Counsel
                    </label>
                    <textarea
                      required
                      rows={3}
                      value={consultationForm.description}
                      onChange={(e) => setConsultationForm({ ...consultationForm, description: e.target.value })}
                      className="w-full px-3.5 py-2 text-xs border border-slate-300 rounded-xl focus:outline-none focus:border-court-maroon"
                    />
                  </div>

                  <div>
                    <label className="block text-xs font-bold text-slate-700 mb-1">
                      Preferred Consultation Mode
                    </label>
                    <select
                      value={consultationForm.preferred_mode}
                      onChange={(e) => setConsultationForm({ ...consultationForm, preferred_mode: e.target.value })}
                      className="w-full px-3.5 py-2 text-xs border border-slate-300 rounded-xl focus:outline-none focus:border-court-maroon"
                    >
                      <option value="ONLINE">Online Video / Chat Consultation</option>
                      <option value="PHONE">Telephone Call</option>
                      <option value="IN_PERSON">In-Person Meeting</option>
                    </select>
                  </div>

                  {/* Explicit Draft Sharing Consent Checkbox */}
                  <div className="p-4 bg-amber-50 border border-amber-200 rounded-2xl space-y-2">
                    <label className="flex items-start gap-3 cursor-pointer">
                      <input
                        type="checkbox"
                        checked={consultationForm.shareDraftWithLawyer}
                        onChange={(e) => setConsultationForm({ ...consultationForm, shareDraftWithLawyer: e.target.checked })}
                        className="mt-1 h-4 w-4 rounded border-slate-300 text-court-maroon focus:ring-court-maroon"
                      />
                      <span className="text-xs text-amber-950 leading-relaxed">
                        <strong>Explicit Sharing Consent:</strong> I explicitly consent to sharing this selected legal draft and the associated information with the chosen lawyer for the purpose of my consultation request. Access is limited to the selected sharing scope and may be revoked.
                      </span>
                    </label>
                    <p className="text-[11px] text-amber-800 ml-7">
                      Note: The advocate will only receive access to this draft if this consent box is checked.
                    </p>
                  </div>

                  <div className="flex items-center justify-end gap-2 pt-2">
                    <button
                      type="button"
                      onClick={() => setSelectedLawyer(null)}
                      className="px-4 py-2 rounded-xl text-xs font-bold text-slate-600 hover:bg-slate-100"
                    >
                      Back
                    </button>
                    <button
                      type="submit"
                      disabled={consultationSubmitting}
                      className="px-5 py-2 rounded-xl bg-court-maroon hover:bg-rose-700 text-white font-bold text-xs shadow-sm flex items-center gap-1.5 disabled:opacity-50"
                    >
                      {consultationSubmitting ? <Loader2 size={13} className="animate-spin" /> : <Check size={13} />}
                      <span>{consultationSubmitting ? 'Submitting...' : 'Submit Consultation Request'}</span>
                    </button>
                  </div>
                </form>
              ) : (
                // Step 1: Browse Verified Lawyers Directory
                <div className="space-y-4">
                  <div className="flex items-center gap-2">
                    <input
                      type="text"
                      placeholder="Filter by specialization (e.g. RTI, Consumer, Cyber)..."
                      value={specializationFilter}
                      onChange={(e) => setSpecializationFilter(e.target.value)}
                      className="w-full px-3.5 py-2 text-xs border border-slate-300 rounded-xl focus:outline-none focus:border-court-maroon"
                    />
                  </div>

                  {loadingLawyers ? (
                    <div className="py-12 text-center text-xs text-slate-500">
                      <Loader2 size={20} className="animate-spin mx-auto mb-2 text-court-maroon" />
                      Loading verified advocates...
                    </div>
                  ) : filteredLawyers.length === 0 ? (
                    <div className="py-8 text-center text-xs text-slate-500">
                      No advocates found matching filter criteria.
                    </div>
                  ) : (
                    <div className="grid grid-cols-1 md:grid-cols-2 gap-3 max-h-[380px] overflow-y-auto pr-1">
                      {filteredLawyers.map((l) => (
                        <div
                          key={l.id}
                          className="p-4 rounded-2xl border border-slate-200 hover:border-court-maroon hover:shadow-sm transition bg-white space-y-2 flex flex-col justify-between"
                        >
                          <div>
                            <div className="flex items-center justify-between">
                              <span className="font-bold text-xs text-slate-900">{l.full_name}</span>
                              <span className="text-[10px] text-slate-400 font-mono">
                                {l.years_of_practice} yrs
                              </span>
                            </div>
                            <span className="text-[11px] text-slate-500 block">{l.bar_council}</span>

                            <div className="flex flex-wrap gap-1 mt-2">
                              {(l.specializations || []).slice(0, 3).map((s, idx) => (
                                <span key={idx} className="text-[10px] bg-slate-100 text-slate-700 px-2 py-0.5 rounded-md">
                                  {s}
                                </span>
                              ))}
                            </div>
                          </div>

                          <button
                            type="button"
                            onClick={() => handleSelectLawyerForConsultation(l)}
                            className="mt-3 w-full py-1.5 rounded-xl bg-slate-900 hover:bg-court-maroon text-white font-bold text-xs transition cursor-pointer"
                          >
                            Consult Advocate
                          </button>
                        </div>
                      ))}
                    </div>
                  )}
                </div>
              )}
            </motion.div>
          </div>
        )}
      </AnimatePresence>

      {/* ============================================================= */}
      {/* Drawer: My Saved Legal Drafts                                */}
      {/* ============================================================= */}
      <AnimatePresence>
        {isDrawerOpen && (
          <div className="fixed inset-0 z-50 bg-slate-900/40 backdrop-blur-xs flex justify-end">
            <motion.div
              initial={{ x: '100%' }}
              animate={{ x: 0 }}
              exit={{ x: '100%' }}
              transition={{ type: 'spring', damping: 25, stiffness: 200 }}
              className="bg-white w-full max-w-md h-full shadow-2xl p-6 flex flex-col justify-between"
            >
              <div className="space-y-4">
                <div className="flex items-center justify-between border-b border-slate-100 pb-3">
                  <div className="flex items-center gap-2">
                    <FolderOpen size={18} className="text-court-maroon" />
                    <h3 className="font-bold text-sm text-slate-900">My Saved Legal Drafts</h3>
                  </div>
                  <button
                    type="button"
                    onClick={() => setIsDrawerOpen(false)}
                    className="p-1 rounded-lg text-slate-400 hover:text-slate-600"
                  >
                    <X size={18} />
                  </button>
                </div>

                {loadingDrafts ? (
                  <div className="py-12 text-center text-xs text-slate-500">
                    <Loader2 size={18} className="animate-spin mx-auto mb-2 text-court-maroon" />
                    Loading your saved drafts...
                  </div>
                ) : savedDraftsList.length === 0 ? (
                  <div className="py-12 text-center text-xs text-slate-500">
                    No saved drafts yet. Click &quot;Save Draft&quot; to preserve your current work.
                  </div>
                ) : (
                  <div className="space-y-2.5 max-h-[75vh] overflow-y-auto pr-1">
                    {savedDraftsList.map((d) => (
                      <div
                        key={d.id}
                        className={`p-3.5 rounded-2xl border transition ${
                          draftId === d.id
                            ? 'bg-rose-50/70 border-court-maroon'
                            : 'bg-slate-50 border-slate-200 hover:border-slate-300'
                        }`}
                      >
                        <div className="flex items-start justify-between gap-2">
                          <button
                            type="button"
                            onClick={() => handleSelectSavedDraft(d)}
                            className="text-left flex-1"
                          >
                            <h4 className="font-bold text-xs text-slate-900 hover:text-court-maroon transition">
                              {d.title}
                            </h4>
                            <span className="text-[10px] text-slate-400 font-mono block mt-0.5">
                              v{d.version} | {new Date(d.updated_at).toLocaleDateString()}
                            </span>
                          </button>
                          <button
                            type="button"
                            onClick={() => handleDeleteDraft(d.id)}
                            className="text-slate-400 hover:text-rose-600 transition p-1"
                            title="Delete draft"
                          >
                            <Trash2 size={13} />
                          </button>
                        </div>
                      </div>
                    ))}
                  </div>
                )}
              </div>

              <div className="pt-4 border-t border-slate-100 text-center">
                <button
                  type="button"
                  onClick={() => setIsDrawerOpen(false)}
                  className="w-full py-2 rounded-xl bg-slate-100 text-slate-700 text-xs font-bold hover:bg-slate-200 transition"
                >
                  Close
                </button>
              </div>
            </motion.div>
          </div>
        )}
      </AnimatePresence>
    </motion.div>
  );
}
