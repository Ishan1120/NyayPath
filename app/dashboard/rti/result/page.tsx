'use client';

import { Suspense } from 'react';
import RTIResultView from '@/views/RTIResultView';

export default function RTIResultPage() {
  return (
    <Suspense
      fallback={
        <div className="min-h-screen bg-slate-950 text-slate-100 flex items-center justify-center font-mono">
          <div className="text-center space-y-3">
            <div className="h-6 w-6 border-2 border-emerald-500 border-t-transparent rounded-full animate-spin mx-auto" />
            <p className="text-slate-400 text-sm">Loading RTI Result Session...</p>
          </div>
        </div>
      }
    >
      <RTIResultView />
    </Suspense>
  );
}
