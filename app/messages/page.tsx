'use client';

import React, { useState, useEffect, useRef } from 'react';
import Link from 'next/link';
import { useRouter, useSearchParams } from 'next/navigation';
import {
  MessageSquare,
  Send,
  Paperclip,
  Calendar,
  Clock,
  Shield,
  ShieldCheck,
  User,
  Scale,
  FileText,
  Download,
  Check,
  CheckCheck,
  ArrowLeft,
  RefreshCw,
  AlertCircle,
  ExternalLink,
  ChevronRight,
  Video,
  MapPin,
  Phone,
  X
} from 'lucide-react';
import {
  getConversations,
  getConversation,
  getConversationMessages,
  sendConversationMessage,
  markConversationRead,
  uploadConversationAttachment,
  getAttachmentSignedUrl,
  scheduleMeeting,
  Conversation,
  ChatMessage,
  MessageAttachment
} from '@/lib/api';

function MessagesPageContent() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const initialConvId = searchParams.get('id');

  const [conversations, setConversations] = useState<Conversation[]>([]);
  const [selectedConversation, setSelectedConversation] = useState<Conversation | null>(null);
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [loadingConversations, setLoadingConversations] = useState(true);
  const [loadingMessages, setLoadingMessages] = useState(false);
  const [messageInput, setMessageInput] = useState('');
  const [sending, setSending] = useState(false);
  const [uploading, setUploading] = useState(false);
  const [filterType, setFilterType] = useState<'ALL' | 'LAWYER_CITIZEN' | 'CASE'>('ALL');
  const [error, setError] = useState<string | null>(null);
  const [currentUser, setCurrentUser] = useState<any>(null);

  // Meeting Schedule Modal state
  const [meetingModalOpen, setMeetingModalOpen] = useState(false);
  const [meetingMode, setMeetingMode] = useState<'ONLINE' | 'IN_PERSON' | 'PHONE'>('ONLINE');
  const [meetingStartDate, setMeetingStartDate] = useState('');
  const [meetingStartTime, setMeetingStartTime] = useState('');
  const [meetingDuration, setMeetingDuration] = useState(30);
  const [meetingAgenda, setMeetingAgenda] = useState('');
  const [meetingPhone, setMeetingPhone] = useState('');
  const [schedulingMeeting, setSchedulingMeeting] = useState(false);
  const [meetingSuccessMessage, setMeetingSuccessMessage] = useState<string | null>(null);

  const messagesEndRef = useRef<HTMLDivElement>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);

  // Load current user profile from localStorage
  useEffect(() => {
    if (typeof window !== 'undefined') {
      try {
        const u = localStorage.getItem('nyaypath_user');
        if (u) setCurrentUser(JSON.parse(u));
      } catch {}
    }
  }, []);

  // Fetch conversations list
  const loadConversations = async (selectId?: string) => {
    try {
      setError(null);
      const res = await getConversations();
      const list: Conversation[] = res.conversations || [];
      setConversations(list);

      const targetId = selectId || initialConvId;
      if (targetId) {
        const found = list.find((c) => c.id === targetId);
        if (found) {
          handleSelectConversation(found);
        } else if (list.length > 0 && !selectedConversation) {
          handleSelectConversation(list[0]);
        }
      } else if (list.length > 0 && !selectedConversation) {
        handleSelectConversation(list[0]);
      }
    } catch (err: any) {
      setError(err?.response?.data?.detail || 'Failed to load conversations.');
    } finally {
      setLoadingConversations(false);
    }
  };

  useEffect(() => {
    loadConversations();
  }, [initialConvId]);

  // Periodic polling for new messages & unread badges every 10 seconds
  useEffect(() => {
    const interval = setInterval(() => {
      if (selectedConversation) {
        loadMessages(selectedConversation.id, false);
      }
      getConversations().then((res) => {
        setConversations(res.conversations || []);
      }).catch(() => {});
    }, 10000);
    return () => clearInterval(interval);
  }, [selectedConversation]);

  // Scroll to bottom of message feed
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages]);

  const loadMessages = async (conversationId: string, showSpinner = true) => {
    if (showSpinner) setLoadingMessages(true);
    try {
      const res = await getConversationMessages(conversationId, { limit: 100 });
      setMessages(res.messages || []);
      // Mark read
      markConversationRead(conversationId).catch(() => {});
      // Update local unread indicator
      setConversations((prev) =>
        prev.map((c) => (c.id === conversationId ? { ...c, unread_count: 0 } : c))
      );
    } catch (err: any) {
      if (err?.response?.status === 403) {
        setError('Access to this conversation has been revoked or expired.');
      }
    } finally {
      if (showSpinner) setLoadingMessages(false);
    }
  };

  const handleSelectConversation = (conv: Conversation) => {
    setSelectedConversation(conv);
    loadMessages(conv.id, true);
  };

  const handleSendMessage = async (e?: React.FormEvent) => {
    if (e) e.preventDefault();
    if (!selectedConversation || !messageInput.trim() || sending) return;

    const body = messageInput.trim();
    const clientMessageId = `msg_${Date.now()}_${Math.random().toString(36).substring(2, 9)}`;

    setSending(true);
    try {
      const sentMsg = await sendConversationMessage(selectedConversation.id, {
        message_body: body,
        message_type: 'TEXT',
        client_message_id: clientMessageId
      });
      setMessageInput('');
      setMessages((prev) => [...prev, sentMsg]);
      // Update conversation last message in list
      setConversations((prev) =>
        prev.map((c) =>
          c.id === selectedConversation.id
            ? {
                ...c,
                last_message_preview: body.substring(0, 100),
                last_message_at: new Date().toISOString()
              }
            : c
        )
      );
    } catch (err: any) {
      alert(err?.response?.data?.detail || 'Failed to send message.');
    } finally {
      setSending(false);
    }
  };

  const handleFileUpload = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file || !selectedConversation) return;

    if (file.size > 10 * 1024 * 1024) {
      alert('Attachment exceeds the 10 MB maximum allowed limit.');
      return;
    }

    setUploading(true);
    try {
      const attachment = await uploadConversationAttachment(selectedConversation.id, file);
      // Refresh messages to show the attachment message
      await loadMessages(selectedConversation.id, false);
    } catch (err: any) {
      alert(err?.response?.data?.detail || 'Failed to upload attachment.');
    } finally {
      setUploading(false);
      if (fileInputRef.current) fileInputRef.current.value = '';
    }
  };

  const handleDownloadAttachment = async (attachmentId: string, filename: string) => {
    try {
      const res = await getAttachmentSignedUrl(attachmentId);
      if (res.signed_url) {
        window.open(res.signed_url, '_blank');
      }
    } catch (err: any) {
      alert(err?.response?.data?.detail || 'Failed to generate signed download link.');
    }
  };

  const handleOpenScheduleMeeting = () => {
    // Default to tomorrow 10:00 AM
    const tomorrow = new Date();
    tomorrow.setDate(tomorrow.getDate() + 1);
    const dateStr = tomorrow.toISOString().split('T')[0];
    setMeetingStartDate(dateStr);
    setMeetingStartTime('10:00');
    setMeetingDuration(30);
    setMeetingAgenda(selectedConversation?.title ? `Discussion regarding ${selectedConversation.title}` : 'Legal consultation session');
    setMeetingSuccessMessage(null);
    setMeetingModalOpen(true);
  };

  const handleSubmitMeeting = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!selectedConversation) return;

    // Determine lawyer participant
    const lawyerPart = selectedConversation.participants?.find(
      (p) => p.participant_role === 'LAWYER' || p.user_role === 'lawyer'
    ) || selectedConversation.other_participant;

    if (!lawyerPart?.user_id) {
      alert('Cannot determine counsel identity for appointment scheduling.');
      return;
    }

    try {
      setSchedulingMeeting(true);
      const startIso = new Date(`${meetingStartDate}T${meetingStartTime}:00Z`).toISOString();
      const endDt = new Date(new Date(startIso).getTime() + meetingDuration * 60 * 1000);
      const endIso = endDt.toISOString();

      await scheduleMeeting({
        consultation_request_id: selectedConversation.consultation_request_id,
        case_id: selectedConversation.case_id,
        lawyer_user_id: lawyerPart.user_id,
        scheduled_start: startIso,
        scheduled_end: endIso,
        meeting_mode: meetingMode,
        agenda: meetingAgenda,
        phone_contact: meetingMode === 'PHONE' ? meetingPhone : undefined
      });

      setMeetingSuccessMessage('Consultation appointment request submitted to counsel. You will be notified upon confirmation.');
      setTimeout(() => {
        setMeetingModalOpen(false);
        setMeetingSuccessMessage(null);
        if (selectedConversation) loadMessages(selectedConversation.id, false);
      }, 2500);
    } catch (err: any) {
      alert(err?.response?.data?.detail || 'Failed to schedule appointment. Time slot may be unavailable.');
    } finally {
      setSchedulingMeeting(false);
    }
  };

  const filteredConversations = conversations.filter((c) => {
    if (filterType === 'LAWYER_CITIZEN') return c.conversation_type === 'LAWYER_CITIZEN';
    if (filterType === 'CASE') return c.conversation_type === 'GENERAL_CASE' || c.conversation_type === 'INSTITUTION_CASE';
    return true;
  });

  return (
    <div className="min-h-screen bg-slate-50 pt-20 pb-8 font-sans">
      <div className="max-w-7xl mx-auto px-4 sm:px-6">
        {/* Breadcrumb / Top Bar */}
        <div className="mb-4 flex items-center justify-between text-xs text-slate-500">
          <div className="flex items-center gap-2">
            <Link href="/" className="hover:text-slate-800">Home</Link>
            <span>/</span>
            <Link href="/dashboard" className="hover:text-slate-800">Workspace</Link>
            <span>/</span>
            <span className="text-slate-700 font-semibold">Secure Communications</span>
          </div>
          <div className="flex items-center gap-2">
            <span className="inline-flex items-center gap-1 text-[11px] font-semibold text-emerald-700 bg-emerald-50 border border-emerald-200 px-2.5 py-0.5 rounded-full">
              <ShieldCheck className="w-3 h-3 text-emerald-600" />
              <span>End-to-End Privileged</span>
            </span>
          </div>
        </div>

        {/* Error Banner */}
        {error && (
          <div className="mb-4 p-3.5 bg-rose-50 border border-rose-200 rounded-xl text-xs text-rose-800 flex items-center gap-2">
            <AlertCircle className="w-4 h-4 text-rose-600 shrink-0" />
            <span>{error}</span>
          </div>
        )}

        {/* Main Communications Workspace: Split Pane */}
        <div className="bg-white rounded-2xl border border-slate-200 shadow-sm overflow-hidden grid grid-cols-1 md:grid-cols-12 min-h-[640px] max-h-[820px]">
          {/* Left Column: Conversations List (4 cols) */}
          <div className="md:col-span-4 border-r border-slate-200 flex flex-col bg-slate-50/50">
            {/* List Header */}
            <div className="p-4 border-b border-slate-200 bg-white">
              <div className="flex items-center justify-between mb-3">
                <h2 className="text-base font-serif font-bold text-slate-900 flex items-center gap-2">
                  <MessageSquare className="w-4 h-4 text-court-maroon" />
                  <span>Conversations</span>
                </h2>
                <button
                  onClick={() => loadConversations(selectedConversation?.id)}
                  title="Refresh Conversations"
                  className="p-1 text-slate-400 hover:text-slate-700 rounded-lg hover:bg-slate-100 transition-colors"
                >
                  <RefreshCw className="w-3.5 h-3.5" />
                </button>
              </div>

              {/* Filter Tabs */}
              <div className="flex items-center gap-1 p-1 bg-slate-100 rounded-xl text-[11px] font-bold">
                <button
                  onClick={() => setFilterType('ALL')}
                  className={`flex-1 py-1 px-2 rounded-lg transition-all ${
                    filterType === 'ALL'
                      ? 'bg-white text-slate-900 shadow-xs'
                      : 'text-slate-500 hover:text-slate-800'
                  }`}
                >
                  All ({conversations.length})
                </button>
                <button
                  onClick={() => setFilterType('LAWYER_CITIZEN')}
                  className={`flex-1 py-1 px-2 rounded-lg transition-all ${
                    filterType === 'LAWYER_CITIZEN'
                      ? 'bg-white text-slate-900 shadow-xs'
                      : 'text-slate-500 hover:text-slate-800'
                  }`}
                >
                  Counsel
                </button>
                <button
                  onClick={() => setFilterType('CASE')}
                  className={`flex-1 py-1 px-2 rounded-lg transition-all ${
                    filterType === 'CASE'
                      ? 'bg-white text-slate-900 shadow-xs'
                      : 'text-slate-500 hover:text-slate-800'
                  }`}
                >
                  Cases
                </button>
              </div>
            </div>

            {/* Conversation List Items */}
            <div className="flex-1 overflow-y-auto divide-y divide-slate-100">
              {loadingConversations ? (
                <div className="p-8 text-center">
                  <div className="w-6 h-6 border-2 border-court-maroon border-t-transparent rounded-full animate-spin mx-auto mb-2" />
                  <p className="text-xs text-slate-400">Loading chats...</p>
                </div>
              ) : filteredConversations.length === 0 ? (
                <div className="p-8 text-center text-slate-400 text-xs">
                  <MessageSquare className="w-8 h-8 text-slate-300 mx-auto mb-2" />
                  <p className="font-semibold text-slate-600">No conversations</p>
                  <p className="mt-1 text-[11px] leading-relaxed">
                    Conversations are automatically initialized when counsel accepts your consultation or when shared on a case.
                  </p>
                </div>
              ) : (
                filteredConversations.map((c) => {
                  const isSelected = selectedConversation?.id === c.id;
                  const other = c.other_participant;
                  const displayName = other?.full_name || (c.conversation_type === 'LAWYER_CITIZEN' ? 'Legal Counsel' : 'Case Discussion');
                  const roleLabel = other?.participant_role || (c.conversation_type === 'LAWYER_CITIZEN' ? 'ADVOCATE' : 'CASE');

                  return (
                    <div
                      key={c.id}
                      onClick={() => handleSelectConversation(c)}
                      className={`p-3.5 cursor-pointer transition-all flex items-start gap-3 text-left ${
                        isSelected
                          ? 'bg-white border-l-4 border-court-maroon shadow-xs'
                          : 'hover:bg-slate-100/70'
                      }`}
                    >
                      {/* Avatar */}
                      <div className="w-9 h-9 rounded-full bg-slate-200 border border-slate-300 flex items-center justify-center shrink-0 text-slate-700 font-bold text-xs uppercase">
                        {displayName.charAt(0)}
                      </div>

                      {/* Content */}
                      <div className="flex-1 min-w-0">
                        <div className="flex items-center justify-between gap-1 mb-1">
                          <h4 className="text-xs font-bold text-slate-900 truncate">
                            {displayName}
                          </h4>
                          {c.last_message_at && (
                            <span className="text-[10px] text-slate-400 shrink-0">
                              {new Date(c.last_message_at).toLocaleDateString([], { month: 'short', day: 'numeric' })}
                            </span>
                          )}
                        </div>

                        <div className="flex items-center gap-1.5 mb-1">
                          <span className={`text-[9px] font-bold px-1.5 py-0.2 rounded-full uppercase ${
                            roleLabel === 'LAWYER'
                              ? 'bg-purple-100 text-purple-800'
                              : roleLabel === 'PROCTOR'
                              ? 'bg-blue-100 text-blue-800'
                              : 'bg-slate-200 text-slate-700'
                          }`}>
                            {roleLabel}
                          </span>
                          {c.case_id && (
                            <span className="text-[10px] font-mono text-slate-400 truncate">
                              #{c.case_id}
                            </span>
                          )}
                        </div>

                        <p className="text-[11px] text-slate-500 truncate">
                          {c.last_message_preview || 'No messages yet.'}
                        </p>
                      </div>

                      {/* Unread Counter Badge */}
                      {Boolean(c.unread_count && c.unread_count > 0) && (
                        <span className="bg-court-maroon text-white text-[10px] font-bold px-1.5 py-0.5 rounded-full shrink-0">
                          {c.unread_count}
                        </span>
                      )}
                    </div>
                  );
                })
              )}
            </div>
          </div>

          {/* Right Column: Chat View & Feed (8 cols) */}
          <div className="md:col-span-8 flex flex-col bg-white">
            {selectedConversation ? (
              <>
                {/* Chat Top Header */}
                <div className="p-4 border-b border-slate-200 flex items-center justify-between gap-3 bg-white">
                  <div className="flex items-center gap-3 min-w-0">
                    <div className="w-10 h-10 rounded-full bg-slate-900 text-amber-300 flex items-center justify-center font-bold text-sm shrink-0">
                      {(selectedConversation.other_participant?.full_name || 'C').charAt(0)}
                    </div>
                    <div className="min-w-0">
                      <div className="flex items-center gap-2">
                        <h3 className="text-sm font-bold text-slate-900 truncate">
                          {selectedConversation.other_participant?.full_name ||
                            (selectedConversation.conversation_type === 'LAWYER_CITIZEN' ? 'Legal Counsel' : 'Case Channel')}
                        </h3>
                        <span className="text-[10px] font-bold px-2 py-0.5 rounded-full bg-slate-100 text-slate-600 border border-slate-200">
                          {selectedConversation.conversation_type}
                        </span>
                      </div>
                      <div className="flex items-center gap-2 text-[11px] text-slate-500 mt-0.5">
                        {selectedConversation.case_id && (
                          <span className="font-mono text-court-maroon font-semibold">
                            Case: {selectedConversation.case_id}
                          </span>
                        )}
                        <span>â€¢</span>
                        <span className="text-emerald-700 flex items-center gap-1">
                          <span className="w-1.5 h-1.5 rounded-full bg-emerald-500 animate-pulse" />
                          <span>Active Consultation Session</span>
                        </span>
                      </div>
                    </div>
                  </div>

                  {/* Header Actions */}
                  <div className="flex items-center gap-2 shrink-0">
                    {/* Schedule Meeting CTA */}
                    <button
                      onClick={handleOpenScheduleMeeting}
                      className="px-3 py-1.5 bg-slate-900 hover:bg-slate-800 text-amber-300 rounded-xl text-xs font-bold uppercase tracking-wider transition-all flex items-center gap-1.5 shadow-xs cursor-pointer"
                    >
                      <Calendar size={13} className="text-amber-300" />
                      <span>Schedule Meeting</span>
                    </button>

                    {selectedConversation.case_id && (
                      <Link
                        href={`/dashboard/my-cases?case_id=${encodeURIComponent(selectedConversation.case_id)}`}
                        className="p-2 text-slate-500 hover:text-slate-800 rounded-lg hover:bg-slate-100"
                        title="View Linked Case"
                      >
                        <ExternalLink size={15} />
                      </Link>
                    )}
                  </div>
                </div>

                {/* Messages Feed */}
                <div className="flex-1 p-4 sm:p-6 overflow-y-auto space-y-4 bg-slate-50/40">
                  {loadingMessages ? (
                    <div className="py-20 text-center">
                      <div className="w-8 h-8 border-3 border-court-maroon border-t-transparent rounded-full animate-spin mx-auto mb-2" />
                      <p className="text-xs text-slate-400">Loading conversation history...</p>
                    </div>
                  ) : messages.length === 0 ? (
                    <div className="py-20 text-center text-slate-400">
                      <ShieldCheck className="w-10 h-10 text-slate-300 mx-auto mb-2" />
                      <p className="text-sm font-semibold text-slate-700">Encrypted Privileged Channel</p>
                      <p className="text-xs max-w-sm mx-auto mt-1 text-slate-500">
                        This channel is restricted to authorized case participants. Send a message to initiate communication with counsel.
                      </p>
                    </div>
                  ) : (
                    messages.map((m) => {
                      const isMe = currentUser?.id && m.sender_user_id === currentUser.id;

                      return (
                        <div
                          key={m.id}
                          className={`flex flex-col ${isMe ? 'items-end' : 'items-start'}`}
                        >
                          <div className="flex items-center gap-1.5 mb-1 px-1">
                            <span className="text-[10px] font-bold text-slate-500">
                              {isMe ? 'You' : m.sender_name || 'Counsel'}
                            </span>
                            <span className="text-[9px] text-slate-400">
                              {new Date(m.created_at).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}
                            </span>
                          </div>

                          {/* Message Body */}
                          <div
                            className={`max-w-lg rounded-2xl p-3.5 text-xs shadow-xs leading-relaxed whitespace-pre-line ${
                              isMe
                                ? 'bg-court-maroon text-white rounded-tr-xs'
                                : 'bg-white border border-slate-200 text-slate-800 rounded-tl-xs'
                            }`}
                          >
                            <p>{m.message_body}</p>

                            {/* Attachments if any */}
                            {m.attachments && m.attachments.length > 0 && (
                              <div className="mt-3 space-y-2 pt-2 border-t border-white/20">
                                {m.attachments.map((att) => (
                                  <div
                                    key={att.id}
                                    className={`flex items-center justify-between gap-3 p-2 rounded-xl text-xs ${
                                      isMe ? 'bg-rose-900/40 text-rose-100' : 'bg-slate-100 text-slate-800'
                                    }`}
                                  >
                                    <div className="flex items-center gap-2 min-w-0">
                                      <FileText className="w-4 h-4 shrink-0 text-amber-300" />
                                      <div className="truncate">
                                        <p className="font-bold truncate">{att.file_name}</p>
                                        <p className="text-[10px] opacity-75">
                                          {(att.file_size_bytes / 1024).toFixed(1)} KB â€¢ Privileged
                                        </p>
                                      </div>
                                    </div>
                                    <button
                                      onClick={() => handleDownloadAttachment(att.id, att.file_name)}
                                      className="p-1 hover:bg-black/10 rounded-lg transition-colors cursor-pointer"
                                      title="Download attachment (signed link valid for 300s)"
                                    >
                                      <Download className="w-4 h-4" />
                                    </button>
                                  </div>
                                ))}
                              </div>
                            )}
                          </div>
                        </div>
                      );
                    })
                  )}
                  <div ref={messagesEndRef} />
                </div>

                {/* Input Toolbar & Compose Bar */}
                <div className="p-3 sm:p-4 border-t border-slate-200 bg-white">
                  <form onSubmit={handleSendMessage} className="space-y-2">
                    <div className="flex items-center gap-2">
                      {/* Hidden File Input */}
                      <input
                        type="file"
                        ref={fileInputRef}
                        onChange={handleFileUpload}
                        className="hidden"
                        accept="application/pdf,image/png,image/jpeg,image/webp"
                      />

                      {/* Attach Button */}
                      <button
                        type="button"
                        onClick={() => fileInputRef.current?.click()}
                        disabled={uploading}
                        className="p-2.5 text-slate-500 hover:text-slate-800 hover:bg-slate-100 rounded-xl transition-all cursor-pointer border border-slate-200"
                        title="Upload document attachment (PDF, PNG, JPG <= 10MB)"
                      >
                        {uploading ? (
                          <div className="w-4 h-4 border-2 border-slate-600 border-t-transparent rounded-full animate-spin" />
                        ) : (
                          <Paperclip className="w-4 h-4" />
                        )}
                      </button>

                      {/* Message Input Box */}
                      <input
                        type="text"
                        value={messageInput}
                        onChange={(e) => setMessageInput(e.target.value)}
                        placeholder="Write a message to legal counsel... (Enter to send)"
                        maxLength={4000}
                        className="flex-1 px-4 py-2.5 bg-slate-50 border border-slate-200 rounded-xl text-xs text-slate-900 focus:outline-none focus:ring-2 focus:ring-court-maroon/20 focus:border-court-maroon transition-all"
                      />

                      {/* Send Button */}
                      <button
                        type="submit"
                        disabled={!messageInput.trim() || sending}
                        className="px-4 py-2.5 bg-court-maroon hover:bg-rose-700 disabled:opacity-40 text-white rounded-xl text-xs font-bold uppercase tracking-wider transition-all flex items-center gap-1.5 shadow-sm cursor-pointer"
                      >
                        {sending ? (
                          <div className="w-4 h-4 border-2 border-white border-t-transparent rounded-full animate-spin" />
                        ) : (
                          <>
                            <span>Send</span>
                            <Send size={12} />
                          </>
                        )}
                      </button>
                    </div>
                    <div className="flex items-center justify-between px-1 text-[10px] text-slate-400">
                      <span>Attachments stored in private encrypted bucket (max 10MB). Signed URLs valid for 5 mins.</span>
                      <span>{messageInput.length} / 4000</span>
                    </div>
                  </form>
                </div>
              </>
            ) : (
              <div className="flex-1 flex flex-col items-center justify-center p-8 text-center text-slate-400">
                <MessageSquare className="w-12 h-12 text-slate-200 mb-3" />
                <h3 className="font-serif font-bold text-base text-slate-700">Select a Conversation</h3>
                <p className="text-xs text-slate-400 max-w-sm mt-1">
                  Choose a conversation from the left to view messages, share evidence documents, or schedule consultation appointments.
                </p>
              </div>
            )}
          </div>
        </div>

        {/* Schedule Consultation Meeting Modal */}
        {meetingModalOpen && (
          <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-xs p-4">
            <div className="bg-white rounded-2xl max-w-md w-full p-6 shadow-2xl border border-slate-200">
              <div className="flex items-center justify-between mb-4">
                <div className="flex items-center gap-2">
                  <div className="p-2 bg-amber-100 text-amber-900 rounded-xl">
                    <Calendar className="w-4 h-4" />
                  </div>
                  <div>
                    <h3 className="font-serif font-bold text-sm text-slate-900">Schedule Consultation</h3>
                    <p className="text-[11px] text-slate-500">Book an appointment with legal counsel</p>
                  </div>
                </div>
                <button
                  onClick={() => setMeetingModalOpen(false)}
                  className="p-1 text-slate-400 hover:text-slate-700 rounded-lg"
                >
                  <X className="w-4 h-4" />
                </button>
              </div>

              {meetingSuccessMessage ? (
                <div className="p-4 bg-emerald-50 border border-emerald-200 rounded-xl text-xs text-emerald-800 flex items-center gap-2">
                  <ShieldCheck className="w-5 h-5 text-emerald-600 shrink-0" />
                  <span>{meetingSuccessMessage}</span>
                </div>
              ) : (
                <form onSubmit={handleSubmitMeeting} className="space-y-3.5 text-xs">
                  {/* Mode Selector */}
                  <div>
                    <label className="block font-bold text-slate-700 mb-1">Consultation Mode</label>
                    <div className="grid grid-cols-3 gap-2">
                      {(['ONLINE', 'IN_PERSON', 'PHONE'] as const).map((mode) => (
                        <button
                          key={mode}
                          type="button"
                          onClick={() => setMeetingMode(mode)}
                          className={`py-2 px-3 rounded-xl font-bold uppercase text-[10px] border flex items-center justify-center gap-1.5 transition-all ${
                            meetingMode === mode
                              ? 'bg-slate-900 text-amber-300 border-slate-900 shadow-xs'
                              : 'bg-slate-50 text-slate-600 border-slate-200 hover:bg-slate-100'
                          }`}
                        >
                          {mode === 'ONLINE' && <Video size={12} />}
                          {mode === 'IN_PERSON' && <MapPin size={12} />}
                          {mode === 'PHONE' && <Phone size={12} />}
                          <span>{mode.replace('_', ' ')}</span>
                        </button>
                      ))}
                    </div>
                  </div>

                  {/* Date & Time */}
                  <div className="grid grid-cols-2 gap-2">
                    <div>
                      <label className="block font-bold text-slate-700 mb-1">Date</label>
                      <input
                        type="date"
                        required
                        value={meetingStartDate}
                        onChange={(e) => setMeetingStartDate(e.target.value)}
                        className="w-full px-3 py-2 bg-slate-50 border border-slate-200 rounded-xl text-xs text-slate-900 focus:outline-none focus:ring-1 focus:ring-court-maroon"
                      />
                    </div>
                    <div>
                      <label className="block font-bold text-slate-700 mb-1">Start Time (UTC/Local)</label>
                      <input
                        type="time"
                        required
                        value={meetingStartTime}
                        onChange={(e) => setMeetingStartTime(e.target.value)}
                        className="w-full px-3 py-2 bg-slate-50 border border-slate-200 rounded-xl text-xs text-slate-900 focus:outline-none focus:ring-1 focus:ring-court-maroon"
                      />
                    </div>
                  </div>

                  {/* Duration */}
                  <div>
                    <label className="block font-bold text-slate-700 mb-1">Duration</label>
                    <select
                      value={meetingDuration}
                      onChange={(e) => setMeetingDuration(Number(e.target.value))}
                      className="w-full px-3 py-2 bg-slate-50 border border-slate-200 rounded-xl text-xs text-slate-900 focus:outline-none focus:ring-1 focus:ring-court-maroon"
                    >
                      <option value={15}>15 Minutes (Brief Assessment)</option>
                      <option value={30}>30 Minutes (Standard Consultation)</option>
                      <option value={45}>45 Minutes (Detailed Case Review)</option>
                      <option value={60}>60 Minutes (Full Strategy Session)</option>
                    </select>
                  </div>

                  {/* Phone number if Phone mode */}
                  {meetingMode === 'PHONE' && (
                    <div>
                      <label className="block font-bold text-slate-700 mb-1">Citizen Contact Phone</label>
                      <input
                        type="tel"
                        required
                        placeholder="+91 98765 43210"
                        value={meetingPhone}
                        onChange={(e) => setMeetingPhone(e.target.value)}
                        className="w-full px-3 py-2 bg-slate-50 border border-slate-200 rounded-xl text-xs text-slate-900 focus:outline-none focus:ring-1 focus:ring-court-maroon"
                      />
                    </div>
                  )}

                  {/* Agenda */}
                  <div>
                    <label className="block font-bold text-slate-700 mb-1">Session Agenda & Discussion Topics</label>
                    <textarea
                      rows={2}
                      value={meetingAgenda}
                      onChange={(e) => setMeetingAgenda(e.target.value)}
                      placeholder="Outline specific legal questions, evidence to review, or court milestones..."
                      className="w-full px-3 py-2 bg-slate-50 border border-slate-200 rounded-xl text-xs text-slate-900 focus:outline-none focus:ring-1 focus:ring-court-maroon"
                    />
                  </div>

                  <p className="text-[10px] text-slate-400">
                    Online video meeting links, chamber address, or dial-in credentials remain masked and will be unlocked once counsel confirms this appointment.
                  </p>

                  <div className="flex items-center justify-end gap-2 pt-2">
                    <button
                      type="button"
                      onClick={() => setMeetingModalOpen(false)}
                      className="px-4 py-2 bg-slate-100 hover:bg-slate-200 text-slate-700 rounded-xl text-xs font-bold uppercase transition-all"
                    >
                      Cancel
                    </button>
                    <button
                      type="submit"
                      disabled={schedulingMeeting}
                      className="px-5 py-2 bg-court-maroon hover:bg-rose-700 text-white rounded-xl text-xs font-bold uppercase tracking-wider transition-all flex items-center gap-1.5 shadow-sm"
                    >
                      {schedulingMeeting ? (
                        <div className="w-3.5 h-3.5 border-2 border-white border-t-transparent rounded-full animate-spin" />
                      ) : (
                        <>
                          <Calendar size={13} />
                          <span>Submit Request</span>
                        </>
                      )}
                    </button>
                  </div>
                </form>
              )}
            </div>
          </div>
        )}
      </div>
    </div>
  );
}

export default function MessagesPage() {
  return (
    <React.Suspense
      fallback={
        <div className="min-h-screen flex items-center justify-center bg-gray-900 text-gray-400">
          <div className="w-8 h-8 border-4 border-indigo-500 border-t-transparent rounded-full animate-spin mr-3" />
          Loading Conversations...
        </div>
      }
    >
      <MessagesPageContent />
    </React.Suspense>
  );
}


