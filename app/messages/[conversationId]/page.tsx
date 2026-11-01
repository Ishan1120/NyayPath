'use client';

import React, { useEffect } from 'react';
import { useParams, useRouter } from 'next/navigation';

export default function ConversationDetailPage() {
  const params = useParams();
  const router = useRouter();
  const conversationId = params?.conversationId as string;

  useEffect(() => {
    if (conversationId) {
      router.replace(`/messages?id=${encodeURIComponent(conversationId)}`);
    } else {
      router.replace('/messages');
    }
  }, [conversationId, router]);

  return (
    <div className="min-h-screen bg-slate-50 flex items-center justify-center font-sans">
      <div className="text-center">
        <div className="w-8 h-8 border-3 border-court-maroon border-t-transparent rounded-full animate-spin mx-auto mb-3" />
        <p className="text-xs text-slate-500">Opening conversation...</p>
      </div>
    </div>
  );
}

