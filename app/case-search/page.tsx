'use client';

import React, { useState, useEffect } from 'react';
import Link from 'next/link';
import { 
  Scale, 
  Search, 
  Filter, 
  BookOpen, 
  Sparkles, 
  Copy, 
  Check, 
  ArrowLeft, 
  Building2, 
  X, 
  Loader2, 
  ArrowRight,
  Bookmark,
  Gavel,
  ShieldCheck,
  Calendar,
  ChevronDown,
  ChevronUp,
  Download
} from 'lucide-react';
import Navbar from '@/app/Navbar';
import { searchPrecedents, summarizePrecedent, downloadCaseBriefPdf } from '@/lib/api';
import useCaseStore from '@/store/caseStore';

export default function CaseSearchPage() {
  const { caseId, citedPrecedents, addPrecedentCitation, removePrecedentCitation } = useCaseStore();
  const userProblemFromStore = useCaseStore((s) => s.userProblem || '');
  const [userCaseGrievance, setUserCaseGrievance] = useState(userProblemFromStore);
  const [copiedAdvisorArg, setCopiedAdvisorArg] = useState(false);
  const [downloadingId, setDownloadingId] = useState<string | null>(null);

  const handleDownloadPdf = async (caseIdToDownload: string) => {
    setDownloadingId(caseIdToDownload);
    try {
      const blob = await downloadCaseBriefPdf(caseIdToDownload);
      const url = URL.createObjectURL(new Blob([blob], { type: 'application/pdf' }));
      const a = document.createElement('a');
      a.href = url;
      a.download = `Case_Brief_${caseIdToDownload}.pdf`;
      document.body.appendChild(a);
      a.click();
      setTimeout(() => {
        if (a.parentNode) a.parentNode.removeChild(a);
        URL.revokeObjectURL(url);
      }, 5000);
    } catch (e) {
      console.error('Failed to download case brief PDF', e);
      alert('Failed to generate PDF. Please try again.');
    } finally {
      setDownloadingId(null);
    }
  };

  const [precedents, setPrecedents] = useState<any[]>([]);
  const [expansionData, setExpansionData] = useState<any | null>(null);
  const [searchQuery, setSearchQuery] = useState('');
  const [selectedCategory, setSelectedCategory] = useState('All');
  const [loading, setLoading] = useState(true);

  // AI Summarizer Drawer / Modal State
  const [summarizerOpen, setSummarizerOpen] = useState(false);
  const [activeCase, setActiveCase] = useState<any | null>(null);
  const [customCaseText, setCustomCaseText] = useState('');
  const [summaryData, setSummaryData] = useState<any | null>(null);
  const [summarizing, setSummarizing] = useState(false);
  const [copiedCitation, setCopiedCitation] = useState<string | null>(null);

  const categories = [
    'All',
    'Higher Education & Campus Grievance',
    'Education & Student Rights',
    'Civic Infrastructure & Roads',
    'Consumer Protection & Housing',
    'Public Records & Transparency',
    'Investigation & Police',
    'Digital Rights & Free Speech',
    'Social Security & Pension',
    'Public Healthcare & Medical Rights'
  ];

  useEffect(() => {
    setLoading(true);
    searchPrecedents(searchQuery, selectedCategory)
      .then((data) => {
        setPrecedents(data?.precedents || []);
        setExpansionData(data?.expansion || null);
      })
      .catch((err) => {
        console.error('Failed to search precedents', err);
      })
      .finally(() => setLoading(false));
  }, [searchQuery, selectedCategory]);

  const handleOpenSummarizer = async (caseItem?: any, grievanceOverride?: string) => {
    const activeGrievance = grievanceOverride !== undefined ? grievanceOverride : (userCaseGrievance || userProblemFromStore);
    setActiveCase(caseItem || null);
    setSummaryData(null);
    setSummarizerOpen(true);
    setSummarizing(true);

    try {
      if (caseItem) {
        const res = await summarizePrecedent(caseItem.id, undefined, 'English', activeGrievance);
        setSummaryData(res);
      } else if (customCaseText.trim()) {
        const res = await summarizePrecedent(undefined, customCaseText, 'English', activeGrievance);
        setSummaryData(res);
      }
    } catch (e) {
      console.error('Summarization failed', e);
    } finally {
      setSummarizing(false);
    }
  };

  const handleCustomSummarize = async () => {
    if (!customCaseText.trim()) return;
    setActiveCase(null);
    setSummarizing(true);
    try {
      const activeGrievance = userCaseGrievance || userProblemFromStore;
      const res = await summarizePrecedent(undefined, customCaseText, 'English', activeGrievance);
      setSummaryData(res);
    } catch (e) {
      console.error('Custom summarization failed', e);
    } finally {
      setSummarizing(false);
    }
  };

  const handleCopyCitation = (citation: string, id: string) => {
    navigator.clipboard.writeText(citation);
    setCopiedCitation(id);
    setTimeout(() => setCopiedCitation(null), 2000);
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

          <div className="flex flex-wrap items-center gap-2.5">
            {citedPrecedents && citedPrecedents.length > 0 && (
              <div className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-full bg-emerald-50 border border-emerald-300 text-emerald-900 text-xs font-bold shadow-xs">
                <Check size={13} className="text-emerald-700" />
                <span>{citedPrecedents.length} Cited in #{caseId || 'DRAFT'}</span>
                <Link href="/dashboard" className="text-emerald-800 hover:text-emerald-950 underline ml-1 font-extrabold">
                  View in Draft →
                </Link>
              </div>
            )}

            <button
              onClick={() => {
                setActiveCase(null);
                setCustomCaseText('');
                setSummaryData(null);
                setSummarizerOpen(true);
              }}
              className="inline-flex items-center gap-2 px-3.5 py-1.5 rounded-full bg-gradient-to-r from-court-maroon to-rose-700 hover:from-rose-700 hover:to-rose-800 text-white text-xs font-bold shadow-md cursor-pointer transition-all active:scale-95"
            >
              <Sparkles size={13} className="text-amber-300" />
              <span>AI Summarize Any Judgment</span>
            </button>
          </div>
        </div>

        {/* Hero Section */}
        <div className="text-center max-w-3xl mx-auto mb-10">
          <div className="inline-flex items-center gap-2 px-3.5 py-1.5 rounded-full bg-rose-50 border border-rose-200 text-court-maroon text-xs font-bold mb-4 shadow-xs">
            <BookOpen size={14} />
            <span>Landmark Indian Case Law &amp; Court Hearing Archives</span>
          </div>
          <h1 className="text-3xl sm:text-5xl font-black text-ashoka-navy tracking-tight mb-4">
            Search Case Law &amp; Citations
          </h1>
          <p className="text-sm sm:text-base text-slate-600 font-medium leading-relaxed">
            Examine landmark Supreme Court of India, High Court, and Central Information Commission judgments. Review the exact oral arguments, the orders the judges issued, and copy-paste ready legal citations for your RTI and administrative petitions.
          </p>
        </div>

        {/* Search & Category Filter */}
        <div className="bg-white p-4 sm:p-5 rounded-3xl border border-slate-200 shadow-sm mb-8">
          <div className="flex flex-col md:flex-row items-center gap-4 mb-4">
            <div className="relative w-full">
              <Search className="absolute left-3.5 top-1/2 -translate-y-1/2 text-slate-400" size={16} />
              <input
                type="text"
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                placeholder="Search by legal issue, judge, or statute (e.g. anti-ragging FIR, answer sheet inspection, PWD road DLP, builder delay, 8(1)(j) privacy)..."
                className="w-full pl-10 pr-4 py-3 text-sm bg-slate-50 border border-slate-200 rounded-xl focus:outline-none focus:border-court-maroon focus:ring-2 focus:ring-court-maroon/10 font-medium"
              />
            </div>
          </div>

          <div className="flex items-center gap-2 overflow-x-auto pb-1 scrollbar-none">
            <span className="text-xs text-slate-500 font-bold uppercase shrink-0 flex items-center gap-1 mr-1">
              <Filter size={12} /> Category:
            </span>
            {categories.map((cat) => (
              <button
                key={cat}
                onClick={() => setSelectedCategory(cat)}
                className={`px-3 py-1.5 rounded-xl text-xs font-bold whitespace-nowrap transition-all cursor-pointer ${
                  selectedCategory === cat
                    ? 'bg-court-maroon text-white shadow-sm'
                    : 'bg-slate-100 hover:bg-slate-200 text-slate-700'
                }`}
              >
                {cat}
              </button>
            ))}
          </div>
        </div>

        {/* AI Semantic Intent Recognized Banner */}
        {expansionData?.has_expansion && expansionData?.legal_intent && searchQuery.trim() && (
          <div className="bg-gradient-to-r from-court-maroon/5 via-rose-50 to-amber-50/50 border border-court-maroon/20 rounded-3xl p-4 sm:p-5 mb-6 flex flex-col sm:flex-row sm:items-center justify-between gap-3 shadow-xs">
            <div className="flex items-center gap-3">
              <div className="w-9 h-9 rounded-2xl bg-court-maroon text-white flex items-center justify-center shrink-0 shadow-xs">
                <Sparkles size={18} className="text-amber-300" />
              </div>
              <div>
                <div className="text-[10px] font-black uppercase tracking-wider text-court-maroon flex items-center gap-1.5">
                  <span>AI Semantic Intent Recognized</span>
                </div>
                <div className="text-sm sm:text-base font-black text-ashoka-navy tracking-tight">
                  {expansionData.legal_intent}
                </div>
              </div>
            </div>

            {expansionData.expanded_terms?.length > 0 && (
              <div className="flex flex-wrap items-center gap-1.5 sm:justify-end">
                <span className="text-[11px] font-bold text-slate-500 mr-1">Semantic Concepts:</span>
                {expansionData.expanded_terms.slice(0, 5).map((term: string) => (
                  <span key={term} className="px-2.5 py-1 rounded-xl bg-white border border-slate-200 text-slate-700 text-xs font-semibold shadow-2xs">
                    +{term}
                  </span>
                ))}
              </div>
            )}
          </div>
        )}

        {/* Precedents Listing */}
        {loading ? (
          <div className="space-y-4">
            {[1, 2, 3].map((i) => (
              <div key={i} className="h-64 rounded-3xl bg-slate-100 animate-pulse border border-slate-200" />
            ))}
          </div>
        ) : precedents.length === 0 ? (
          <div className="text-center py-16 bg-white rounded-3xl border border-slate-200">
            <BookOpen size={36} className="mx-auto text-slate-300 mb-3" />
            <h3 className="text-lg font-bold text-slate-700 mb-1">No precedents matched your query</h3>
            <p className="text-xs text-slate-500">Try searching for keywords like &quot;ragging&quot;, &quot;student&quot;, &quot;answer sheet&quot;, &quot;potholes&quot;, or &quot;privacy&quot;.</p>
          </div>
        ) : (
          <div className="space-y-6">
            {precedents.map((item) => (
              <div
                key={item.id}
                className="bg-white rounded-3xl border border-slate-200 hover:border-court-maroon/40 p-6 sm:p-7 shadow-xs hover:shadow-md transition-all text-left"
              >
                {/* Header: Category, Court & Actions */}
                <div className="flex flex-col sm:flex-row sm:items-start justify-between gap-4 mb-4">
                  <div className="space-y-1">
                    <div className="flex flex-wrap items-center gap-2 mb-1.5">
                      <span className="px-2.5 py-0.5 rounded-full text-[11px] font-bold bg-rose-50 text-court-maroon border border-rose-200">
                        {item.category}
                      </span>
                      {item.relevance_score && searchQuery.trim() && (
                        <span className={`px-2.5 py-0.5 rounded-full text-[11px] font-black border flex items-center gap-1 ${
                          item.relevance_score >= 85
                            ? 'bg-emerald-50 text-emerald-800 border-emerald-200'
                            : 'bg-amber-50 text-amber-900 border-amber-200'
                        }`}>
                          <Sparkles size={11} className={item.relevance_score >= 85 ? 'text-emerald-600' : 'text-amber-600'} />
                          <span>{item.relevance_label || `${item.relevance_score}% Match`}</span>
                        </span>
                      )}
                      <span className="text-xs text-slate-400 font-bold">•</span>
                      <span className="text-xs font-bold text-slate-700 flex items-center gap-1">
                        <Building2 size={13} className="text-slate-400" />
                        <span>{item.court}</span>
                      </span>
                      {item.hearing_date && (
                        <>
                          <span className="text-xs text-slate-400 font-bold">•</span>
                          <span className="text-xs font-medium text-slate-500 flex items-center gap-1">
                            <Calendar size={12} className="text-slate-400" />
                            <span>{item.hearing_date}</span>
                          </span>
                        </>
                      )}
                    </div>

                    <h3 className="text-xl sm:text-2xl font-black text-ashoka-navy leading-snug">
                      {item.title}
                    </h3>
                    <p className="text-xs font-mono font-bold text-rose-800">
                      Citation: {item.citation}
                    </p>

                    {item.bench && (
                      <div className="flex items-center gap-1.5 text-xs text-slate-600 font-semibold pt-1">
                        <Scale size={13} className="text-court-maroon shrink-0" />
                        <span>Bench: {item.bench}</span>
                      </div>
                    )}
                  </div>

                  <div className="flex flex-wrap items-center gap-2 shrink-0">
                    {/* Upgrade 2: 1-Click Cite in Active Draft */}
                    {citedPrecedents?.some((c: any) => c.id === item.id) ? (
                      <button
                        onClick={() => removePrecedentCitation(item.id)}
                        className="px-3 py-2 rounded-xl bg-emerald-50 hover:bg-emerald-100 border border-emerald-300 text-emerald-900 text-xs font-bold flex items-center gap-1.5 transition-colors cursor-pointer"
                        title="Click to remove from active case draft"
                      >
                        <Check size={13} className="text-emerald-600" />
                        <span>Cited in Draft ✓</span>
                      </button>
                    ) : (
                      <button
                        onClick={() => addPrecedentCitation(item)}
                        className="px-3.5 py-2 rounded-xl bg-gradient-to-r from-court-maroon via-rose-700 to-court-maroon hover:from-rose-700 hover:to-rose-800 text-white text-xs font-bold flex items-center gap-1.5 transition-all shadow-md active:scale-95 cursor-pointer"
                        title="Embed this landmark judgment into your active petition draft"
                      >
                        <Sparkles size={13} className="text-amber-300" />
                        <span>Cite in Draft</span>
                      </button>
                    )}

                    <button
                      onClick={() => handleCopyCitation(item.how_to_cite, item.id)}
                      className="px-3 py-2 rounded-xl bg-slate-100 hover:bg-slate-200 text-slate-700 text-xs font-bold flex items-center gap-1.5 transition-colors cursor-pointer"
                      title="Copy citation snippet"
                    >
                      {copiedCitation === item.id ? <Check size={13} className="text-emerald-600" /> : <Copy size={13} />}
                      <span>{copiedCitation === item.id ? 'Copied!' : 'Copy Citation'}</span>
                    </button>

                    <button
                      onClick={() => handleOpenSummarizer(item)}
                      className="px-3 py-2 rounded-xl bg-white border border-slate-300 hover:bg-slate-50 text-slate-700 text-xs font-bold flex items-center gap-1.5 shadow-2xs transition-all cursor-pointer"
                    >
                      <Sparkles size={13} className="text-amber-500" />
                      <span>AI Summarize</span>
                    </button>

                    <button
                      onClick={() => handleDownloadPdf(item.id)}
                      disabled={downloadingId === item.id}
                      className="px-3 py-2 rounded-xl bg-slate-100 hover:bg-slate-200 text-slate-700 text-xs font-bold flex items-center gap-1.5 transition-colors cursor-pointer disabled:opacity-50"
                      title="Download Official 1-Page Case Brief PDF"
                    >
                      {downloadingId === item.id ? (
                        <Loader2 size={13} className="animate-spin text-court-maroon" />
                      ) : (
                        <Download size={13} className="text-slate-600" />
                      )}
                      <span>{downloadingId === item.id ? 'PDF...' : 'Brief PDF'}</span>
                    </button>
                  </div>
                </div>

                {/* Dispute Facts & Background */}
                {item.facts && (
                  <div className="mb-4 bg-slate-50/70 p-3.5 rounded-2xl border border-slate-100">
                    <span className="block text-[10px] font-bold uppercase tracking-wider text-slate-500 mb-1">
                      Dispute Background &amp; Core Facts:
                    </span>
                    <p className="text-xs sm:text-sm text-slate-700 font-medium leading-relaxed">
                      {item.facts}
                    </p>
                  </div>
                )}

                {/* STRUCTURED: The Hearing That Court Gave & Operative Orders */}
                {item.court_hearing_and_directions && (
                  <div className="bg-rose-50/70 border border-rose-200/80 rounded-2xl p-4 sm:p-5 mb-4">
                    <span className="block text-[11px] font-black uppercase tracking-wider text-court-maroon mb-2 flex items-center gap-1.5">
                      <Gavel size={15} className="text-court-maroon shrink-0" />
                      <span>The Hearing &amp; Operative Orders the Court Gave:</span>
                    </span>
                    <div className="text-xs sm:text-sm font-medium text-slate-800 leading-relaxed whitespace-pre-line">
                      {item.court_hearing_and_directions}
                    </div>
                  </div>
                )}

                {/* Core Legal Ratio */}
                <div className="bg-slate-50 rounded-2xl p-4 mb-4 border border-slate-200">
                  <span className="block text-[10px] font-bold uppercase tracking-wider text-slate-500 mb-1">
                    Operative Legal Ratio (Ratio Decidendi):
                  </span>
                  <p className="text-sm font-semibold text-slate-800 leading-relaxed">
                    &quot;{item.key_ratio}&quot;
                  </p>
                </div>

                {/* How to Cite in Your Case */}
                <div className="bg-amber-50/70 border border-amber-200 rounded-2xl p-4 mb-4">
                  <span className="block text-[10px] font-bold uppercase tracking-wider text-amber-900 mb-1 flex items-center gap-1">
                    <Bookmark size={12} className="text-amber-700" />
                    How to cite this in your RTI / Grievance:
                  </span>
                  <p className="text-xs text-amber-950 font-medium leading-relaxed font-mono select-all">
                    {item.how_to_cite}
                  </p>
                </div>

                {/* Citizen Action Takeaway */}
                {item.citizen_action_takeaway && (
                  <div className="bg-emerald-50/60 border border-emerald-200/70 rounded-2xl p-3.5 mb-4">
                    <span className="block text-[10px] font-bold uppercase tracking-wider text-emerald-900 mb-1 flex items-center gap-1">
                      <ShieldCheck size={12} className="text-emerald-700" />
                      Citizen Action Takeaway:
                    </span>
                    <p className="text-xs text-emerald-950 font-semibold leading-relaxed">
                      {item.citizen_action_takeaway}
                    </p>
                  </div>
                )}

                {/* Footer tags and sections */}
                <div className="flex flex-wrap items-center justify-between gap-3 pt-3 border-t border-slate-100 text-xs">
                  <div className="flex flex-wrap items-center gap-1.5">
                    <span className="font-bold text-slate-500 mr-1">Statutory Sections:</span>
                    {(item.statutory_sections || []).map((sec: string) => (
                      <span key={sec} className="px-2 py-0.5 rounded-md bg-slate-100 text-slate-700 font-mono text-[11px] font-bold">
                        {sec}
                      </span>
                    ))}
                  </div>

                  <div className="flex flex-wrap gap-1">
                    {(item.tags || []).map((t: string) => (
                      <span key={t} className="text-[10px] font-medium text-slate-500 px-1.5 py-0.5 rounded bg-slate-50">
                        #{t}
                      </span>
                    ))}
                  </div>
                </div>
              </div>
            ))}
          </div>
        )}

        {/* AI Case Summarizer Modal */}
        {summarizerOpen && (
          <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/70 backdrop-blur-md p-4 animate-fade-in">
            <div className="bg-white rounded-3xl shadow-2xl max-w-2xl w-full p-6 sm:p-8 border border-slate-200 max-h-[90vh] overflow-y-auto relative text-slate-900">
              <button
                onClick={() => setSummarizerOpen(false)}
                className="absolute top-5 right-5 p-2 rounded-full hover:bg-slate-100 text-slate-400 hover:text-slate-700 transition-colors"
              >
                <X size={18} />
              </button>

              <div className="inline-flex items-center gap-1.5 px-3 py-1 bg-rose-50 text-court-maroon border border-rose-200 rounded-full text-xs font-bold mb-4">
                <Sparkles size={13} />
                <span>AI Case Summarizer &amp; Legal Synthesis</span>
              </div>

              <h2 className="text-2xl sm:text-3xl font-black text-ashoka-navy mb-2 tracking-tight">
                {activeCase ? activeCase.title : 'Analyze Any Court Judgment'}
              </h2>
              <p className="text-xs text-slate-500 mb-6 font-medium">
                {activeCase
                  ? `Detailed legal ratio and hearing orders synthesized from ${activeCase.court} precedent.`
                  : 'Paste any court judgment or dispute text below to generate an instant legal breakdown.'}
              </p>

              {/* Custom Input if no case is selected */}
              {!activeCase && (
                <div className="mb-6">
                  <textarea
                    rows={4}
                    value={customCaseText}
                    onChange={(e) => setCustomCaseText(e.target.value)}
                    placeholder="Paste court order text, judgment excerpt, or dispute facts here..."
                    className="w-full p-4 text-sm bg-slate-50 border border-slate-300 rounded-2xl focus:outline-none focus:border-court-maroon font-medium mb-3"
                  />
                  <button
                    onClick={handleCustomSummarize}
                    disabled={summarizing || !customCaseText.trim()}
                    className="w-full py-3 bg-gradient-to-r from-court-maroon to-rose-700 text-white font-bold text-sm rounded-xl flex items-center justify-center gap-2 shadow-sm disabled:opacity-40 cursor-pointer"
                  >
                    {summarizing ? <Loader2 size={16} className="animate-spin" /> : <Sparkles size={16} />}
                    <span>Summarize Judgment</span>
                  </button>
                </div>
              )}

              {/* Summarizing Loader */}
              {summarizing && (
                <div className="py-12 text-center">
                  <Loader2 size={32} className="animate-spin text-court-maroon mx-auto mb-3" />
                  <p className="text-sm font-bold text-ashoka-navy">Analyzing judgment &amp; statutory ratio...</p>
                  <p className="text-xs text-slate-500">Extracting facts, hearing directives, sections, and citizen action takeaway.</p>
                </div>
              )}

              {/* Summary Results Card */}
              {summaryData && !summarizing && (
                <div className="space-y-4 text-left">
                  <div className="bg-slate-50 p-4 rounded-2xl border border-slate-200">
                    <span className="block text-[10px] font-bold text-slate-400 uppercase tracking-wider mb-1">
                      Case Title &amp; Jurisdiction
                    </span>
                    <h4 className="text-base font-black text-ashoka-navy">
                      {summaryData.case_title}
                    </h4>
                    <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2 mt-2">
                      <div className="flex flex-wrap items-center gap-2">
                        <span className="text-xs font-bold text-court-maroon">
                          {summaryData.court_and_year}
                        </span>
                        {summaryData.presiding_bench && (
                          <span className="text-xs font-medium text-slate-600">
                            • Bench: {summaryData.presiding_bench}
                          </span>
                        )}
                      </div>
                      {activeCase && (
                        <button
                          type="button"
                          onClick={() => handleDownloadPdf(activeCase.id)}
                          disabled={downloadingId === activeCase.id}
                          className="px-3 py-1.5 rounded-xl bg-white hover:bg-slate-50 border border-slate-300 text-slate-700 text-xs font-bold flex items-center gap-1.5 shadow-2xs transition-colors cursor-pointer disabled:opacity-50 self-start sm:self-auto"
                        >
                          {downloadingId === activeCase.id ? (
                            <Loader2 size={12} className="animate-spin text-court-maroon" />
                          ) : (
                            <Download size={12} className="text-court-maroon" />
                          )}
                          <span>Download Case Brief PDF</span>
                        </button>
                      )}
                    </div>
                  </div>

                  <div className="bg-white p-4 rounded-2xl border border-slate-200 shadow-xs">
                    <span className="block text-[10px] font-bold text-slate-400 uppercase tracking-wider mb-1">
                      Core Dispute &amp; Background
                    </span>
                    <p className="text-xs text-slate-700 leading-relaxed font-medium">
                      {summaryData.facts_summary}
                    </p>
                  </div>

                  {/* Hearing Orders Given by Court */}
                  {summaryData.court_hearing_and_directions && (
                    <div className="bg-rose-50/70 p-4 rounded-2xl border border-rose-200 shadow-xs">
                      <span className="block text-[10px] font-black text-court-maroon uppercase tracking-wider mb-1 flex items-center gap-1.5">
                        <Gavel size={13} />
                        The Hearing &amp; Operative Orders the Court Gave:
                      </span>
                      <p className="text-xs text-slate-800 font-medium leading-relaxed whitespace-pre-line">
                        {summaryData.court_hearing_and_directions}
                      </p>
                    </div>
                  )}

                  {/* Upgrade 3: AI Case Relevance Advisor Card */}
                  {summaryData.case_relevance_advisor && (
                    <div className="bg-gradient-to-br from-emerald-50 via-teal-50/60 to-emerald-50 border border-emerald-300 rounded-3xl p-5 shadow-xs space-y-3.5">
                      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2 pb-2.5 border-b border-emerald-200">
                        <div className="flex items-center gap-2">
                          <div className="w-7 h-7 rounded-lg bg-emerald-600 text-white flex items-center justify-center shrink-0 shadow-2xs">
                            <ShieldCheck size={16} />
                          </div>
                          <div>
                            <span className="text-[10px] font-black uppercase tracking-wider text-emerald-800">
                              Legal Match Strategy
                            </span>
                            <h4 className="text-sm font-black text-emerald-950">
                              Why This Precedent Wins Your Specific Case
                            </h4>
                          </div>
                        </div>

                        <span className="text-[10px] font-bold bg-emerald-200/70 text-emerald-900 px-2.5 py-1 rounded-full self-start sm:self-auto">
                          Advocate-Grade Analysis
                        </span>
                      </div>

                      {/* Evidentiary Parallel */}
                      <div className="space-y-1">
                        <span className="text-[10px] font-black uppercase tracking-wider text-emerald-900 block">
                          1. Evidentiary Parallel to Your Complaint:
                        </span>
                        <p className="text-xs text-emerald-950 font-medium leading-relaxed bg-white/70 p-2.5 rounded-xl border border-emerald-100">
                          {summaryData.case_relevance_advisor.evidentiary_parallel}
                        </p>
                      </div>

                      {/* Opposing Authority Counter */}
                      <div className="space-y-1">
                        <span className="text-[10px] font-black uppercase tracking-wider text-rose-900 block">
                          2. Why Opposing Authority&apos;s Defense is Legally Void:
                        </span>
                        <p className="text-xs text-rose-950 font-medium leading-relaxed bg-rose-50/80 p-2.5 rounded-xl border border-rose-200">
                          {summaryData.case_relevance_advisor.counter_argument}
                        </p>
                      </div>

                      {/* Ready-to-Cite Winning Advocacy Paragraph */}
                      <div className="bg-white p-3.5 rounded-2xl border border-emerald-300 shadow-xs space-y-2">
                        <div className="flex items-center justify-between gap-2">
                          <span className="text-[10px] font-black uppercase tracking-wider text-slate-700">
                            3. Actionable Advocacy Paragraph (Ready to Paste in Petition):
                          </span>
                          <button
                            type="button"
                            onClick={() => {
                              navigator.clipboard.writeText(summaryData.case_relevance_advisor.winning_advocacy_paragraph);
                              setCopiedAdvisorArg(true);
                              setTimeout(() => setCopiedAdvisorArg(false), 2000);
                            }}
                            className="px-2.5 py-1 rounded-lg bg-emerald-50 hover:bg-emerald-100 text-emerald-800 text-[11px] font-bold flex items-center gap-1 border border-emerald-200 transition-colors cursor-pointer"
                          >
                            {copiedAdvisorArg ? <Check size={12} className="text-emerald-600" /> : <Copy size={12} />}
                            <span>{copiedAdvisorArg ? 'Copied Paragraph!' : 'Copy Paragraph'}</span>
                          </button>
                        </div>
                        <p className="text-xs text-slate-800 font-mono leading-relaxed select-all bg-slate-50 p-2.5 rounded-xl border border-slate-200">
                          &quot;{summaryData.case_relevance_advisor.winning_advocacy_paragraph}&quot;
                        </p>
                      </div>
                    </div>
                  )}

                  <div className="bg-slate-50 p-4 rounded-2xl border border-slate-200 shadow-xs">
                    <span className="block text-[10px] font-bold text-slate-500 uppercase tracking-wider mb-1">
                      Ratio Decidendi (Binding Legal Principle)
                    </span>
                    <p className="text-xs sm:text-sm text-slate-900 font-bold leading-relaxed">
                      &quot;{summaryData.ratio_decidendi}&quot;
                    </p>
                  </div>

                  <div className="bg-amber-50 p-4 rounded-2xl border border-amber-200 shadow-xs">
                    <span className="block text-[10px] font-bold text-amber-900 uppercase tracking-wider mb-1">
                      How to Cite in Your Case (Action Takeaway)
                    </span>
                    <p className="text-xs text-amber-950 font-mono font-medium leading-relaxed select-all">
                      {summaryData.citizen_action_takeaway}
                    </p>
                  </div>

                  {summaryData.statutory_clauses && summaryData.statutory_clauses.length > 0 && (
                    <div className="flex flex-wrap items-center gap-1.5 pt-2">
                      <span className="text-[10px] font-bold text-slate-400 uppercase">Applicable Sections:</span>
                      {summaryData.statutory_clauses.map((sec: string) => (
                        <span key={sec} className="px-2 py-0.5 rounded bg-slate-100 text-slate-700 text-xs font-mono font-bold">
                          {sec}
                        </span>
                      ))}
                    </div>
                  )}
                </div>
              )}
            </div>
          </div>
        )}
      </main>
    </div>
  );
}
