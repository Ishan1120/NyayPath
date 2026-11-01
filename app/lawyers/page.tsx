'use client';

import React, { useState, useEffect } from 'react';
import Link from 'next/link';
import Image from 'next/image';
import { 
  Search, 
  Filter, 
  ShieldCheck, 
  Briefcase, 
  GraduationCap, 
  MapPin, 
  Languages, 
  Scale, 
  Calendar, 
  ArrowRight,
  ExternalLink,
  RefreshCw,
  Clock,
  UserCheck
} from 'lucide-react';
import Navbar from '@/app/Navbar';
import { getVerifiedLawyers, LawyerProfile } from '@/lib/api';

const SPECIALIZATIONS = [
  'All Specializations',
  'Constitutional Law',
  'Criminal Law',
  'Civil Litigation',
  'Education & Student Rights',
  'Consumer Protection',
  'Cyber Law',
  'Labor & Employment',
  'Family & Matrimonial',
  'RTI & Transparency'
];

const STATES = [
  'All States',
  'Delhi',
  'Maharashtra',
  'Karnataka',
  'West Bengal',
  'Uttar Pradesh',
  'Tamil Nadu',
  'Punjab & Haryana'
];

export default function PublicLawyerDirectory() {
  const [lawyers, setLawyers] = useState<LawyerProfile[]>([]);
  const [loading, setLoading] = useState<boolean>(true);
  const [total, setTotal] = useState<number>(0);

  // Filters
  const [search, setSearch] = useState<string>('');
  const [specialization, setSpecialization] = useState<string>('All Specializations');
  const [state, setState] = useState<string>('All States');
  const [page, setPage] = useState<number>(1);
  const limit = 12;

  useEffect(() => {
    fetchLawyers();
  }, [specialization, state, page]);

  const fetchLawyers = async () => {
    setLoading(true);
    try {
      const data = await getVerifiedLawyers({
        search: search.trim() || undefined,
        specialization: specialization !== 'All Specializations' ? specialization : undefined,
        state: state !== 'All States' ? state : undefined,
        limit,
        offset: (page - 1) * limit
      });
      setLawyers(data.lawyers || []);
      setTotal(data.total || 0);
    } catch (err) {
      console.error('Failed to load lawyers directory', err);
    } finally {
      setLoading(false);
    }
  };

  const handleSearchSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    setPage(1);
    fetchLawyers();
  };

  return (
    <div className="min-h-screen bg-slate-50 text-slate-900 font-sans">
      <Navbar />

      <main className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 pt-24 pb-16">
        {/* Hero Section */}
        <div className="bg-gradient-to-br from-slate-900 via-court-maroon to-slate-900 text-white rounded-3xl p-8 sm:p-12 mb-8 shadow-xl relative overflow-hidden">
          <div className="relative z-10 max-w-3xl">
            <span className="inline-flex items-center gap-1.5 px-3 py-1 rounded-full bg-amber-400/20 text-amber-300 text-xs font-bold uppercase tracking-wider mb-4 border border-amber-300/30">
              <ShieldCheck className="w-3.5 h-3.5" /> Bar Council Verified Practitioners
            </span>
            <h1 className="text-3xl sm:text-5xl font-black tracking-tight leading-tight mb-4">
              Connect with Verified Advocates & Legal Experts
            </h1>
            <p className="text-sm sm:text-base text-slate-300 leading-relaxed mb-6">
              Discover verified advocates across High Courts, District Courts, and Statutory Tribunals. 
              Schedule consultations, receive procedural advice, and share case records with explicit consent.
            </p>

            <div className="flex flex-wrap items-center gap-4 text-xs text-slate-300">
              <div className="flex items-center gap-1.5">
                <CheckCircleIcon className="w-4 h-4 text-amber-400" />
                <span>Zero fabricated ratings or reviews</span>
              </div>
              <div className="flex items-center gap-1.5">
                <CheckCircleIcon className="w-4 h-4 text-amber-400" />
                <span>Verified State Bar Council credentials</span>
              </div>
              <div className="flex items-center gap-1.5">
                <CheckCircleIcon className="w-4 h-4 text-amber-400" />
                <span>Consent-driven case sharing</span>
              </div>
            </div>
          </div>
        </div>

        {/* Search & Filter Bar */}
        <div className="bg-white border border-slate-200 rounded-2xl p-4 sm:p-6 shadow-sm mb-8 space-y-4">
          <form onSubmit={handleSearchSubmit} className="flex flex-col md:flex-row gap-3">
            <div className="flex-1 relative">
              <Search className="w-4 h-4 absolute left-3.5 top-1/2 -translate-y-1/2 text-slate-400" />
              <input
                type="text"
                placeholder="Search advocates by name, courts, or legal expertise keywords..."
                value={search}
                onChange={(e) => setSearch(e.target.value)}
                className="w-full pl-10 pr-4 py-2.5 text-sm border border-slate-200 rounded-xl focus:outline-none focus:ring-2 focus:ring-rose-700 bg-slate-50/50"
              />
            </div>

            <div className="flex flex-wrap sm:flex-nowrap gap-3">
              <select
                value={specialization}
                onChange={(e) => { setSpecialization(e.target.value); setPage(1); }}
                className="px-3.5 py-2.5 text-xs font-semibold bg-white border border-slate-200 rounded-xl text-slate-700 focus:outline-none focus:ring-2 focus:ring-rose-700"
              >
                {SPECIALIZATIONS.map(s => (
                  <option key={s} value={s}>{s}</option>
                ))}
              </select>

              <select
                value={state}
                onChange={(e) => { setState(e.target.value); setPage(1); }}
                className="px-3.5 py-2.5 text-xs font-semibold bg-white border border-slate-200 rounded-xl text-slate-700 focus:outline-none focus:ring-2 focus:ring-rose-700"
              >
                {STATES.map(st => (
                  <option key={st} value={st}>{st}</option>
                ))}
              </select>

              <button
                type="submit"
                className="px-5 py-2.5 bg-court-maroon hover:bg-rose-800 text-white font-bold text-xs rounded-xl transition-colors cursor-pointer shrink-0 shadow-sm"
              >
                Find Advocates
              </button>
            </div>
          </form>

          <div className="flex items-center justify-between text-xs text-slate-500 pt-2 border-t border-slate-100">
            <span>Showing {lawyers.length} of {total} verified advocates</span>
            <Link
              href="/lawyer/register"
              className="text-court-maroon hover:underline font-bold inline-flex items-center gap-1"
            >
              Are you an Advocate? Register on NyayPath <ArrowRight className="w-3.5 h-3.5" />
            </Link>
          </div>
        </div>

        {/* Directory Grid */}
        {loading ? (
          <div className="py-20 text-center text-slate-400 text-sm">
            <RefreshCw className="w-8 h-8 animate-spin mx-auto mb-3 text-rose-700" />
            Searching verified advocate directory...
          </div>
        ) : lawyers.length === 0 ? (
          <div className="bg-white border border-slate-200 rounded-2xl p-12 text-center text-slate-500 space-y-3">
            <Scale className="w-12 h-12 text-slate-300 mx-auto" />
            <h3 className="text-lg font-bold text-slate-800">No Verified Advocates Found</h3>
            <p className="text-xs text-slate-500 max-w-md mx-auto">
              No verified advocates matched your search filters. Try broadening your specialization or state selection.
            </p>
            <button
              onClick={() => { setSearch(''); setSpecialization('All Specializations'); setState('All States'); }}
              className="px-4 py-2 bg-slate-100 hover:bg-slate-200 text-slate-700 font-bold text-xs rounded-xl cursor-pointer"
            >
              Reset Filters
            </button>
          </div>
        ) : (
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
            {lawyers.map((lawyer) => (
              <div
                key={lawyer.id}
                className="bg-white border border-slate-200 rounded-2xl p-6 shadow-sm hover:shadow-md transition-all flex flex-col justify-between"
              >
                <div>
                  <div className="flex items-start gap-4 mb-4">
                    <div className="w-14 h-14 rounded-2xl bg-slate-100 border border-slate-200 shrink-0 flex items-center justify-center font-bold text-slate-700 text-lg overflow-hidden">
                      {lawyer.photo_url ? (
                        <img src={lawyer.photo_url} alt={lawyer.full_name} className="w-full h-full object-cover" />
                      ) : (
                        lawyer.full_name.substring(0, 2).toUpperCase()
                      )}
                    </div>
                    <div>
                      <div className="flex items-center gap-1.5 flex-wrap">
                        <h3 className="font-bold text-slate-900 text-base">Adv. {lawyer.full_name}</h3>
                        <span className="inline-flex items-center gap-0.5 px-2 py-0.5 rounded-full bg-emerald-50 text-emerald-700 text-[10px] font-bold border border-emerald-200">
                          <ShieldCheck className="w-3 h-3 text-emerald-600" /> VERIFIED
                        </span>
                      </div>
                      <p className="text-xs text-slate-500 mt-0.5 flex items-center gap-1">
                        <MapPin className="w-3 h-3 text-slate-400" />
                        {lawyer.enrollment_state} Bar ({lawyer.bar_council})
                      </p>
                      <p className="text-xs text-slate-500 mt-0.5 font-medium">
                        {lawyer.years_of_practice} Years of Practice
                      </p>
                    </div>
                  </div>

                  {/* Bio */}
                  {lawyer.bio && (
                    <p className="text-xs text-slate-600 line-clamp-3 mb-4 leading-relaxed">
                      {lawyer.bio}
                    </p>
                  )}

                  {/* Specializations */}
                  <div className="mb-4">
                    <span className="text-[11px] font-bold text-slate-400 uppercase tracking-wider block mb-1.5">Specializations</span>
                    <div className="flex flex-wrap gap-1.5">
                      {lawyer.specializations.slice(0, 3).map((spec, i) => (
                        <span key={i} className="px-2.5 py-1 bg-slate-100 text-slate-700 rounded-lg text-[11px] font-medium">
                          {spec}
                        </span>
                      ))}
                      {lawyer.specializations.length > 3 && (
                        <span className="px-2 py-1 bg-slate-50 text-slate-500 rounded-lg text-[10px] font-bold">
                          +{lawyer.specializations.length - 3} more
                        </span>
                      )}
                    </div>
                  </div>

                  {/* Courts & Languages */}
                  <div className="space-y-1.5 text-xs text-slate-500 mb-4 pb-4 border-b border-slate-100">
                    {lawyer.courts && lawyer.courts.length > 0 && (
                      <div className="flex items-center gap-1.5 truncate">
                        <Scale className="w-3.5 h-3.5 text-slate-400 shrink-0" />
                        <span className="truncate">{lawyer.courts.join(', ')}</span>
                      </div>
                    )}
                    {lawyer.languages && lawyer.languages.length > 0 && (
                      <div className="flex items-center gap-1.5">
                        <Languages className="w-3.5 h-3.5 text-slate-400 shrink-0" />
                        <span>{lawyer.languages.join(', ')}</span>
                      </div>
                    )}
                  </div>
                </div>

                {/* Actions */}
                <div className="grid grid-cols-2 gap-2 pt-2">
                  <Link
                    href={`/lawyers/${lawyer.id}`}
                    className="py-2 text-center text-xs font-bold text-slate-700 bg-slate-100 hover:bg-slate-200 rounded-xl transition-colors cursor-pointer"
                  >
                    View Profile
                  </Link>
                  <Link
                    href={`/dashboard/find-lawyer?lawyer_id=${lawyer.id}`}
                    className="py-2 text-center text-xs font-bold text-white bg-court-maroon hover:bg-rose-800 rounded-xl transition-colors cursor-pointer shadow-sm shadow-rose-950/20"
                  >
                    Consult
                  </Link>
                </div>
              </div>
            ))}
          </div>
        )}
      </main>
    </div>
  );
}

function CheckCircleIcon(props: any) {
  return (
    <svg fill="none" viewBox="0 0 24 24" strokeWidth={2} stroke="currentColor" {...props}>
      <path strokeLinecap="round" strokeLinejoin="round" d="M9 12.75L11.25 15 15 9.75M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
    </svg>
  );
}
