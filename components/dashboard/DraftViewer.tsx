'use client';

import { useState, useEffect } from 'react'
import { motion } from 'framer-motion'
import { Copy, Download, CheckCheck, FileText, Printer, Loader2, Globe, Scale, Briefcase, Check } from 'lucide-react'
import { downloadGenericPdf, downloadRtiPdf, translateDocument } from '@/lib/api'
import useCaseStore from '@/store/caseStore'

export default function DraftViewer({ title = 'Generated Document', draft, lawyerBrief: propLawyerBrief, caseId }: any) {
  const storeLawyerBrief = useCaseStore((s) => s.lawyerBrief);
  const activeLawyerBrief = propLawyerBrief || storeLawyerBrief || null;
  const citedPrecedents = useCaseStore((s) => s.citedPrecedents || []);
  const removePrecedentCitation = useCaseStore((s) => s.removePrecedentCitation);

  const [activeTab, setActiveTab] = useState<'draft' | 'lawyer'>('draft');
  const [copied, setCopied] = useState(false)
  const [copiedLawyer, setCopiedLawyer] = useState(false)
  const [downloading, setDownloading] = useState(false)
  const [displayDraft, setDisplayDraft] = useState(draft)
  const [translating, setTranslating] = useState(false)
  const [selectedLang, setSelectedLang] = useState('English')

  useEffect(() => {
    setDisplayDraft(draft);
    setSelectedLang('English');
  }, [draft]);

  if (!draft) return null

  const cleanDraftText = (displayDraft || '').replace(/\*\*(.*?)\*\*/g, '$1').replace(/#{1,6}\s?/g, '');
  const cleanLawyerBrief = (activeLawyerBrief || '').replace(/\*\*(.*?)\*\*/g, '$1');

  const currentContent = activeTab === 'draft' ? cleanDraftText : (cleanLawyerBrief || cleanDraftText);

  const citationsBlock = citedPrecedents.length > 0 
    ? `\n\n==================================================\nBINDING JUDICIAL PRECEDENTS RELIED UPON:\n` +
      citedPrecedents.map((cp: any, i: number) => `${i + 1}. ${cp.title} [${cp.citation}]\n   Citation: "${cp.how_to_cite}"\n   Ratio: "${cp.ratio}"`).join('\n\n')
    : '';

  const handleCopy = () => {
    navigator.clipboard.writeText(cleanDraftText + citationsBlock)
    setCopied(true)
    setTimeout(() => setCopied(false), 2000)
  }

  const handleCopyForLawyer = () => {
    const textToCopy = cleanLawyerBrief 
      ? `${cleanLawyerBrief}\n\nATTACHED STATUTORY PETITION DRAFT:\n${cleanDraftText}${citationsBlock}` 
      : `${cleanDraftText}${citationsBlock}`;
    navigator.clipboard.writeText(textToCopy);
    setCopiedLawyer(true);
    setTimeout(() => setCopiedLawyer(false), 2500);
  };

  const handleDownloadPdf = async () => {
    setDownloading(true)
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
          blob = await downloadGenericPdf(title, cleanDraftText);
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
  }

  const handlePrint = () => {
    const iframe = document.createElement('iframe')
    iframe.style.position = 'fixed'
    iframe.style.right = '0'
    iframe.style.bottom = '0'
    iframe.style.width = '0'
    iframe.style.height = '0'
    iframe.style.border = '0'
    document.body.appendChild(iframe)
    
    const content = `
      <html>
        <head>
          <title>${title} - ${activeTab === 'lawyer' ? 'Lawyer Brief' : selectedLang}</title>
          <style>
            body { font-family: Arial, sans-serif; font-size: 14px; line-height: 1.6; padding: 40px; color: #000; }
            pre { white-space: pre-wrap; font-family: inherit; margin: 0; }
          </style>
        </head>
        <body>
          <h2>${title} ${activeTab === 'lawyer' ? '(Advocate Case Brief)' : `(${selectedLang})`}</h2>
          <pre>${currentContent.replace(/</g, '&lt;').replace(/>/g, '&gt;')}</pre>
        </body>
      </html>
    `
    
    if (iframe.contentWindow) {
      iframe.contentWindow.document.open()
      iframe.contentWindow.document.write(content)
      iframe.contentWindow.document.close()
      
      iframe.contentWindow.focus()
      setTimeout(() => {
        if (iframe.contentWindow) {
          iframe.contentWindow.print()
        }
        setTimeout(() => {
          if (document.body.contains(iframe)) {
            document.body.removeChild(iframe)
          }
        }, 1000)
      }, 250)
    }
  }

  const handleTranslate = async (e: any) => {
    const lang = e.target.value;
    setSelectedLang(lang);
    if (lang === 'English') {
      setDisplayDraft(draft);
      return;
    }
    setTranslating(true);
    try {
      const res = await translateDocument(draft, lang);
      setDisplayDraft(res.translated_text);
    } catch (err) {
      console.error('Translation failed:', err);
      alert('Failed to translate document. Please try again.');
      setSelectedLang('English');
      setDisplayDraft(draft);
    } finally {
      setTranslating(false);
    }
  }

  return (
    <motion.div
      initial={{ opacity: 0, y: 16 }}
      animate={{ opacity: 1, y: 0 }}
      className="bg-white/95 backdrop-blur-sm border border-slate-300 rounded-3xl overflow-hidden shadow-xl"
    >
      {/* Top Header with Document Mode Tabs */}
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

          {caseId && (
            <span className="hidden sm:inline-block text-xs font-mono text-slate-500 bg-white px-2 py-1 rounded border border-slate-200">
              #{caseId}
            </span>
          )}
        </div>
        
        <div className="flex flex-wrap items-center gap-2 w-full md:w-auto">
          {activeTab === 'draft' && (
            <div className="flex items-center gap-1.5 bg-white border border-slate-200 rounded-lg px-2.5 py-1.5 shadow-sm">
              <Globe size={13} className="text-slate-500" />
              <select
                value={selectedLang}
                onChange={handleTranslate}
                disabled={translating}
                className="text-xs font-bold text-slate-600 bg-transparent focus:outline-none cursor-pointer tracking-tight"
              >
                <option value="English">English</option>
                <option value="Hindi">Hindi (हिन्दी)</option>
                <option value="Marathi">Marathi (मराठी)</option>
                <option value="Tamil">Tamil (தமிழ்)</option>
                <option value="Gujarati">Gujarati (ગુજરાતી)</option>
                <option value="Bengali">Bengali (বাংলা)</option>
                <option value="Telugu">Telugu (తెలుగు)</option>
              </select>
            </div>
          )}

          <div className="flex items-center gap-1.5">
            <button
              onClick={handleCopyForLawyer}
              className="btn-ghost flex-1 sm:flex-none text-xs py-1.5 px-3 gap-1.5 bg-gradient-to-r from-slate-900 to-slate-800 text-amber-300 hover:text-white border border-slate-700 shadow-xs cursor-pointer font-bold"
              title="Copy Advocate Brief & Facts to forward to your lawyer"
            >
              {copiedLawyer ? (
                <>
                  <Check size={13} className="text-emerald-400" />
                  <span>Brief Copied!</span>
                </>
              ) : (
                <>
                  <Scale size={13} className="text-amber-400" />
                  <span>Copy for Lawyer</span>
                </>
              )}
            </button>

            <button onClick={handleCopy} className="btn-ghost flex-1 sm:flex-none text-xs py-1.5 px-3 gap-1.5 bg-white border border-slate-200 text-slate-600 hover:text-ashoka-navy hover:bg-slate-50 cursor-pointer">
              {copied ? <><CheckCheck size={13} className="text-emerald-500" /> Copied!</> : <><Copy size={13} /> Copy</>}
            </button>
            <button 
              onClick={handleDownloadPdf} 
              disabled={downloading} 
              className="btn-ghost flex-1 sm:flex-none text-xs py-1.5 px-3 gap-1.5 bg-white border border-slate-200 text-slate-600 hover:text-ashoka-navy hover:bg-slate-50 disabled:opacity-50 cursor-pointer"
            >
              {downloading ? <><Loader2 size={13} className="animate-spin" /> Gen...</> : <><Download size={13} /> {activeTab === 'lawyer' || selectedLang !== 'English' ? 'Text File' : 'PDF'}</>}
            </button>
            <button onClick={handlePrint} className="btn-ghost flex-1 sm:flex-none text-xs py-1.5 px-3 gap-1.5 bg-white border border-slate-200 text-slate-600 hover:text-ashoka-navy hover:bg-slate-50 cursor-pointer">
              <Printer size={13} /> Print
            </button>
          </div>
        </div>
      </div>

      {activeTab === 'lawyer' && (
        <div className="bg-amber-50 border-b border-amber-200 px-5 py-2.5 flex items-center justify-between text-xs text-amber-900">
          <div className="flex items-center gap-2">
            <Scale size={15} className="text-amber-700 shrink-0" />
            <span className="font-medium">
              <strong>Advocate Forwarding Brief:</strong> Structured summary of parties, cause of action, statutory sections, and required evidence to share with your legal counsel.
            </span>
          </div>
          <button
            type="button"
            onClick={handleCopyForLawyer}
            className="px-2.5 py-1 bg-amber-600 hover:bg-amber-700 text-white font-bold rounded-lg transition-colors shrink-0 cursor-pointer"
          >
            {copiedLawyer ? 'Copied' : 'Copy Brief'}
          </button>
        </div>
      )}
      
      <div className="p-5 sm:p-6">
        <div className="relative bg-[#F8FAFC] border border-slate-200 rounded-2xl p-5 sm:p-6 shadow-inner min-h-[300px] max-h-[520px] overflow-y-auto">
          {translating && (
            <div className="absolute inset-0 bg-white/50 backdrop-blur-[1px] flex items-center justify-center z-10 rounded-2xl">
              <div className="flex items-center gap-2 bg-white px-5 py-2.5 rounded-full shadow border border-slate-200">
                <Loader2 size={16} className="animate-spin text-[#FF9933]" />
                <span className="text-xs font-bold text-slate-600">Translating Document...</span>
              </div>
            </div>
          )}
          <pre className="text-xs sm:text-sm text-ashoka-navy font-mono font-medium leading-relaxed whitespace-pre-wrap break-words">
            {currentContent}
          </pre>
        </div>

        {/* Cited Judicial Precedents Box */}
        {citedPrecedents.length > 0 && (
          <div className="mt-5 p-4 sm:p-5 bg-amber-50/70 border border-amber-200/80 rounded-2xl text-left">
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
                <div key={cp.id || idx} className="bg-white/90 p-3.5 rounded-xl border border-amber-200/60 shadow-2xs">
                  <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-1 mb-1">
                    <span className="text-xs font-black text-ashoka-navy">
                      {idx + 1}. {cp.title}
                    </span>
                    <div className="flex items-center gap-2">
                      <span className="text-[10px] font-mono font-bold text-rose-800 bg-rose-50 px-2 py-0.5 rounded">
                        {cp.citation}
                      </span>
                      {removePrecedentCitation && (
                        <button
                          type="button"
                          onClick={() => removePrecedentCitation(cp.id)}
                          className="text-[10px] text-red-600 hover:text-red-800 font-bold underline cursor-pointer"
                        >
                          Remove
                        </button>
                      )}
                    </div>
                  </div>
                  <p className="text-[11px] text-slate-700 font-mono select-all leading-relaxed">
                    &quot;{cp.how_to_cite}&quot;
                  </p>
                </div>
              ))}
            </div>
          </div>
        )}
      </div>
    </motion.div>
  )
}
