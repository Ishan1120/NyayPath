'use client';

import React, { useState, useEffect } from 'react';
import Link from 'next/link';
import { 
  Scale, 
  ArrowLeft, 
  Newspaper, 
  ExternalLink, 
  Calendar, 
  Building2, 
  ShieldCheck, 
  Sparkles, 
  Filter, 
  ArrowRight,
  Search,
  RotateCw,
  Gavel,
  Radio,
  FileText,
  Clock,
  ArrowUpDown,
  X
} from 'lucide-react';
import Navbar from '@/app/Navbar';
import { fetchCourtNews } from '@/lib/api';

export default function CourtNewsPage() {
  const [newsList, setNewsList] = useState<any[]>([]);
  const [selectedCategory, setSelectedCategory] = useState('All');
  const [searchQuery, setSearchQuery] = useState('');
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [lastUpdated, setLastUpdated] = useState('Checking live feed...');
  const [sourceStatus, setSourceStatus] = useState('Connecting to Legal Wire...');

  const categories = [
    'All',
    'Campus Discipline & Anti-Ragging',
    'Education & Examination',
    'Civic Infrastructure & Roads',
    'Consumer Protection & Housing',
    'Social Security & Pension',
    'Public Healthcare & Medical Rights',
    'Constitutional & Digital Rights'
  ];

  const loadNews = async (force: boolean = false) => {
    if (force) setRefreshing(true);
    else setLoading(true);

    try {
      const data = await fetchCourtNews(selectedCategory, force);
      setNewsList(data?.news || []);
      if (data?.last_updated_at) setLastUpdated(data.last_updated_at);
      if (data?.source_status) setSourceStatus(data.source_status);
    } catch (err) {
      console.error('Failed to load court news', err);
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  };

  useEffect(() => {
    loadNews(false);
  }, [selectedCategory]);

  // Filter and strictly sort newest first (descending by timestamp_ms)
  const filteredNews = newsList
    .filter((n) => {
      if (!searchQuery.trim()) return true;
      const q = searchQuery.toLowerCase();
      return (
        (n.headline || '').toLowerCase().includes(q) ||
        (n.summary || '').toLowerCase().includes(q) ||
        (n.court || '').toLowerCase().includes(q) ||
        (n.court_hearing_and_directions || '').toLowerCase().includes(q) ||
        (n.bench || '').toLowerCase().includes(q) ||
        (n.date || '').toLowerCase().includes(q) ||
        (n.relative_time || '').toLowerCase().includes(q) ||
        (n.tags || []).some((t: string) => t.toLowerCase().includes(q))
      );
    })
    .sort((a, b) => {
      const timeA = a.timestamp_ms || 0;
      const timeB = b.timestamp_ms || 0;
      return timeB - timeA;
    });

  return (
    <div className="min-h-screen bg-[#F8FAFC] text-slate-900 font-sans">
      <Navbar />

      <main className="max-w-6xl mx-auto px-4 sm:px-6 pt-28 pb-16">
        {/* Navigation Breadcrumb & Live Refresh Status Bar */}
        <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-4 mb-8">
          <Link
            href="/"
            className="inline-flex items-center gap-1.5 text-xs font-bold text-slate-600 hover:text-court-maroon transition-colors"
          >
            <ArrowLeft size={14} />
            <span>Back to Home</span>
          </Link>

          <div className="flex flex-wrap items-center gap-2.5">
            <div className="inline-flex items-center gap-2 px-3 py-1.5 rounded-full bg-emerald-50 border border-emerald-200 text-emerald-900 text-xs font-semibold shadow-xs">
              <span className="w-2 h-2 rounded-full bg-emerald-500 animate-pulse shrink-0" />
              <span>{sourceStatus}</span>
              <span className="text-emerald-400">•</span>
              <span className="text-[11px] text-emerald-700 font-mono">Updated: {lastUpdated}</span>
            </div>

            <button
              onClick={() => loadNews(true)}
              disabled={refreshing || loading}
              className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-full bg-white hover:bg-slate-100 border border-slate-300 text-slate-700 text-xs font-bold shadow-xs cursor-pointer transition-all active:scale-95 disabled:opacity-50"
              title="Fetch fresh real-time RSS updates from Bar & Bench and Supreme Court"
            >
              <RotateCw size={13} className={refreshing ? 'animate-spin text-court-maroon' : 'text-slate-500'} />
              <span>{refreshing ? 'Fetching Live Wire...' : 'Refresh Feed'}</span>
            </button>
          </div>
        </div>

        {/* Hero Section */}
        <div className="text-center max-w-3xl mx-auto mb-10">
          <div className="inline-flex items-center gap-2 px-3.5 py-1.5 rounded-full bg-rose-50 border border-rose-200 text-court-maroon text-xs font-bold mb-4 shadow-xs">
            <Newspaper size={14} />
            <span>Live Judicial Intelligence &amp; Operative Bench Orders</span>
          </div>
          <h1 className="text-3xl sm:text-5xl font-black text-ashoka-navy tracking-tight mb-4">
            Live Court News &amp; Court Hearings
          </h1>
          <p className="text-sm sm:text-base text-slate-600 font-medium leading-relaxed">
            Continuously updated judicial feed covering the Supreme Court of India, State High Courts, and Central Information Commission. Review the exact oral arguments, operative hearing directives, and citations you can use in your legal complaints.
          </p>
        </div>

        {/* Search & Filter Bar */}
        <div className="bg-white p-4 sm:p-5 rounded-3xl border border-slate-200 shadow-sm mb-6">
          <div className="flex flex-col md:flex-row items-center gap-4 mb-4">
            <div className="relative w-full">
              <Search className="absolute left-3.5 top-1/2 -translate-y-1/2 text-slate-400" size={16} />
              <input
                type="text"
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                placeholder="Search judgments by judge, bench directive, or keyword (e.g. ragging FIR, answer sheet inspection, PWD pothole, builder refund)..."
                className="w-full pl-10 pr-10 py-3 text-sm bg-slate-50 border border-slate-200 rounded-xl focus:outline-none focus:border-court-maroon focus:ring-2 focus:ring-court-maroon/10 font-medium"
              />
              {searchQuery && (
                <button
                  onClick={() => setSearchQuery('')}
                  className="absolute right-3.5 top-1/2 -translate-y-1/2 text-slate-400 hover:text-slate-600"
                  title="Clear search"
                >
                  <X size={15} />
                </button>
              )}
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

        {/* Results Counter & Sort Indicator Bar */}
        <div className="flex flex-wrap items-center justify-between gap-3 mb-6 px-1">
          <div className="text-xs font-bold text-slate-600 flex items-center gap-2">
            <span>Showing <span className="text-court-maroon font-black">{filteredNews.length}</span> court orders &amp; live reports</span>
            {searchQuery && (
              <span className="text-slate-400 text-[11px] font-normal">
                (filtered by &ldquo;{searchQuery}&rdquo;)
              </span>
            )}
          </div>

          <div className="inline-flex items-center gap-1.5 px-3 py-1 rounded-full bg-white border border-slate-200 text-xs font-semibold text-slate-700 shadow-2xs">
            <ArrowUpDown size={12} className="text-court-maroon" />
            <span className="text-slate-500 font-medium">Sorted by:</span>
            <span className="font-bold text-slate-900">Newest First</span>
            <span className="text-[10px] text-emerald-700 font-bold bg-emerald-50 px-1.5 py-0.2 rounded">Real-time</span>
          </div>
        </div>

        {/* News Grid */}
        {loading ? (
          <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
            {[1, 2, 3, 4].map((i) => (
              <div key={i} className="h-80 rounded-3xl bg-slate-100 animate-pulse border border-slate-200" />
            ))}
          </div>
        ) : filteredNews.length === 0 ? (
          <div className="text-center py-16 bg-white rounded-3xl border border-slate-200">
            <Newspaper size={36} className="mx-auto text-slate-300 mb-3" />
            <h3 className="text-lg font-bold text-slate-700 mb-1">No matching judicial news found</h3>
            <p className="text-xs text-slate-500">Try adjusting your search terms or category filter.</p>
          </div>
        ) : (
          <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
            {filteredNews.map((item) => (
              <div
                key={item.id}
                className="bg-white rounded-3xl border border-slate-200 hover:border-court-maroon/40 p-6 sm:p-7 shadow-xs hover:shadow-md transition-all flex flex-col justify-between group"
              >
                <div>
                  {/* Badge & Prominent Date/Time Header */}
                  <div className="flex flex-wrap items-center justify-between gap-2.5 mb-3.5 pb-2.5 border-b border-slate-100">
                    <div className="flex items-center gap-2 flex-wrap">
                      <span className={`px-2.5 py-1 rounded-full text-[11px] font-bold flex items-center gap-1 ${
                        item.is_live
                          ? 'bg-emerald-50 text-emerald-800 border border-emerald-200'
                          : 'bg-amber-50 text-amber-900 border border-amber-200'
                      }`}>
                        {item.is_live && <Radio size={11} className="text-emerald-600 animate-pulse" />}
                        <span>{item.badge}</span>
                      </span>

                      {item.relative_time && (
                        <span className="inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full text-[10px] font-bold bg-sky-50 text-sky-800 border border-sky-200">
                          <Clock size={11} className="text-sky-600" />
                          <span>{item.relative_time}</span>
                        </span>
                      )}
                    </div>

                    {/* Highly Visible Posted Date Badge */}
                    <div className="inline-flex items-center gap-1.5 px-3 py-1 rounded-xl bg-slate-100 border border-slate-200/90 text-xs font-bold text-slate-800 shadow-2xs">
                      <Calendar size={13} className="text-court-maroon shrink-0" />
                      <span className="text-[11px] text-slate-500 font-medium">Posted:</span>
                      <span className="font-bold text-slate-900">{item.date}</span>
                    </div>
                  </div>

                  {/* Headline */}
                  <h3 className="text-lg sm:text-xl font-black text-ashoka-navy group-hover:text-court-maroon transition-colors mb-2 leading-snug">
                    {item.headline}
                  </h3>

                  {/* Court & Bench */}
                  <div className="space-y-1 mb-4">
                    <div className="flex items-center gap-1.5 text-xs font-bold text-slate-700">
                      <Building2 size={14} className="text-court-maroon shrink-0" />
                      <span>{item.court}</span>
                      <span className="text-slate-300">•</span>
                      <span className="text-rose-700">{item.category}</span>
                    </div>
                    {item.bench && (
                      <div className="flex items-center gap-1.5 text-[11px] font-semibold text-slate-500">
                        <Scale size={13} className="text-slate-400 shrink-0" />
                        <span>Bench: {item.bench}</span>
                      </div>
                    )}
                  </div>

                  {/* Summary / Dispute Facts */}
                  <p className="text-sm text-slate-600 font-medium leading-relaxed mb-4">
                    {item.summary}
                  </p>

                  {/* STRUCTURED: The Hearing That Court Gave */}
                  {item.court_hearing_and_directions && (
                    <div className="bg-rose-50/70 border border-rose-200/80 rounded-2xl p-4 mb-4 text-left">
                      <span className="block text-[11px] font-black uppercase tracking-wider text-court-maroon mb-1.5 flex items-center gap-1.5">
                        <Gavel size={14} className="text-court-maroon shrink-0" />
                        <span>The Hearing &amp; Operative Orders the Court Gave:</span>
                      </span>
                      <div className="text-xs sm:text-[13px] text-slate-800 font-medium leading-relaxed whitespace-pre-line">
                        {item.court_hearing_and_directions}
                      </div>
                    </div>
                  )}
                </div>

                {/* Footer Section */}
                <div className="pt-4 border-t border-slate-100 mt-auto">
                  <div className="bg-slate-50 rounded-2xl p-3.5 mb-4 border border-slate-100">
                    <span className="block text-[10px] font-bold uppercase tracking-wider text-slate-500 mb-1 flex items-center gap-1">
                      <ShieldCheck size={12} className="text-emerald-600" />
                      Statutory Citizen &amp; Student Impact:
                    </span>
                    <p className="text-xs text-slate-700 font-semibold leading-relaxed">
                      {item.statutory_impact}
                    </p>
                  </div>

                  <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-3">
                    <div className="flex flex-wrap gap-1.5">
                      {(item.tags || []).map((t: string) => (
                        <span key={t} className="text-[10px] font-semibold px-2 py-0.5 rounded-md bg-slate-100 text-slate-600">
                          #{t}
                        </span>
                      ))}
                    </div>

                    <div className="flex items-center gap-3 shrink-0">
                      {item.source_link && (
                        <a
                          href={item.source_link}
                          target="_blank"
                          rel="noopener noreferrer"
                          className="inline-flex items-center gap-1 text-[11px] font-bold text-slate-500 hover:text-slate-800 transition-colors"
                          title="Open original judicial report"
                        >
                          <span>Source</span>
                          <ExternalLink size={12} />
                        </a>
                      )}

                      <Link
                        href={`/case-search?query=${encodeURIComponent(item.category.split('&')[0].trim())}`}
                        className="inline-flex items-center gap-1 text-xs font-bold text-court-maroon hover:text-rose-800 transition-colors"
                      >
                        <span>Search Citations</span>
                        <ArrowRight size={13} />
                      </Link>
                    </div>
                  </div>
                </div>
              </div>
            ))}
          </div>
        )}

        {/* Quick Footer Call-out */}
        <div className="mt-12 bg-gradient-to-r from-court-maroon via-rose-800 to-ashoka-navy rounded-3xl p-8 text-white shadow-xl flex flex-col sm:flex-row items-center justify-between gap-6">
          <div className="max-w-xl text-center sm:text-left">
            <h3 className="text-2xl font-black mb-2 tracking-tight">Need to cite a court hearing in your RTI or Grievance?</h3>
            <p className="text-sm text-rose-100 font-medium">
              Explore our landmark Indian Case Law library with 14+ deep structured precedents, complete bench orders, and an AI Case Summarizer.
            </p>
          </div>

          <div className="flex flex-wrap gap-3">
            <Link
              href="/case-search"
              className="px-6 py-3 rounded-xl bg-white text-court-maroon font-black text-sm hover:bg-rose-50 transition-all shadow-md shrink-0 flex items-center gap-2"
            >
              <Sparkles size={16} />
              <span>Explore Landmark Precedents &amp; AI Summarizer</span>
            </Link>
            <Link
              href="/dashboard"
              className="px-6 py-3 rounded-xl bg-white/10 hover:bg-white/20 border border-white/20 text-white font-bold text-sm transition-all shrink-0"
            >
              <span>Draft Statutory RTI</span>
            </Link>
          </div>
        </div>
      </main>
    </div>
  );
}
