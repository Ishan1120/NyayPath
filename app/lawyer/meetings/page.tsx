'use client';

import React, { useState, useEffect } from 'react';
import Link from 'next/link';
import { useRouter } from 'next/navigation';
import {
  Calendar,
  Clock,
  CheckCircle2,
  XCircle,
  AlertCircle,
  Video,
  MapPin,
  Phone,
  User,
  Scale,
  Gavel,
  ChevronRight,
  MessageSquare,
  Settings,
  RefreshCw,
  Plus,
  Trash2,
  ShieldCheck,
  Check
} from 'lucide-react';
import {
  getUserMeetings,
  updateMeetingStatus,
  getLawyerAvailability,
  updateLawyerAvailability,
  ConsultationMeeting,
  LawyerAvailability
} from '@/lib/api';

export default function LawyerMeetingsPage() {
  const router = useRouter();

  const [meetings, setMeetings] = useState<ConsultationMeeting[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [actionSuccess, setActionSuccess] = useState<string | null>(null);
  const [activeTab, setActiveTab] = useState<'UPCOMING' | 'PAST' | 'AVAILABILITY'>('UPCOMING');

  // Confirmation Modal
  const [confirmModalMeeting, setConfirmModalMeeting] = useState<ConsultationMeeting | null>(null);
  const [meetingUrlInput, setMeetingUrlInput] = useState('');
  const [locationInput, setLocationInput] = useState('');
  const [phoneInput, setPhoneInput] = useState('');
  const [confirmNotes, setConfirmNotes] = useState('');
  const [updatingStatus, setUpdatingStatus] = useState(false);

  // Decline Modal
  const [declineModalMeeting, setDeclineModalMeeting] = useState<ConsultationMeeting | null>(null);
  const [declineNotes, setDeclineNotes] = useState('');

  // Availability Settings
  const [availability, setAvailability] = useState<LawyerAvailability>({
    lawyer_user_id: '',
    available_days: [1, 2, 3, 4, 5],
    start_time_utc: '04:30:00',
    end_time_utc: '12:30:00',
    slot_duration_minutes: 30,
    timezone: 'Asia/Kolkata',
    unavailable_dates: []
  });
  const [loadingAvailability, setLoadingAvailability] = useState(false);
  const [savingAvailability, setSavingAvailability] = useState(false);
  const [newBlackoutDate, setNewBlackoutDate] = useState('');

  const loadData = async () => {
    setLoading(true);
    try {
      setError(null);
      const res = await getUserMeetings();
      setMeetings(res.meetings || []);

      // Load availability for current lawyer
      const userStr = typeof window !== 'undefined' ? localStorage.getItem('nyaypath_user') : null;
      if (userStr) {
        const u = JSON.parse(userStr);
        if (u.id) {
          try {
            const availRes = await getLawyerAvailability(u.id);
            if (availRes) setAvailability(availRes);
          } catch {}
        }
      }
    } catch (err: any) {
      setError(err?.response?.data?.detail || 'Failed to load appointments.');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadData();
  }, []);

  const handleOpenConfirmModal = (m: ConsultationMeeting) => {
    setConfirmModalMeeting(m);
    setMeetingUrlInput(m.meeting_mode === 'ONLINE' ? 'https://nyaypath.gov.in/consultation-room/' + m.id.substring(0, 8) : '');
    setLocationInput(m.meeting_mode === 'IN_PERSON' ? 'Chamber No. 42, High Court Complex' : '');
    setPhoneInput(m.phone_contact || '');
    setConfirmNotes('Appointment confirmed. Please arrive on time.');
  };

  const handleConfirmMeeting = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!confirmModalMeeting) return;

    setUpdatingStatus(true);
    try {
      await updateMeetingStatus(confirmModalMeeting.id, {
        status: 'CONFIRMED',
        notes: confirmNotes,
        online_meeting_url: confirmModalMeeting.meeting_mode === 'ONLINE' ? meetingUrlInput : undefined,
        location_details: confirmModalMeeting.meeting_mode === 'IN_PERSON' ? locationInput : undefined,
        phone_contact: confirmModalMeeting.meeting_mode === 'PHONE' ? phoneInput : undefined
      });
      setActionSuccess('Appointment confirmed successfully! Notification dispatched to citizen.');
      setConfirmModalMeeting(null);
      await loadData();
    } catch (err: any) {
      alert(err?.response?.data?.detail || 'Failed to confirm appointment.');
    } finally {
      setUpdatingStatus(false);
    }
  };

  const handleDeclineMeeting = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!declineModalMeeting) return;

    setUpdatingStatus(true);
    try {
      await updateMeetingStatus(declineModalMeeting.id, {
        status: 'DECLINED',
        notes: declineNotes || 'Counsel is unavailable during the requested time slot.'
      });
      setActionSuccess('Appointment request declined.');
      setDeclineModalMeeting(null);
      await loadData();
    } catch (err: any) {
      alert(err?.response?.data?.detail || 'Failed to decline appointment.');
    } finally {
      setUpdatingStatus(false);
    }
  };

  const handleMarkCompleted = async (meetingId: string) => {
    if (!confirm('Mark this consultation session as concluded?')) return;
    try {
      await updateMeetingStatus(meetingId, { status: 'COMPLETED' });
      setActionSuccess('Consultation marked as completed.');
      await loadData();
    } catch (err: any) {
      alert(err?.response?.data?.detail || 'Failed to update meeting status.');
    }
  };

  const handleSaveAvailability = async (e: React.FormEvent) => {
    e.preventDefault();
    setSavingAvailability(true);
    try {
      await updateLawyerAvailability(availability);
      setActionSuccess('Practice availability schedule and blackout dates saved successfully.');
    } catch (err: any) {
      alert(err?.response?.data?.detail || 'Failed to update availability.');
    } finally {
      setSavingAvailability(false);
    }
  };

  const handleToggleDay = (dayNum: number) => {
    setAvailability((prev) => {
      const exists = prev.available_days.includes(dayNum);
      const nextDays = exists
        ? prev.available_days.filter((d) => d !== dayNum)
        : [...prev.available_days, dayNum].sort();
      return { ...prev, available_days: nextDays };
    });
  };

  const handleAddBlackoutDate = () => {
    if (!newBlackoutDate) return;
    if (availability.unavailable_dates.includes(newBlackoutDate)) return;
    setAvailability((prev) => ({
      ...prev,
      unavailable_dates: [...prev.unavailable_dates, newBlackoutDate].sort()
    }));
    setNewBlackoutDate('');
  };

  const handleRemoveBlackoutDate = (dt: string) => {
    setAvailability((prev) => ({
      ...prev,
      unavailable_dates: prev.unavailable_dates.filter((d) => d !== dt)
    }));
  };

  const getStatusBadge = (st: string) => {
    switch (st) {
      case 'CONFIRMED':
        return (
          <span className="inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full text-[11px] font-bold bg-emerald-50 text-emerald-700 border border-emerald-200">
            <CheckCircle2 className="w-3 h-3 text-emerald-600" />
            <span>CONFIRMED</span>
          </span>
        );
      case 'REQUESTED':
        return (
          <span className="inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full text-[11px] font-bold bg-amber-50 text-amber-700 border border-amber-200">
            <Clock className="w-3 h-3 text-amber-600" />
            <span>PENDING CONFIRMATION</span>
          </span>
        );
      case 'DECLINED':
        return (
          <span className="inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full text-[11px] font-bold bg-rose-50 text-rose-700 border border-rose-200">
            <XCircle className="w-3 h-3" />
            <span>DECLINED</span>
          </span>
        );
      case 'COMPLETED':
        return (
          <span className="inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full text-[11px] font-bold bg-blue-50 text-blue-700 border border-blue-200">
            <CheckCircle2 className="w-3 h-3" />
            <span>CONCLUDED</span>
          </span>
        );
      case 'CANCELLED':
        return (
          <span className="inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full text-[11px] font-bold bg-slate-100 text-slate-600 border border-slate-200">
            <span>CANCELLED</span>
          </span>
        );
      default:
        return (
          <span className="inline-flex items-center px-2.5 py-0.5 rounded-full text-[11px] font-bold bg-slate-100 text-slate-700">
            {st}
          </span>
        );
    }
  };

  const upcomingMeetings = meetings.filter((m) => m.status === 'REQUESTED' || m.status === 'CONFIRMED');
  const pastMeetings = meetings.filter((m) => m.status === 'COMPLETED' || m.status === 'DECLINED' || m.status === 'CANCELLED');

  const pendingCount = meetings.filter((m) => m.status === 'REQUESTED').length;
  const confirmedCount = meetings.filter((m) => m.status === 'CONFIRMED').length;
  const completedCount = meetings.filter((m) => m.status === 'COMPLETED').length;

  const daysOfWeek = [
    { num: 1, label: 'Mon' },
    { num: 2, label: 'Tue' },
    { num: 3, label: 'Wed' },
    { num: 4, label: 'Thu' },
    { num: 5, label: 'Fri' },
    { num: 6, label: 'Sat' },
    { num: 7, label: 'Sun' }
  ];

  return (
    <div className="min-h-screen bg-slate-50 pt-24 pb-16 font-sans">
      <div className="max-w-6xl mx-auto px-4 sm:px-6">
        {/* Breadcrumb */}
        <div className="mb-6 flex items-center justify-between text-xs text-slate-500">
          <div className="flex items-center gap-2">
            <Link href="/" className="hover:text-slate-800">Home</Link>
            <span>/</span>
            <Link href="/lawyer/dashboard" className="hover:text-slate-800">Lawyer Desk</Link>
            <span>/</span>
            <span className="text-slate-700 font-semibold">Appointments & Practice Calendar</span>
          </div>
          <div className="flex items-center gap-2">
            <span className="inline-flex items-center gap-1 text-[11px] font-semibold text-emerald-700 bg-emerald-50 border border-emerald-200 px-2.5 py-0.5 rounded-full">
              <ShieldCheck className="w-3 h-3 text-emerald-600" />
              <span>Privileged Appointments</span>
            </span>
          </div>
        </div>

        {/* Header */}
        <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4 mb-6">
          <div>
            <div className="flex items-center gap-2 mb-1">
              <span className="inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full text-[11px] font-bold bg-slate-900 text-amber-300">
                <Gavel className="w-3 h-3 text-amber-300" />
                <span>Counsel Desk</span>
              </span>
            </div>
            <h1 className="text-2xl sm:text-3xl font-serif font-bold text-slate-900">
              Appointments & Practice Calendar
            </h1>
            <p className="text-xs text-slate-500 mt-1">
              Manage citizen consultation bookings, configure practice hours, and set courtroom blackout dates.
            </p>
          </div>

          <div className="flex items-center gap-2">
            <button
              onClick={loadData}
              disabled={loading}
              className="px-4 py-2 bg-white border border-slate-200 hover:bg-slate-50 text-slate-700 rounded-xl text-xs font-bold transition-all flex items-center gap-1.5 shadow-xs cursor-pointer"
            >
              <RefreshCw size={13} className={loading ? 'animate-spin' : ''} />
              <span>Refresh</span>
            </button>
            <Link
              href="/messages"
              className="px-4 py-2 bg-court-maroon hover:bg-rose-700 text-white rounded-xl text-xs font-bold uppercase tracking-wider transition-all flex items-center gap-1.5 shadow-sm"
            >
              <MessageSquare size={13} />
              <span>Messages</span>
            </Link>
          </div>
        </div>

        {/* Notifications / Alerts */}
        {error && (
          <div className="mb-6 p-4 bg-rose-50 border border-rose-200 rounded-2xl text-xs text-rose-800 flex items-center gap-2">
            <AlertCircle className="w-4 h-4 text-rose-600 shrink-0" />
            <span>{error}</span>
          </div>
        )}

        {actionSuccess && (
          <div className="mb-6 p-4 bg-emerald-50 border border-emerald-200 rounded-2xl text-xs text-emerald-800 flex items-center justify-between">
            <div className="flex items-center gap-2">
              <CheckCircle2 className="w-4 h-4 text-emerald-600 shrink-0" />
              <span>{actionSuccess}</span>
            </div>
            <button onClick={() => setActionSuccess(null)} className="text-emerald-700 font-bold hover:underline">
              Dismiss
            </button>
          </div>
        )}

        {/* Stats Row */}
        <div className="grid grid-cols-1 sm:grid-cols-3 gap-4 mb-6">
          <div className="bg-white rounded-2xl border border-slate-200 p-5 shadow-xs">
            <div className="flex items-center justify-between">
              <span className="text-xs font-bold text-slate-500 uppercase tracking-wider">Pending Review</span>
              <div className="p-2 bg-amber-50 rounded-xl text-amber-700">
                <Clock className="w-4 h-4" />
              </div>
            </div>
            <p className="text-2xl font-serif font-bold text-slate-900 mt-2">{pendingCount}</p>
            <p className="text-[11px] text-slate-400 mt-0.5">Citizen consultation booking requests</p>
          </div>

          <div className="bg-white rounded-2xl border border-slate-200 p-5 shadow-xs">
            <div className="flex items-center justify-between">
              <span className="text-xs font-bold text-slate-500 uppercase tracking-wider">Confirmed</span>
              <div className="p-2 bg-emerald-50 rounded-xl text-emerald-700">
                <CheckCircle2 className="w-4 h-4" />
              </div>
            </div>
            <p className="text-2xl font-serif font-bold text-slate-900 mt-2">{confirmedCount}</p>
            <p className="text-[11px] text-slate-400 mt-0.5">Scheduled appointments upcoming</p>
          </div>

          <div className="bg-white rounded-2xl border border-slate-200 p-5 shadow-xs">
            <div className="flex items-center justify-between">
              <span className="text-xs font-bold text-slate-500 uppercase tracking-wider">Concluded</span>
              <div className="p-2 bg-blue-50 rounded-xl text-blue-700">
                <Calendar className="w-4 h-4" />
              </div>
            </div>
            <p className="text-2xl font-serif font-bold text-slate-900 mt-2">{completedCount}</p>
            <p className="text-[11px] text-slate-400 mt-0.5">Completed legal consultations</p>
          </div>
        </div>

        {/* View Tabs */}
        <div className="flex items-center gap-2 mb-6 border-b border-slate-200 text-xs font-bold">
          <button
            onClick={() => setActiveTab('UPCOMING')}
            className={`pb-3 px-3 transition-all flex items-center gap-1.5 ${
              activeTab === 'UPCOMING'
                ? 'border-b-2 border-court-maroon text-court-maroon'
                : 'text-slate-500 hover:text-slate-800'
            }`}
          >
            <Clock size={14} />
            <span>Upcoming & Pending ({upcomingMeetings.length})</span>
          </button>
          <button
            onClick={() => setActiveTab('PAST')}
            className={`pb-3 px-3 transition-all flex items-center gap-1.5 ${
              activeTab === 'PAST'
                ? 'border-b-2 border-court-maroon text-court-maroon'
                : 'text-slate-500 hover:text-slate-800'
            }`}
          >
            <CheckCircle2 size={14} />
            <span>Past & Concluded ({pastMeetings.length})</span>
          </button>
          <button
            onClick={() => setActiveTab('AVAILABILITY')}
            className={`pb-3 px-3 transition-all flex items-center gap-1.5 ${
              activeTab === 'AVAILABILITY'
                ? 'border-b-2 border-court-maroon text-court-maroon'
                : 'text-slate-500 hover:text-slate-800'
            }`}
          >
            <Settings size={14} />
            <span>Practice Availability & Blackouts</span>
          </button>
        </div>

        {/* Tab 1: Upcoming & Pending Appointments */}
        {activeTab === 'UPCOMING' && (
          <div>
            {loading ? (
              <div className="py-20 text-center">
                <div className="w-8 h-8 border-3 border-court-maroon border-t-transparent rounded-full animate-spin mx-auto mb-3" />
                <p className="text-xs text-slate-400">Loading appointments...</p>
              </div>
            ) : upcomingMeetings.length === 0 ? (
              <div className="bg-white rounded-2xl border border-slate-200 p-12 text-center text-slate-400">
                <Calendar className="w-10 h-10 text-slate-300 mx-auto mb-3" />
                <h3 className="font-serif font-bold text-base text-slate-700">No Upcoming Appointments</h3>
                <p className="text-xs text-slate-400 max-w-sm mx-auto mt-1">
                  Citizens who request consultation sessions with your chambers will appear here for review and confirmation.
                </p>
              </div>
            ) : (
              <div className="space-y-4">
                {upcomingMeetings.map((m) => (
                  <div
                    key={m.id}
                    className="bg-white rounded-2xl border border-slate-200 p-5 sm:p-6 shadow-xs transition-all hover:border-slate-300"
                  >
                    <div className="flex flex-col lg:flex-row lg:items-start justify-between gap-4">
                      {/* Left Details */}
                      <div className="flex-1">
                        <div className="flex flex-wrap items-center gap-2 mb-2">
                          {getStatusBadge(m.status)}
                          <span className="text-xs font-bold text-slate-900">
                            Citizen Requester: {m.citizen_profile?.full_name || 'Client'}
                          </span>
                          <span className="text-[11px] font-bold text-indigo-700 bg-indigo-50 border border-indigo-200 px-2 py-0.5 rounded-full flex items-center gap-1">
                            {m.meeting_mode === 'ONLINE' && <Video size={11} />}
                            {m.meeting_mode === 'IN_PERSON' && <MapPin size={11} />}
                            {m.meeting_mode === 'PHONE' && <Phone size={11} />}
                            <span>{m.meeting_mode.replace('_', ' ')}</span>
                          </span>
                        </div>

                        {/* Date & Time */}
                        <div className="flex items-center gap-4 text-xs text-slate-600 mb-2">
                          <span className="flex items-center gap-1 font-semibold text-slate-800">
                            <Calendar size={13} className="text-court-maroon" />
                            {new Date(m.scheduled_start).toLocaleDateString([], {
                              weekday: 'short',
                              year: 'numeric',
                              month: 'short',
                              day: 'numeric'
                            })}
                          </span>
                          <span className="flex items-center gap-1">
                            <Clock size={13} className="text-slate-400" />
                            {new Date(m.scheduled_start).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}
                            {' â€“ '}
                            {new Date(m.scheduled_end).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}
                          </span>
                        </div>

                        {/* Agenda */}
                        {m.agenda && (
                          <p className="text-xs text-slate-600 bg-slate-50 p-3 rounded-xl border border-slate-100 mb-3">
                            <span className="font-bold text-slate-700">Agenda: </span>
                            {m.agenda}
                          </p>
                        )}

                        {/* Confirmed Details if Confirmed */}
                        {m.status === 'CONFIRMED' && (
                          <div className="p-3 bg-emerald-50/60 border border-emerald-200 rounded-xl text-xs text-emerald-900 space-y-1">
                            {m.online_meeting_url && (
                              <p className="flex items-center gap-1.5">
                                <Video size={13} className="text-emerald-700 shrink-0" />
                                <span className="font-bold">Meeting URL:</span>
                                <a href={m.online_meeting_url} target="_blank" rel="noopener noreferrer" className="underline font-mono">
                                  {m.online_meeting_url}
                                </a>
                              </p>
                            )}
                            {m.location_details && (
                              <p className="flex items-center gap-1.5">
                                <MapPin size={13} className="text-emerald-700 shrink-0" />
                                <span className="font-bold">Chambers / Location:</span>
                                <span>{m.location_details}</span>
                              </p>
                            )}
                            {m.phone_contact && (
                              <p className="flex items-center gap-1.5">
                                <Phone size={13} className="text-emerald-700 shrink-0" />
                                <span className="font-bold">Contact Phone:</span>
                                <span>{m.phone_contact}</span>
                              </p>
                            )}
                          </div>
                        )}
                      </div>

                      {/* Right Action Buttons */}
                      <div className="flex sm:flex-col gap-2 shrink-0">
                        {m.status === 'REQUESTED' && (
                          <>
                            <button
                              onClick={() => handleOpenConfirmModal(m)}
                              className="px-4 py-2 bg-emerald-700 hover:bg-emerald-800 text-white rounded-xl text-xs font-bold uppercase tracking-wider transition-all flex items-center gap-1.5 shadow-sm cursor-pointer"
                            >
                              <Check size={13} />
                              <span>Confirm Appointment</span>
                            </button>
                            <button
                              onClick={() => setDeclineModalMeeting(m)}
                              className="px-4 py-2 bg-slate-100 hover:bg-rose-50 hover:text-rose-700 text-slate-700 rounded-xl text-xs font-bold uppercase transition-all cursor-pointer"
                            >
                              Decline
                            </button>
                          </>
                        )}

                        {m.status === 'CONFIRMED' && (
                          <>
                            <button
                              onClick={() => handleMarkCompleted(m.id)}
                              className="px-4 py-2 bg-blue-700 hover:bg-blue-800 text-white rounded-xl text-xs font-bold uppercase tracking-wider transition-all flex items-center gap-1.5 shadow-sm cursor-pointer"
                            >
                              <CheckCircle2 size={13} />
                              <span>Conclude Session</span>
                            </button>
                            <Link
                              href="/messages"
                              className="px-4 py-2 bg-slate-100 hover:bg-slate-200 text-slate-700 rounded-xl text-xs font-bold uppercase transition-all text-center flex items-center justify-center gap-1"
                            >
                              <MessageSquare size={13} />
                              <span>Message</span>
                            </Link>
                          </>
                        )}
                      </div>
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>
        )}

        {/* Tab 2: Past Meetings */}
        {activeTab === 'PAST' && (
          <div className="space-y-4">
            {pastMeetings.length === 0 ? (
              <div className="bg-white rounded-2xl border border-slate-200 p-12 text-center text-slate-400">
                <CheckCircle2 className="w-10 h-10 text-slate-300 mx-auto mb-3" />
                <h3 className="font-serif font-bold text-base text-slate-700">No Past Sessions</h3>
                <p className="text-xs text-slate-400 max-w-sm mx-auto mt-1">
                  Completed, declined, or cancelled consultation appointments will be logged here.
                </p>
              </div>
            ) : (
              pastMeetings.map((m) => (
                <div key={m.id} className="bg-white rounded-2xl border border-slate-200 p-5 shadow-xs">
                  <div className="flex items-center justify-between mb-2">
                    {getStatusBadge(m.status)}
                    <span className="text-xs text-slate-400">
                      {new Date(m.scheduled_start).toLocaleDateString()}
                    </span>
                  </div>
                  <p className="text-xs font-bold text-slate-800">
                    Citizen Requester: {m.citizen_profile?.full_name || 'Client'}
                  </p>
                  {m.notes && (
                    <p className="text-xs text-slate-500 italic mt-1">&ldquo;{m.notes}&rdquo;</p>
                  )}
                </div>
              ))
            )}
          </div>
        )}

        {/* Tab 3: Availability Settings */}
        {activeTab === 'AVAILABILITY' && (
          <div className="bg-white rounded-2xl border border-slate-200 p-6 shadow-xs">
            <form onSubmit={handleSaveAvailability} className="space-y-6 max-w-2xl">
              <div>
                <h3 className="font-serif font-bold text-base text-slate-900 mb-1">
                  Practice Availability Schedule
                </h3>
                <p className="text-xs text-slate-500">
                  Configure the working weekdays and hours during which citizens can schedule consultations with your chambers.
                </p>
              </div>

              {/* Working Days */}
              <div>
                <label className="block text-xs font-bold text-slate-700 mb-2">Working Days</label>
                <div className="flex flex-wrap gap-2">
                  {daysOfWeek.map((day) => {
                    const isSelected = availability.available_days.includes(day.num);
                    return (
                      <button
                        key={day.num}
                        type="button"
                        onClick={() => handleToggleDay(day.num)}
                        className={`px-3.5 py-1.5 rounded-xl text-xs font-bold uppercase transition-all ${
                          isSelected
                            ? 'bg-court-maroon text-white shadow-xs'
                            : 'bg-slate-100 text-slate-600 hover:bg-slate-200'
                        }`}
                      >
                        {day.label}
                      </button>
                    );
                  })}
                </div>
              </div>

              {/* Working Hours */}
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                <div>
                  <label className="block text-xs font-bold text-slate-700 mb-1">Daily Start (UTC)</label>
                  <input
                    type="time"
                    value={availability.start_time_utc.substring(0, 5)}
                    onChange={(e) => setAvailability((prev) => ({ ...prev, start_time_utc: `${e.target.value}:00` }))}
                    className="w-full px-3 py-2 bg-slate-50 border border-slate-200 rounded-xl text-xs text-slate-900 focus:outline-none focus:ring-1 focus:ring-court-maroon"
                  />
                  <span className="text-[10px] text-slate-400 mt-1 block">e.g. 04:30 UTC is 10:00 AM IST</span>
                </div>
                <div>
                  <label className="block text-xs font-bold text-slate-700 mb-1">Daily End (UTC)</label>
                  <input
                    type="time"
                    value={availability.end_time_utc.substring(0, 5)}
                    onChange={(e) => setAvailability((prev) => ({ ...prev, end_time_utc: `${e.target.value}:00` }))}
                    className="w-full px-3 py-2 bg-slate-50 border border-slate-200 rounded-xl text-xs text-slate-900 focus:outline-none focus:ring-1 focus:ring-court-maroon"
                  />
                  <span className="text-[10px] text-slate-400 mt-1 block">e.g. 12:30 UTC is 06:00 PM IST</span>
                </div>
              </div>

              {/* Slot Duration */}
              <div>
                <label className="block text-xs font-bold text-slate-700 mb-1">Default Slot Duration</label>
                <select
                  value={availability.slot_duration_minutes}
                  onChange={(e) => setAvailability((prev) => ({ ...prev, slot_duration_minutes: Number(e.target.value) }))}
                  className="w-full px-3 py-2 bg-slate-50 border border-slate-200 rounded-xl text-xs text-slate-900 focus:outline-none focus:ring-1 focus:ring-court-maroon"
                >
                  <option value={15}>15 Minutes</option>
                  <option value={30}>30 Minutes</option>
                  <option value={45}>45 Minutes</option>
                  <option value={60}>60 Minutes</option>
                </select>
              </div>

              {/* Blackout Dates */}
              <div>
                <label className="block text-xs font-bold text-slate-700 mb-1">
                  Court Hearings / Blackout Dates
                </label>
                <p className="text-[11px] text-slate-500 mb-2">
                  Dates when you are occupied in High Court / Supreme Court hearings and cannot take consultations.
                </p>

                <div className="flex items-center gap-2 mb-3">
                  <input
                    type="date"
                    value={newBlackoutDate}
                    onChange={(e) => setNewBlackoutDate(e.target.value)}
                    className="px-3 py-2 bg-slate-50 border border-slate-200 rounded-xl text-xs text-slate-900 focus:outline-none"
                  />
                  <button
                    type="button"
                    onClick={handleAddBlackoutDate}
                    className="px-4 py-2 bg-slate-900 hover:bg-slate-800 text-amber-300 rounded-xl text-xs font-bold uppercase transition-all flex items-center gap-1"
                  >
                    <Plus size={13} />
                    <span>Add Blackout</span>
                  </button>
                </div>

                <div className="flex flex-wrap gap-2">
                  {availability.unavailable_dates.length === 0 ? (
                    <span className="text-xs text-slate-400 italic">No blackout dates registered.</span>
                  ) : (
                    availability.unavailable_dates.map((dt) => (
                      <span
                        key={dt}
                        className="inline-flex items-center gap-1.5 px-3 py-1 rounded-xl text-xs font-bold bg-rose-50 text-rose-800 border border-rose-200"
                      >
                        <span>{dt}</span>
                        <button
                          type="button"
                          onClick={() => handleRemoveBlackoutDate(dt)}
                          className="text-rose-600 hover:text-rose-900"
                        >
                          <Trash2 size={12} />
                        </button>
                      </span>
                    ))
                  )}
                </div>
              </div>

              <div className="pt-4 border-t border-slate-200">
                <button
                  type="submit"
                  disabled={savingAvailability}
                  className="px-6 py-2.5 bg-court-maroon hover:bg-rose-700 text-white rounded-xl text-xs font-bold uppercase tracking-wider transition-all flex items-center gap-2 shadow-sm cursor-pointer"
                >
                  {savingAvailability ? (
                    <div className="w-4 h-4 border-2 border-white border-t-transparent rounded-full animate-spin" />
                  ) : (
                    <>
                      <ShieldCheck size={14} />
                      <span>Save Availability Schedule</span>
                    </>
                  )}
                </button>
              </div>
            </form>
          </div>
        )}

        {/* Confirm Modal */}
        {confirmModalMeeting && (
          <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-xs p-4">
            <div className="bg-white rounded-2xl max-w-md w-full p-6 shadow-2xl border border-slate-200">
              <h3 className="font-serif font-bold text-sm text-slate-900 mb-1">
                Confirm Consultation Appointment
              </h3>
              <p className="text-[11px] text-slate-500 mb-4">
                Provide meeting access credentials or chamber details. These will be securely unlocked for the citizen requester.
              </p>

              <form onSubmit={handleConfirmMeeting} className="space-y-3.5 text-xs">
                {confirmModalMeeting.meeting_mode === 'ONLINE' && (
                  <div>
                    <label className="block font-bold text-slate-700 mb-1">Online Video Meeting URL</label>
                    <input
                      type="url"
                      required
                      value={meetingUrlInput}
                      onChange={(e) => setMeetingUrlInput(e.target.value)}
                      placeholder="https://meet.google.com/xyz or room URL"
                      className="w-full px-3 py-2 bg-slate-50 border border-slate-200 rounded-xl text-xs text-slate-900 focus:outline-none focus:ring-1 focus:ring-court-maroon font-mono"
                    />
                  </div>
                )}

                {confirmModalMeeting.meeting_mode === 'IN_PERSON' && (
                  <div>
                    <label className="block font-bold text-slate-700 mb-1">Chamber Office Location / Address</label>
                    <textarea
                      rows={2}
                      required
                      value={locationInput}
                      onChange={(e) => setLocationInput(e.target.value)}
                      placeholder="e.g. Chamber No. 42, High Court Complex, New Delhi"
                      className="w-full px-3 py-2 bg-slate-50 border border-slate-200 rounded-xl text-xs text-slate-900 focus:outline-none focus:ring-1 focus:ring-court-maroon"
                    />
                  </div>
                )}

                {confirmModalMeeting.meeting_mode === 'PHONE' && (
                  <div>
                    <label className="block font-bold text-slate-700 mb-1">Contact Dial-In Number</label>
                    <input
                      type="tel"
                      required
                      value={phoneInput}
                      onChange={(e) => setPhoneInput(e.target.value)}
                      placeholder="+91 98765 43210"
                      className="w-full px-3 py-2 bg-slate-50 border border-slate-200 rounded-xl text-xs text-slate-900 focus:outline-none focus:ring-1 focus:ring-court-maroon"
                    />
                  </div>
                )}

                <div>
                  <label className="block font-bold text-slate-700 mb-1">Instructions for Citizen (Optional)</label>
                  <textarea
                    rows={2}
                    value={confirmNotes}
                    onChange={(e) => setConfirmNotes(e.target.value)}
                    placeholder="Instructions regarding documents to bring or preparation..."
                    className="w-full px-3 py-2 bg-slate-50 border border-slate-200 rounded-xl text-xs text-slate-900 focus:outline-none focus:ring-1 focus:ring-court-maroon"
                  />
                </div>

                <div className="flex items-center justify-end gap-2 pt-2">
                  <button
                    type="button"
                    onClick={() => setConfirmModalMeeting(null)}
                    className="px-4 py-2 bg-slate-100 hover:bg-slate-200 text-slate-700 rounded-xl text-xs font-bold uppercase transition-all"
                  >
                    Cancel
                  </button>
                  <button
                    type="submit"
                    disabled={updatingStatus}
                    className="px-5 py-2 bg-emerald-700 hover:bg-emerald-800 text-white rounded-xl text-xs font-bold uppercase tracking-wider transition-all flex items-center gap-1.5 shadow-sm"
                  >
                    {updatingStatus ? (
                      <div className="w-3.5 h-3.5 border-2 border-white border-t-transparent rounded-full animate-spin" />
                    ) : (
                      <>
                        <Check size={13} />
                        <span>Confirm & Notify</span>
                      </>
                    )}
                  </button>
                </div>
              </form>
            </div>
          </div>
        )}

        {/* Decline Modal */}
        {declineModalMeeting && (
          <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-xs p-4">
            <div className="bg-white rounded-2xl max-w-md w-full p-6 shadow-2xl border border-slate-200">
              <h3 className="font-serif font-bold text-sm text-slate-900 mb-1">
                Decline Consultation Appointment
              </h3>
              <p className="text-[11px] text-slate-500 mb-4">
                Please provide a brief reason so the citizen requester understands your unavailability.
              </p>

              <form onSubmit={handleDeclineMeeting} className="space-y-3.5 text-xs">
                <div>
                  <label className="block font-bold text-slate-700 mb-1">Reason for Decline</label>
                  <textarea
                    rows={3}
                    required
                    value={declineNotes}
                    onChange={(e) => setDeclineNotes(e.target.value)}
                    placeholder="e.g. Occupied in scheduled hearing at the High Court..."
                    className="w-full px-3 py-2 bg-slate-50 border border-slate-200 rounded-xl text-xs text-slate-900 focus:outline-none focus:ring-1 focus:ring-court-maroon"
                  />
                </div>

                <div className="flex items-center justify-end gap-2 pt-2">
                  <button
                    type="button"
                    onClick={() => setDeclineModalMeeting(null)}
                    className="px-4 py-2 bg-slate-100 hover:bg-slate-200 text-slate-700 rounded-xl text-xs font-bold uppercase transition-all"
                  >
                    Cancel
                  </button>
                  <button
                    type="submit"
                    disabled={updatingStatus}
                    className="px-5 py-2 bg-rose-700 hover:bg-rose-800 text-white rounded-xl text-xs font-bold uppercase tracking-wider transition-all flex items-center gap-1.5 shadow-sm"
                  >
                    {updatingStatus ? (
                      <div className="w-3.5 h-3.5 border-2 border-white border-t-transparent rounded-full animate-spin" />
                    ) : (
                      <span>Decline Request</span>
                    )}
                  </button>
                </div>
              </form>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
