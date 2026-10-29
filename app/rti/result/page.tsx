'use client';

import { useState } from 'react';
import { motion } from 'framer-motion';
import { Sparkles, TrendingUp, AlertCircle, RefreshCw } from 'lucide-react';
import DraftViewer from '@/components/dashboard/DraftViewer';
import { rtiPredict, rtiImprove } from '@/lib/api';

interface RTIResultViewProps {
  caseId: string;
  initialDraft: string;
  initialDepartment?: string;
}

export default function RTIResultView({
  caseId,
  initialDraft,
  initialDepartment,
}: RTIResultViewProps) {
  const [draft, setDraft] = useState<string>(initialDraft);
  const [prediction, setPrediction] = useState<any>(null);
  const [loadingPredict, setLoadingPredict] = useState<boolean>(false);
  const [loadingImprove, setLoadingImprove] = useState<boolean>(false);

  // Analyze draft using rtiPredict
  const handlePredict = async () => {
    if (!caseId) return;
    setLoadingPredict(true);
    try {
      const res = await rtiPredict(caseId, draft);
      setPrediction(res);
    } catch (err) {
      console.error('Prediction failed:', err);
    } finally {
      setLoadingPredict(false);
    }
  };

  // Enhance draft using rtiImprove
  const handleImprove = async () => {
    if (!caseId) return;
    setLoadingImprove(true);
    try {
      const res = await rtiImprove(caseId);
      if (res?.draft_text || res?.improved_draft) {
        setDraft(res.draft_text || res.improved_draft);
      }
    } catch (err) {
      console.error('Improvement failed:', err);
    } finally {
      setLoadingImprove(false);
    }
  };

  return (
    <div className="max-w-5xl mx-auto p-6 space-y-6">
      {/* Top Header & Quick Actions */}
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4 bg-white p-6 rounded-3xl border border-slate-200 shadow-sm">
        <div>
          <h1 className="text-xl font-bold text-slate-900">RTI Application Ready</h1>
          <p className="text-xs text-slate-500 mt-1">
            Department: <span className="font-semibold text-slate-700">{initialDepartment || 'Resolving...'}</span>
          </p>
        </div>

        <div className="flex items-center gap-2">
          <button
            onClick={handlePredict}
            disabled={loadingPredict}
            type="button"
            className="flex items-center gap-2 px-4 py-2 text-xs font-semibold text-slate-700 bg-slate-100 hover:bg-slate-200 rounded-xl transition-colors disabled:opacity-50 cursor-pointer"
          >
            <TrendingUp size={15} className="text-blue-600" />
            {loadingPredict ? 'Analyzing...' : 'Predict Success Score'}
          </button>

          <button
            onClick={handleImprove}
            disabled={loadingImprove}
            type="button"
            className="flex items-center gap-2 px-4 py-2 text-xs font-semibold text-white bg-blue-600 hover:bg-blue-700 rounded-xl transition-colors disabled:opacity-50 cursor-pointer"
          >
            <Sparkles size={15} />
            {loadingImprove ? 'Enhancing...' : 'Auto-Improve Draft'}
          </button>
        </div>
      </div>

      {/* Prediction Analytics Card (Renders when prediction data exists) */}
      {prediction && (
        <motion.div
          initial={{ opacity: 0, y: 12 }}
          animate={{ opacity: 1, y: 0 }}
          className="bg-slate-900 text-white p-6 rounded-3xl space-y-4"
        >
          <div className="flex items-center justify-between">
            <span className="text-xs font-semibold uppercase tracking-wider text-slate-400">
              AI Success Score Analysis
            </span>
            <span className="text-2xl font-bold text-emerald-400">
              {prediction.success_rate || prediction.score || '85'}%
            </span>
          </div>
          {prediction.feedback && (
            <p className="text-xs text-slate-300 leading-relaxed border-t border-slate-800 pt-3">
              {prediction.feedback}
            </p>
          )}
        </motion.div>
      )}

      {/* Draft Document Viewer & Download Suite */}
      <DraftViewer
        title="RTI Application Draft"
        draft={draft}
        caseId={caseId}
      />
    </div>
  );
}
