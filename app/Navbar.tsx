"use client";

import React, { useState, useEffect, useRef } from "react";
import Image from "next/image";
import { useRouter } from "next/navigation";
import {
  Gavel,
  Menu,
  X,
  Scale,
  Newspaper,
  BookOpen,
  GraduationCap,
  Clock,
  LayoutDashboard,
  Briefcase,
  UserCheck,
  Bell,
  BellRing,
  Check,
  CheckCheck,
  ExternalLink,
  FileText,
  AlertCircle,
  Building
} from "lucide-react";
import Link from "next/link";
import {
  getUserNotifications,
  getUnreadNotificationCount,
  markNotificationAsRead,
  markAllNotificationsAsRead,
  CaseNotification
} from "@/lib/api";

export default function Navbar() {
  const router = useRouter();
  const [mobileMenuOpen, setMobileMenuOpen] = useState(false);
  const [isLoggedIn, setIsLoggedIn] = useState(false);
  const [unreadCount, setUnreadCount] = useState<number>(0);
  const [notifications, setNotifications] = useState<CaseNotification[]>([]);
  const [dropdownOpen, setDropdownOpen] = useState(false);
  const [loadingNotifications, setLoadingNotifications] = useState(false);
  const dropdownRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (typeof window !== "undefined") {
      const token =
        localStorage.getItem("nyaypath_citizen_token") ||
        localStorage.getItem("nyaypath_token") ||
        localStorage.getItem("nyaypath_proctor_token");
      const logged = !!token;
      setIsLoggedIn(logged);
      if (logged) {
        fetchUnreadCount();
      }
    }
  }, []);

  // Periodic polling for unread notifications every 30 seconds
  useEffect(() => {
    if (!isLoggedIn) return;
    const interval = setInterval(() => {
      fetchUnreadCount();
    }, 30000);
    return () => clearInterval(interval);
  }, [isLoggedIn]);

  // Click outside listener to dismiss dropdown
  useEffect(() => {
    function handleClickOutside(event: MouseEvent) {
      if (dropdownRef.current && !dropdownRef.current.contains(event.target as Node)) {
        setDropdownOpen(false);
      }
    }
    if (dropdownOpen) {
      document.addEventListener("mousedown", handleClickOutside);
    }
    return () => {
      document.removeEventListener("mousedown", handleClickOutside);
    };
  }, [dropdownOpen]);

  const fetchUnreadCount = async () => {
    try {
      const data = await getUnreadNotificationCount();
      setUnreadCount(Number(data.unread_count || 0));
    } catch {
      // Ignore if unauthenticated or network error
    }
  };

  const loadRecentNotifications = async () => {
    setLoadingNotifications(true);
    try {
      const data = await getUserNotifications({ limit: 5 });
      setNotifications(data.notifications || []);
      setUnreadCount(Number(data.unread_count || 0));
    } catch {
      // Fail safely
    } finally {
      setLoadingNotifications(false);
    }
  };

  const handleToggleDropdown = () => {
    if (!dropdownOpen) {
      loadRecentNotifications();
    }
    setDropdownOpen((prev) => !prev);
  };

  const handleMarkOneRead = async (notificationId: string, e: React.MouseEvent) => {
    e.stopPropagation();
    try {
      await markNotificationAsRead(notificationId);
      setNotifications((prev) =>
        prev.map((n) => (n.id === notificationId ? { ...n, is_read: true } : n))
      );
      setUnreadCount((prev) => Math.max(0, prev - 1));
    } catch {
      // Ignore error
    }
  };

  const handleMarkAllRead = async (e: React.MouseEvent) => {
    e.stopPropagation();
    try {
      await markAllNotificationsAsRead();
      setNotifications((prev) => prev.map((n) => ({ ...n, is_read: true })));
      setUnreadCount(0);
    } catch {
      // Ignore error
    }
  };

  const handleNotificationClick = (item: CaseNotification) => {
    if (!item.is_read) {
      markNotificationAsRead(item.id).catch(() => {});
      setUnreadCount((prev) => Math.max(0, prev - 1));
    }
    setDropdownOpen(false);
    if (item.action_url) {
      router.push(item.action_url);
    } else if (item.related_case_id) {
      router.push(`/dashboard/my-cases?case_id=${encodeURIComponent(item.related_case_id)}`);
    } else {
      router.push("/dashboard/notifications");
    }
  };

  const formatTimeAgo = (isoString?: string) => {
    if (!isoString) return "";
    try {
      const diffMs = Date.now() - new Date(isoString).getTime();
      const diffSec = Math.floor(diffMs / 1000);
      if (diffSec < 60) return "Just now";
      const diffMin = Math.floor(diffSec / 60);
      if (diffMin < 60) return `${diffMin}m ago`;
      const diffHr = Math.floor(diffMin / 60);
      if (diffHr < 24) return `${diffHr}h ago`;
      const diffDays = Math.floor(diffHr / 24);
      return `${diffDays}d ago`;
    } catch {
      return "";
    }
  };

  const getEventBadge = (eventType: string) => {
    switch (eventType) {
      case "CASE_SUBMITTED":
        return <FileText className="w-3.5 h-3.5 text-blue-600 shrink-0" />;
      case "HEARING_SCHEDULED":
        return <Clock className="w-3.5 h-3.5 text-purple-600 shrink-0" />;
      case "CASE_WITHDRAWN":
        return <AlertCircle className="w-3.5 h-3.5 text-amber-600 shrink-0" />;
      case "CASE_STATUS_UPDATED":
      default:
        return <Scale className="w-3.5 h-3.5 text-indigo-600 shrink-0" />;
    }
  };

  const navLinks = [
    { name: "Dashboard", href: "/dashboard", icon: LayoutDashboard },
    { name: "My Cases", href: "/dashboard/my-cases", icon: Briefcase },
    { name: "College Proctor", href: "/campus-proctor", icon: GraduationCap },
    { name: "Institution", href: "/institution/dashboard", icon: Building },
    { name: "Case Search", href: "/case-search", icon: BookOpen },
    { name: "Court News", href: "/court-news", icon: Newspaper },
    { name: "Track SLA", href: "/track", icon: Clock },
  ];

  const handleLaunch = () => {
    router.push("/dashboard?tab=assistant");
  };

  return (
    <header className="fixed top-0 left-0 right-0 z-50 px-4 pt-4 font-sans">
      <nav className="max-w-6xl mx-auto bg-white/95 backdrop-blur-md border border-slate-200/90 rounded-full shadow-lg shadow-slate-900/5 ring-1 ring-black/5">
        <div className="px-5 sm:px-7">
          <div className="flex items-center justify-between h-14">
            {/* Brand Logo */}
            <Link href="/" className="flex items-center shrink-0 py-1">
              <Image
                src="/nyaypath-logo.png"
                alt="NyayPath"
                width={200}
                height={160}
                className="object-contain h-9 sm:h-10 w-auto"
                priority
              />
            </Link>

            {/* Desktop Navigation Links */}
            <div className="hidden lg:flex items-center gap-5 text-xs font-bold tracking-tight text-slate-700 uppercase">
              {navLinks.map((link) => {
                const Icon = link.icon;
                return (
                  <Link
                    key={link.name}
                    href={link.href}
                    className="hover:text-court-maroon transition-colors flex items-center gap-1 py-1"
                  >
                    <Icon size={13} className="text-slate-400 group-hover:text-court-maroon" />
                    <span>{link.name}</span>
                  </Link>
                );
              })}
            </div>

            {/* Action CTA & Mobile Toggle */}
            <div className="flex items-center gap-2.5">
              {/* Intelligent Notification Bell & Popover */}
              <div className="relative" ref={dropdownRef}>
                <button
                  type="button"
                  onClick={handleToggleDropdown}
                  aria-label="View notifications"
                  className="relative p-2 rounded-full text-slate-600 hover:text-slate-900 hover:bg-slate-100 transition-colors cursor-pointer border border-slate-200/60"
                >
                  {unreadCount > 0 ? (
                    <BellRing className="w-4 h-4 text-rose-700 animate-pulse" />
                  ) : (
                    <Bell className="w-4 h-4 text-slate-600" />
                  )}
                  {unreadCount > 0 && (
                    <span className="absolute -top-1 -right-1 min-w-[18px] h-[18px] px-1 bg-rose-600 text-white text-[10px] font-bold rounded-full flex items-center justify-center border-2 border-white shadow-sm">
                      {unreadCount > 9 ? "9+" : unreadCount}
                    </span>
                  )}
                </button>

                {/* Notification Popover Dropdown */}
                {dropdownOpen && (
                  <div className="absolute right-0 mt-3 w-80 sm:w-96 bg-white rounded-2xl shadow-2xl border border-slate-200/90 z-50 overflow-hidden transform transition-all animate-in fade-in slide-in-from-top-2">
                    {/* Header */}
                    <div className="p-3.5 bg-gradient-to-r from-slate-900 to-slate-800 text-white flex items-center justify-between">
                      <div className="flex items-center gap-2">
                        <Bell className="w-4 h-4 text-amber-400" />
                        <span className="text-xs font-bold uppercase tracking-wider">
                          Notifications
                        </span>
                        {unreadCount > 0 && (
                          <span className="bg-rose-500 text-white text-[10px] font-bold px-1.5 py-0.5 rounded-full">
                            {unreadCount} new
                          </span>
                        )}
                      </div>
                      {unreadCount > 0 && (
                        <button
                          onClick={handleMarkAllRead}
                          className="text-[11px] font-medium text-slate-300 hover:text-white flex items-center gap-1 cursor-pointer transition-colors"
                        >
                          <CheckCheck className="w-3.5 h-3.5" />
                          <span>Mark all read</span>
                        </button>
                      )}
                    </div>

                    {/* Notification List */}
                    <div className="max-h-80 overflow-y-auto divide-y divide-slate-100">
                      {loadingNotifications ? (
                        <div className="py-8 text-center text-xs text-slate-400">
                          Loading updates...
                        </div>
                      ) : notifications.length === 0 ? (
                        <div className="py-8 px-4 text-center">
                          <Bell className="w-7 h-7 text-slate-300 mx-auto mb-2" />
                          <p className="text-xs font-medium text-slate-600">No notifications yet</p>
                          <p className="text-[11px] text-slate-400 mt-0.5">
                            Real-time case submissions and proctor updates will appear here.
                          </p>
                        </div>
                      ) : (
                        notifications.map((item) => (
                          <div
                            key={item.id}
                            onClick={() => handleNotificationClick(item)}
                            className={`p-3.5 hover:bg-slate-50 transition-colors cursor-pointer flex items-start gap-3 ${
                              !item.is_read ? "bg-rose-50/40" : ""
                            }`}
                          >
                            <div className="p-1.5 rounded-lg bg-slate-100 border border-slate-200 shrink-0 mt-0.5">
                              {getEventBadge(item.event_type)}
                            </div>
                            <div className="flex-1 min-w-0">
                              <div className="flex items-center justify-between gap-1">
                                <p
                                  className={`text-xs font-semibold truncate ${
                                    !item.is_read ? "text-slate-900" : "text-slate-700"
                                  }`}
                                >
                                  {item.title}
                                </p>
                                <span className="text-[10px] text-slate-400 shrink-0">
                                  {formatTimeAgo(item.created_at)}
                                </span>
                              </div>
                              <p className="text-[11px] text-slate-500 line-clamp-2 mt-0.5 leading-snug">
                                {item.message}
                              </p>
                              {item.related_case_id && (
                                <div className="mt-1.5 flex items-center gap-2">
                                  <span className="text-[10px] font-mono font-medium text-court-maroon bg-rose-50 border border-rose-200/60 px-1.5 py-0.2 rounded">
                                    {item.related_case_id}
                                  </span>
                                  {!item.is_read && (
                                    <button
                                      onClick={(e) => handleMarkOneRead(item.id, e)}
                                      className="text-[10px] text-slate-400 hover:text-slate-700 flex items-center gap-0.5 ml-auto cursor-pointer"
                                    >
                                      <Check className="w-3 h-3" />
                                      <span>Mark read</span>
                                    </button>
                                  )}
                                </div>
                              )}
                            </div>
                          </div>
                        ))
                      )}
                    </div>

                    {/* Footer */}
                    <div className="p-2.5 bg-slate-50 border-t border-slate-100 text-center">
                      <Link
                        href="/dashboard/notifications"
                        onClick={() => setDropdownOpen(false)}
                        className="inline-flex items-center justify-center gap-1.5 text-xs font-bold text-court-maroon hover:text-rose-700 transition-colors py-1"
                      >
                        <span>View All Notifications in Center</span>
                        <ExternalLink className="w-3 h-3" />
                      </Link>
                    </div>
                  </div>
                )}
              </div>

              <button
                onClick={handleLaunch}
                className="inline-flex items-center gap-1.5 px-4 py-2 rounded-full bg-gradient-to-r from-court-maroon via-rose-700 to-court-maroon hover:from-rose-700 hover:to-rose-800 text-white text-[11px] font-bold uppercase tracking-wider transition-all shrink-0 cursor-pointer shadow-md shadow-rose-950/20 active:scale-95"
              >
                <Gavel className="w-3.5 h-3.5 text-amber-300 shrink-0" />
                <span>Launch Engine</span>
              </button>

              <button
                onClick={() => setMobileMenuOpen(!mobileMenuOpen)}
                className="lg:hidden p-1.5 text-slate-700 hover:bg-slate-100 rounded-lg transition-colors cursor-pointer"
                aria-label="Toggle Navigation"
              >
                {mobileMenuOpen ? <X className="w-5 h-5" /> : <Menu className="w-5 h-5" />}
              </button>
            </div>
          </div>
        </div>

        {/* Mobile Navigation Drawer */}
        {mobileMenuOpen && (
          <div className="lg:hidden border-t border-slate-200 px-4 pt-3 pb-4 space-y-1 bg-white rounded-b-3xl mt-1 shadow-xl">
            {navLinks.map((link) => {
              const Icon = link.icon;
              return (
                <Link
                  key={link.name}
                  href={link.href}
                  onClick={() => setMobileMenuOpen(false)}
                  className="flex items-center gap-2 px-3 py-2.5 rounded-xl text-xs font-bold text-slate-800 hover:bg-rose-50 hover:text-court-maroon transition-colors"
                >
                  <Icon size={15} className="text-slate-400" />
                  <span>{link.name}</span>
                </Link>
              );
            })}
            <Link
              href="/dashboard/notifications"
              onClick={() => setMobileMenuOpen(false)}
              className="flex items-center justify-between px-3 py-2.5 rounded-xl text-xs font-bold text-slate-800 hover:bg-rose-50 hover:text-court-maroon transition-colors border-t border-slate-100 pt-3"
            >
              <div className="flex items-center gap-2">
                <Bell size={15} className="text-rose-600" />
                <span>Notification Center</span>
              </div>
              {unreadCount > 0 && (
                <span className="bg-rose-600 text-white text-[10px] font-bold px-2 py-0.5 rounded-full">
                  {unreadCount} unread
                </span>
              )}
            </Link>
          </div>
        )}
      </nav>
    </header>
  );
}
