'use client';

import React, { useState } from 'react';
import {
  Scale,
  BookOpen,
  ExternalLink,
  Download,
  Copy,
  Check,
  ShieldCheck,
  AlertCircle,
  Calendar,
  Building2,
  FileText
} from 'lucide-react';
import { CitationMetadata } from '@/lib/api';

interface LegalCitationCardProps {
  citation: CitationMetadata;
  compact?: boolean;
}

export default function LegalCitationCard({ citation, compact = false }: LegalCitationCardProps) {
  const [copied, setCopied] = useState(false);

  const handleCopyCitation = () => {
    const textToCopy = citation.how_to_cite || `${citation.case_title} [${citation.citation}]`;
    navigator.clipboard.writeText(textToCopy);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  const isBinding = citation.authority_type === 'BINDING';

  if (compact) {
    return (
      <div className="p-3.5 rounded-2xl bg-white border border-slate-200 hover:border-court-maroon/40 shadow-sm transition-all space-y-2">
        <div className="flex items-center justify-between gap-2">
          <span
            className={`text-[10px] font-bold uppercase tracking-wider px-2 py-0.5 rounded-md ${
              isBinding
                ? 'bg-emerald-50 text-emerald-700 border border-emerald-200'
                : 'bg-purple-50 text-purple-700 border border-purple-200'
            }`}
          >
            {isBinding ? 'Binding Authority' : 'Persuasive Authority'}
          </span>
          <span className="text-[11px] font-mono text-slate-400 font-medium">
            {citation.year || citation.citation}
          </span>
        </div>

        <div>
          <h4 className="text-xs font-bold text-slate-900 leading-snug line-clamp-1">
            {citation.case_title}
          </h4>
          <span className="text-[11px] text-slate-500 flex items-center gap-1 mt-0.5">
            <Building2 className="w-3 h-3 text-slate-400 shrink-0" />
            <span className="truncate">{citation.court}</span>
          </span>
        </div>

        <div className="flex items-center justify-between pt-1 border-t border-slate-100 text-xs">
          <button
            type="button"
            onClick={handleCopyCitation}
            className="text-[11px] text-court-maroon font-bold flex items-center gap-1 hover:underline cursor-pointer"
          >
            {copied ? <Check className="w-3 h-3 text-emerald-600" /> : <Copy className="w-3 h-3" />}
            <span>{copied ? 'Copied' : 'Cite'}</span>
          </button>

          {citation.source_url && (
            <a
              href={citation.source_url}
              target="_blank"
              rel="noopener noreferrer"
              className="text-[11px] text-slate-500 hover:text-slate-800 flex items-center gap-1"
            >
              <span>Source</span>
              <ExternalLink className="w-3 h-3" />
            </a>
          )}
        </div>
      </div>
    );
  }

  return (
    <div className="p-5 rounded-3xl bg-white border border-slate-200 hover:border-slate-300 shadow-sm space-y-4 transition-all">
      {/* Header Badges */}
      <div className="flex flex-wrap items-center justify-between gap-2">
        <div className="flex items-center gap-2">
          <span
            className={`text-[10px] font-bold uppercase tracking-wider px-2.5 py-1 rounded-full flex items-center gap-1 ${
              isBinding
                ? 'bg-emerald-50 text-emerald-800 border border-emerald-200'
                : 'bg-purple-50 text-purple-800 border border-purple-200'
            }`}
          >
            <ShieldCheck className="w-3 h-3" />
            <span>{isBinding ? 'Binding Authority (Art. 141)' : 'Persuasive Precedent'}</span>
          </span>

          <span className="text-[10px] font-bold uppercase tracking-wider px-2.5 py-1 rounded-full bg-slate-100 text-slate-700 border border-slate-200">
            {citation.category}
          </span>
        </div>

        <span className="text-xs font-mono font-bold text-slate-500">
          {citation.citation}
        </span>
      </div>

      {/* Title & Court */}
      <div>
        <h3 className="text-sm font-bold text-slate-900 leading-snug">
          {citation.case_title}
        </h3>
        <div className="flex flex-wrap items-center gap-3 text-xs text-slate-500 mt-1">
          <span className="flex items-center gap-1 font-medium">
            <Building2 className="w-3.5 h-3.5 text-slate-400" />
            <span>{citation.court}</span>
          </span>
          {citation.year && (
            <>
              <span>•</span>
              <span className="flex items-center gap-1">
                <Calendar className="w-3.5 h-3.5 text-slate-400" />
                <span>{citation.year}</span>
              </span>
            </>
          )}
          {citation.bench && (
            <>
              <span>•</span>
              <span className="truncate max-w-xs">{citation.bench}</span>
            </>
          )}
        </div>
      </div>

      {/* Ratio Decidendi */}
      <div className="p-3.5 rounded-2xl bg-slate-50 border border-slate-200/80 space-y-1">
        <span className="text-[10px] font-bold uppercase tracking-wider text-slate-400 block">
          Key Ratio Decidendi / Legal Principle
        </span>
        <p className="text-xs text-slate-700 leading-relaxed">
          {citation.relevant_ratio}
        </p>
      </div>

      {/* Statutory Provisions */}
      {citation.statutory_provisions && citation.statutory_provisions.length > 0 && (
        <div className="flex flex-wrap items-center gap-1.5 text-xs">
          <span className="text-[11px] font-semibold text-slate-400 mr-1">Statutory Provisions:</span>
          {citation.statutory_provisions.map((sec, idx) => (
            <span
              key={idx}
              className="px-2 py-0.5 rounded-md bg-amber-50 text-amber-800 border border-amber-200 text-[11px] font-medium"
            >
              {sec}
            </span>
          ))}
        </div>
      )}

      {/* Citation Guidance & Actions */}
      <div className="pt-3 border-t border-slate-100 flex flex-col sm:flex-row sm:items-center justify-between gap-3">
        <div className="text-xs text-slate-500 truncate max-w-sm">
          <span className="font-bold text-slate-700">Recommended Citation: </span>
          <span className="font-mono text-[11px]">{citation.how_to_cite}</span>
        </div>

        <div className="flex items-center gap-2 shrink-0">
          <button
            type="button"
            onClick={handleCopyCitation}
            className="px-3 py-1.5 rounded-xl bg-white border border-slate-200 text-slate-700 hover:bg-slate-50 text-xs font-bold transition-colors flex items-center gap-1.5 cursor-pointer shadow-sm"
          >
            {copied ? <Check className="w-3.5 h-3.5 text-emerald-600" /> : <Copy className="w-3.5 h-3.5" />}
            <span>{copied ? 'Copied' : 'Copy Citation'}</span>
          </button>

          {citation.pdf_download_url && (
            <a
              href={citation.pdf_download_url}
              download
              className="px-3 py-1.5 rounded-xl bg-slate-100 hover:bg-slate-200 text-slate-800 text-xs font-bold transition-colors flex items-center gap-1.5 shadow-sm"
            >
              <Download className="w-3.5 h-3.5" />
              <span>PDF Brief</span>
            </a>
          )}

          {citation.source_url && (
            <a
              href={citation.source_url}
              target="_blank"
              rel="noopener noreferrer"
              className="px-3 py-1.5 rounded-xl bg-court-maroon hover:bg-rose-900 text-white text-xs font-bold transition-colors flex items-center gap-1.5 shadow-sm"
            >
              <span>Official Source</span>
              <ExternalLink className="w-3.5 h-3.5" />
            </a>
          )}
        </div>
      </div>
    </div>
  );
}

export function LegalCitationsList({
  citations,
  hasCitations,
  emptyMessage,
  compact = false
}: {
  citations: CitationMetadata[];
  hasCitations?: boolean;
  emptyMessage?: string;
  compact?: boolean;
}) {
  if (!hasCitations || citations.length === 0) {
    return (
      <div className="p-4 rounded-2xl bg-slate-50 border border-slate-200 text-center text-xs text-slate-500 flex items-center justify-center gap-2">
        <AlertCircle className="w-4 h-4 text-slate-400 shrink-0" />
        <span>
          {emptyMessage || 'No verified judicial precedents found for this specific query.'}
        </span>
      </div>
    );
  }

  return (
    <div className={`space-y-3 ${compact ? 'grid grid-cols-1 sm:grid-cols-2 gap-3 space-y-0' : ''}`}>
      {citations.map((c, idx) => (
        <LegalCitationCard key={c.source_identifier || idx} citation={c} compact={compact} />
      ))}
    </div>
  );
}
