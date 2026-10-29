"use client";

import React, { useEffect, useState } from "react";
import Image from "next/image";
import { useRouter } from "next/navigation";
import Navbar from "./Navbar";
import Link from "next/link";
import {
  Scale,
  FileText,
  Shield,
  ArrowRight,
  ChevronRight,
  Landmark,
  Gavel,
  HardDrive,
  FileCheck,
  TriangleAlert,
  CircleX,
  Copy,
  Check,
  BookOpen,
  Bot,
  Clock,
  ShieldCheck,
  Terminal,
  Activity,
  X,
  Printer,
  Download,
  CheckCircle,
  Newspaper,
  GraduationCap,
} from "lucide-react";

interface ConsolePreset {
  id: string;
  tag: string;
  category: string;
  citizenInput: string;
  authority: string;
  targetAct: string;
  sectionClause: string;
  statutoryClock: string;
  penaltyLiability: string;
  successOdds: number;
  rejectionReason: string;
  legalDraftSnippet: string[];
}

const CONSOLE_PRESETS: ConsolePreset[] = [
  {
    id: "road",
    tag: "PWD Road Repair Delay",
    category: "Public Works / Municipal PWD",
    citizenInput:
      "Ward 12 road carpeting delayed 7 months despite budget sanction and tender award.",
    authority:
      "Public Information Officer, PWD Executive Division / Municipal Corporation",
    targetAct: "Right to Information Act, 2005",
    sectionClause:
      "Sec. 6(1) read with Sec. 2(j)(i) [Certified Physical Inspection]",
    statutoryClock: "30 Calendar Days (Sec. 7(1))",
    penaltyLiability:
      "₹250/day up to ₹25,000 personal fine on CPIO under Sec. 20(1)",
    successOdds: 96,
    rejectionReason:
      "Avoid asking 'Why'. Demanding certified copies of the Measurement Book (MB) and delay penalty ledger eliminates Section 2(f) rejection.",
    legalDraftSnippet: [
      "1. Certified copy of the sanctioned work order, tender agreement, and execution milestone schedule for Ward 12 road carpeting.",
      "2. Certified copy of the Measurement Book (MB) entries and bituminous test logs submitted by inspecting engineers.",
      "3. Details of total funds disbursed to contractor till date and certified copies of delay penalty notices issued under contract terms.",
    ],
  },
  {
    id: "epfo",
    tag: "EPFO Pension Claim Hold",
    category: "Social Security / EPFO",
    citizenInput:
      "Pension EPS-95 claim rejected without issuing any formal deficiency memo or reason.",
    authority:
      "Central Public Information Officer, Regional EPFO Commissioner",
    targetAct: "Right to Information Act, 2005 (Social Security)",
    sectionClause: "Sec. 6(1) [File Movement & Deficiency Audit]",
    statutoryClock: "30 Calendar Days (Sec. 7(1))",
    penaltyLiability: "Disciplinary recommendation under Sec. 20(2)",
    successOdds: 94,
    rejectionReason:
      "Raw complaints get lost. Demanding the daily file movement sheet and Accounts Officer file notes forces immediate administrative review.",
    legalDraftSnippet: [
      "1. Daily file movement sheet from the date of submission of Pension Claim ID #PPO-884912 to the present date.",
      "2. Certified extract of the deficiency memo or objections recorded in file by the dealing Accounts Officer.",
      "3. Name and designation of the dealing official holding the file beyond the 20-day citizen charter limit.",
    ],
  },
  {
    id: "consumer",
    tag: "E-Commerce Refund Refusal",
    category: "Consumer Disputes / E-Commerce",
    citizenInput:
      "E-commerce platform delivered a defective electronic item and denied refund within return window.",
    authority:
      "District Consumer Disputes Redressal Commission / National Consumer Helpline",
    targetAct: "Consumer Protection Act, 2019",
    sectionClause:
      "Sec. 2(47) [Unfair Trade Practice] & Sec. 35 [Statutory Notice]",
    statutoryClock: "21 Days Statutory Notice for Deficiency of Service",
    penaltyLiability:
      "Replacement, refund with 18% interest & litigation damages under Sec. 39",
    successOdds: 98,
    rejectionReason:
      "Customer care chats are easily ignored. A structured statutory notice under CPA 2019 triggers the legal compliance cell.",
    legalDraftSnippet: [
      "1. Formal statutory notice for deficiency of service and unfair trade practice under CPA 2019.",
      "2. Claim for 100% refund of transaction amount with 18% p.a. statutory interest.",
      "3. Claim for damages for harassment and litigation expenses.",
    ],
  },
  {
    id: "ration",
    tag: "Fair Price Shop PDS Denial",
    category: "Food & Civil Supplies / PDS",
    citizenInput:
      "Fair price shop owner refusing to disburse monthly subsidized grain quota to BPL cardholders.",
    authority:
      "District Food & Civil Supplies Officer / Vigilance Cell",
    targetAct: "National Food Security Act, 2013 & RTI Act, 2005",
    sectionClause:
      "Sec. 6(1) read with Sec. 4(1)(b) Proactive PDS Disclosure",
    statutoryClock:
      "48 Hours (Life & Liberty Clause, Sec. 7(1) proviso)",
    penaltyLiability:
      "Suspension of Fair Price Shop license and criminal liability under Essential Commodities Act",
    successOdds: 97,
    rejectionReason:
      "Demanding e-POS transaction logs and monthly allotment registers leaves no room for local diversion.",
    legalDraftSnippet: [
      "1. Certified copy of monthly grain quota allocation and distribution register for Fair Price Shop #418.",
      "2. Electronic POS machine transaction logs and biometric verification receipts for current cycle.",
      "3. Inspection logs of the Food and Civil Supplies Inspector for the preceding three months.",
    ],
  },
];

export default function Landing() {
  const router = useRouter();

  useEffect(() => {
    if (typeof window !== "undefined") {
      window.history.scrollRestoration = "manual";
      window.scrollTo(0, 0);
    }

    const navigation = performance.getEntriesByType(
      "navigation"
    )[0] as PerformanceNavigationTiming;

    if (navigation?.type === "reload") {
      const currentPath = window.location.pathname;

      if (currentPath !== "/") {
        router.replace("/");
      }
    }
  }, [router]);
  const [selectedPresetId, setSelectedPresetId] = useState<string>("road");
  const [inputText, setInputText] = useState<string>(
    CONSOLE_PRESETS[0].citizenInput
  );
  const [copied, setCopied] = useState<boolean>(false);
  const [modalOpen, setModalOpen] = useState<boolean>(false);

  const preset =
    CONSOLE_PRESETS.find((p) => p.id === selectedPresetId) ||
    CONSOLE_PRESETS[0];

  const handleSelectPreset = (p: ConsolePreset) => {
    setSelectedPresetId(p.id);
    setInputText(p.citizenInput);
  };

  const handleStartIntake = () => {
    if (typeof window !== "undefined" && inputText.trim()) {
      sessionStorage.setItem("nyaypath_problem", inputText);
      sessionStorage.setItem("janadhikar_problem", inputText);
    }
    router.push("/dashboard");
  };

  const getFullPetitionText = () => {
    return `APPLICATION UNDER SECTION 6(1) OF THE RIGHT TO INFORMATION ACT, 2005

To:
${preset.authority}

1. Full Name of the Applicant: [Citizen Name]
2. Address for Correspondence: [Citizen Residential Address]
3. Citizenship: Indian Citizen

4. PARTICULARS OF INFORMATION SOUGHT:
Subject Matter: ${preset.tag}
Statutory Reference: ${preset.sectionClause}

PRAYER POINTS:
${preset.legalDraftSnippet.join("\n")}

5. STATUTORY TIME LIMIT:
As per Section 7(1) of the RTI Act, 2005, the requested information must be furnished within ${preset.statutoryClock}.

6. STATUTORY PENALTY CLAUSE:
Take notice that deliberate delay, mala fide denial, or misleading information attracts personal penal proceedings under Section 20(1) (₹250/day up to ₹25,000) and recommendation for disciplinary proceedings under Section 20(2) of the RTI Act, 2005.

7. APPLICATION FEE:
RTI application fee of ₹10/- attached via Postal Order / Court Fee Stamp / Online Portal Reference.

Date: ${new Date().toLocaleDateString("en-IN", {
      day: "numeric",
      month: "long",
      year: "numeric",
    })}
Place: India

__________________________
[Signature of Applicant]`;
  };

  const handleCopyDraft = () => {
    navigator.clipboard.writeText(getFullPetitionText());
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  const handlePrint = () => {
    window.print();
  };

  return (
    <div className="min-h-screen bg-slate-50 text-slate-900 font-sans selection:bg-[#881337] selection:text-white relative">
      <Navbar />

      {/* BACKGROUND ASHOKA CHAKRA */}
      <div className="fixed inset-0 pointer-events-none z-0 flex items-center justify-center overflow-hidden">
        <svg
          className="w-[950px] h-[950px] opacity-[0.022] text-[#881337] select-none -translate-y-12"
          viewBox="0 0 200 200"
          fill="none"
          stroke="currentColor"
        >
          <circle cx="100" cy="100" r="95" strokeWidth="2.5" />
          <circle cx="100" cy="100" r="82" strokeWidth="1.5" />
          <circle cx="100" cy="100" r="20" strokeWidth="2.5" />
          <circle cx="100" cy="100" r="6" fill="currentColor" />

          {Array.from({ length: 24 }).map((_, i) => {
            const angle = (i * 360) / 24;
            return (
              <line
                key={i}
                x1="100"
                y1="100"
                x2="100"
                y2="18"
                strokeWidth="1.5"
                transform={`rotate(${angle} 100 100)`}
              />
            );
          })}
        </svg>
      </div>

      <style jsx global>{`
        @keyframes jn-chakra-spin {
          from {
            transform: rotate(0deg);
          }
          to {
            transform: rotate(360deg);
          }
        }

        .jn-seal-ring {
          animation: jn-chakra-spin 22s linear infinite;
        }

        @media (prefers-reduced-motion: reduce) {
          .jn-seal-ring {
            animation: none;
          }
        }

        .jn-nav-link {
          position: relative;
        }

        .jn-nav-link::after {
          content: "";
          position: absolute;
          left: 0;
          right: 0;
          bottom: -4px;
          height: 1.5px;
          background: #881337;
          transform: scaleX(0);
          transform-origin: left;
          transition: transform 0.2s ease;
        }

        .jn-nav-link:hover::after {
          transform: scaleX(1);
        }

        @keyframes fade-in-up {
          0% {
            opacity: 0;
            transform: translateY(20px);
          }
          100% {
            opacity: 1;
            transform: translateY(0);
          }
        }

        .animate-fade-in-up {
          opacity: 0;
          animation: fade-in-up 0.8s cubic-bezier(0.16, 1, 0.3, 1) forwards;
        }

        .delay-100 { animation-delay: 100ms; }
        .delay-200 { animation-delay: 200ms; }
        .delay-300 { animation-delay: 300ms; }
        .delay-400 { animation-delay: 400ms; }
      `}</style>

      {/* MAIN */}
      <main className="relative z-10 pt-16 sm:pt-20 pb-16 sm:pb-24">
        {/* HERO */}
        <section className="relative px-4 sm:px-6 lg:px-8 max-w-7xl mx-auto min-h-[calc(100vh-5rem)] flex items-start pt-12 sm:pt-20 justify-center">
          <div className="hidden xl:block absolute right-4 2xl:right-12 top-[55%] -translate-y-1/2 pointer-events-none select-none z-20">
            <div
              className="absolute inset-0 pointer-events-none"
              style={{
                background:
                  "radial-gradient(ellipse 50% 50% at 50% 50%, rgba(180,118,42,0.18) 0%, transparent 80%)",
                filter: "blur(25px)",
              }}
            />
            <img
              src="/lady justice.png"
              alt="Indian Lady of Justice"
              className="h-[460px] 2xl:h-[520px] w-auto object-contain opacity-95 transition-transform duration-500 hover:scale-[1.02] animate-fade-in-up delay-300"
              style={{
                filter: "drop-shadow(0 12px 24px rgba(140,90,20,0.22))",
              }}
            />
          </div>

          <div className="relative z-10 w-full max-w-4xl mx-auto text-center flex flex-col items-center my-0 py-4">
            <h1 className="animate-fade-in-up text-5xl sm:text-6xl xl:text-7xl font-extrabold tracking-tight text-slate-900 leading-[1.08] max-w-3xl">
  Claim Your Civic Rights.{" "}
  <span className="relative inline-block text-[#A32A02]">
    Zero Bureaucracy!
    <svg
      className="absolute -bottom-2 left-0 w-full h-[16px] sm:h-[20px] pointer-events-none overflow-visible"
      viewBox="0 0 320 22"
      fill="none"
      xmlns="http://www.w3.org/2000/svg"
      preserveAspectRatio="none"
    >
      <path
        d="M 3,13 C 65,5 145,16 220,9 C 265,5 295,14 317,8"
        stroke="#FF9933"
        strokeWidth="3.8"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
      <path
        d="M 14,18 C 85,14 185,20 295,14"
        stroke="#FF9933"
        strokeWidth="2"
        strokeLinecap="round"
        strokeLinejoin="round"
        opacity="0.85"
      />
    </svg>
  </span>
</h1>

            <p className="animate-fade-in-up delay-100 mt-6 text-lg sm:text-xl text-slate-600 max-w-2xl leading-relaxed">
              An autonomous, local-first legal engine that helps turn everyday
              civic problems into structured RTI applications, grievance
              routes, and statutory appeals. No legal jargon required.
            </p>

            <div className="animate-fade-in-up delay-200 mt-8 flex flex-col sm:flex-row justify-center gap-4 w-full px-4 sm:px-0">
              <button
  onClick={handleStartIntake}
  className="inline-flex items-center justify-center gap-3 px-8 py-4 rounded-xl bg-gradient-to-r from-court-maroon via-rose-700 to-court-maroon hover:from-rose-700 hover:to-rose-800 transition-colors font-bold text-base text-white tracking-tight shadow-md group cursor-pointer"
>
  <Gavel className="w-5 h-5 text-amber-200 shrink-0" />
  <span>Launch NyayPath</span>
  <ChevronRight className="w-5 h-5 text-white/70 group-hover:translate-x-0.5 transition-transform shrink-0" />
</button>

<button
  onClick={() => router.push('/track')}
  className="inline-flex items-center justify-center gap-3 px-8 py-4 rounded-xl bg-gradient-to-r from-court-maroon via-rose-700 to-court-maroon hover:from-rose-700 hover:to-rose-800 transition-colors font-bold text-base text-white tracking-tight shadow-md group cursor-pointer"
>
  <Activity className="w-5 h-5 text-emerald-200 shrink-0" />
  <span>Track Filed Case</span>
  <ChevronRight className="w-5 h-5 text-white/70 group-hover:translate-x-0.5 transition-transform shrink-0" />
</button>
            </div>
          </div>
        </section>

        {/* COLLEGE PROJECT ACADEMIC SHOWCASE & NEW MODULES */}
        <section className="py-12 bg-white border-y border-slate-200">
          <div className="max-w-6xl mx-auto px-4 sm:px-6 lg:px-8">
            <div className="flex flex-col md:flex-row items-center justify-between gap-4 p-5 rounded-2xl bg-slate-900 text-white mb-10 shadow-lg">
              <div className="flex items-center gap-3">
                <div className="w-11 h-11 rounded-xl bg-gradient-to-br from-court-maroon to-rose-600 text-white flex items-center justify-center font-bold text-lg shrink-0 shadow-md"><Scale className="w-5 h-5 text-amber-300" /></div>
                <div>
                  <div className="flex flex-wrap items-center gap-2">
                    <span className="text-xs font-bold text-amber-400 uppercase tracking-widest">NyayPath Legal Engine v2.6</span>
                    <span className="text-[10px] px-2 py-0.5 rounded-full bg-emerald-500/20 text-emerald-400 font-bold">
                      100% Benchmark Accuracy
                    </span>
                  </div>
                  <h3 className="text-base sm:text-lg font-black tracking-tight text-white mt-0.5">National Judicial Intelligence &amp; Citizen Redressal Infrastructure</h3>
                </div>
              </div>

              <div className="flex flex-wrap items-center gap-2 sm:gap-3 text-xs font-semibold">
                <Link
                  href="/court-news"
                  className="px-3.5 py-2 rounded-xl bg-white/10 hover:bg-white/20 text-slate-200 transition-colors"
                >
                  Court News
                </Link>
                <Link
                  href="/case-search"
                  className="px-3.5 py-2 rounded-xl bg-white/10 hover:bg-white/20 text-slate-200 transition-colors"
                >
                  Case Search &amp; AI
                </Link>
                <Link
                  href="/campus-proctor"
                  className="px-3.5 py-2 rounded-xl bg-gradient-to-r from-court-maroon to-rose-700 hover:from-rose-700 hover:to-rose-800 text-white transition-all shadow-sm"
                >
                  Campus Proctor
                </Link>
              </div>
            </div>

            <div className="text-center max-w-2xl mx-auto mb-10">
              <span className="text-xs font-bold uppercase tracking-widest text-[#881337] bg-rose-50 px-3 py-1 rounded-full border border-rose-200">
                Expanded Legal Tech Modules
              </span>
              <h2 className="text-3xl font-black text-slate-900 mt-3 tracking-tight">
                Empowering Citizens &amp; College Campuses
              </h2>
              <p className="text-sm text-slate-600 mt-2 font-medium">
                Comprehensive legal tools designed for real-world civic advocacy, landmark precedent research, and campus grievance governance.
              </p>
            </div>

            <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
              {/* Card 1: Live Court News */}
              <div className="bg-slate-50 rounded-3xl p-6 sm:p-7 border border-slate-200 hover:border-court-maroon/30 transition-all shadow-xs flex flex-col justify-between group">
                <div>
                  <div className="w-12 h-12 rounded-2xl bg-rose-100 text-court-maroon flex items-center justify-center mb-5 group-hover:scale-105 transition-transform">
                    <Newspaper size={24} />
                  </div>
                  <h3 className="text-xl font-black text-ashoka-navy mb-2">Live Court News</h3>
                  <p className="text-xs sm:text-sm text-slate-600 font-medium leading-relaxed mb-4">
                    Track breaking judgments and statutory directives from the Supreme Court, High Courts, and Central Information Commission affecting citizen &amp; student rights.
                  </p>
                </div>
                <Link
                  href="/court-news"
                  className="inline-flex items-center gap-1.5 text-xs font-bold text-court-maroon hover:text-rose-800 transition-colors pt-4 border-t border-slate-200"
                >
                  <span>Explore Judicial News Feed</span>
                  <ChevronRight size={14} />
                </Link>
              </div>

              {/* Card 2: Precedent Search & AI Summarizer */}
              <div className="bg-slate-50 rounded-3xl p-6 sm:p-7 border border-slate-200 hover:border-court-maroon/30 transition-all shadow-xs flex flex-col justify-between group">
                <div>
                  <div className="w-12 h-12 rounded-2xl bg-amber-100 text-amber-800 flex items-center justify-center mb-5 group-hover:scale-105 transition-transform">
                    <BookOpen size={24} />
                  </div>
                  <h3 className="text-xl font-black text-ashoka-navy mb-2">Case Search &amp; AI Summarizer</h3>
                  <p className="text-xs sm:text-sm text-slate-600 font-medium leading-relaxed mb-4">
                    Search landmark judgments (e.g. CBSE v. Aditya Bandopadhyay, Paramveer Singh) and let our AI extract the exact legal ratio to cite in your own RTI or appeal.
                  </p>
                </div>
                <Link
                  href="/case-search"
                  className="inline-flex items-center gap-1.5 text-xs font-bold text-court-maroon hover:text-rose-800 transition-colors pt-4 border-t border-slate-200"
                >
                  <span>Search Case Law &amp; AI</span>
                  <ChevronRight size={14} />
                </Link>
              </div>

              {/* Card 3: College Proctor & Student Grievance */}
              <div className="bg-slate-50 rounded-3xl p-6 sm:p-7 border border-slate-200 hover:border-court-maroon/30 transition-all shadow-xs flex flex-col justify-between group">
                <div>
                  <div className="w-12 h-12 rounded-2xl bg-blue-100 text-blue-800 flex items-center justify-center mb-5 group-hover:scale-105 transition-transform">
                    <GraduationCap size={24} />
                  </div>
                  <h3 className="text-xl font-black text-ashoka-navy mb-2">College Proctor &amp; Grievance</h3>
                  <p className="text-xs sm:text-sm text-slate-600 font-medium leading-relaxed mb-4">
                    Dedicated campus portal for students to file protected hostel, marksheet, fee, and facility grievances, with a Proctor dashboard enforcing UGC 15-day SLAs.
                  </p>
                </div>
                <Link
                  href="/campus-proctor"
                  className="inline-flex items-center gap-1.5 text-xs font-bold text-court-maroon hover:text-rose-800 transition-colors pt-4 border-t border-slate-200"
                >
                  <span>Open Campus Redressal Portal</span>
                  <ChevronRight size={14} />
                </Link>
              </div>
            </div>
          </div>
        </section>

        {/* COMPARISON */}
        <section
          id="comparison"
          className="py-20 bg-slate-50 border-b border-slate-300 scroll-mt-24"
        >
          <div className="max-w-6xl mx-auto px-4 sm:px-6 lg:px-8">
            <div className="max-w-3xl mb-12 text-left">
              <span className="text-xs font-bold uppercase tracking-widest text-[#881337] bg-rose-50 px-3 py-1 rounded-full border border-rose-200">
                Architectural Distinction
              </span>

              <h2 className="text-3xl sm:text-4xl font-extrabold tracking-tight text-slate-900 mt-3">
                General LLMs vs. Dedicated Legal Engine
              </h2>

              <p className="mt-2 text-slate-600 text-sm sm:text-base leading-relaxed">
                Generic AI chatbots generate natural-language responses. NyayPath is designed around statutory rules, authority mapping,
                document structure, and legal workflow.
              </p>
            </div>

            <div className="grid grid-cols-1 md:grid-cols-2 gap-8 items-stretch">
              <div className="bg-rose-50/40 border border-red-200 rounded-2xl p-6 sm:p-8 flex flex-col justify-between shadow-xs">
                <div>
                  <div className="flex items-center justify-between pb-4 border-b border-red-200/60 mb-6">
                    <div className="flex items-center gap-2.5">
                      <div className="w-8 h-8 rounded-lg bg-red-100 border border-red-200 flex items-center justify-center text-red-700">
                        <Bot className="w-4 h-4" />
                      </div>
                      <h3 className="font-bold text-base text-slate-900">
                        Standard AI Chatbots
                      </h3>
                    </div>
          
                  </div>

                  <ul className="space-y-4 text-xs text-slate-700">
                    <li className="flex items-start gap-2.5">
                      <CircleX className="w-4 h-4 text-red-500 shrink-0 mt-0.5" />
                      <span>
                        <strong>Asks "Why" or "How":</strong> May generate
                        subjective questions that don't correspond to
                        information actually held by an authority.
                      </span>
                    </li>
                    <li className="flex items-start gap-2.5">
                      <CircleX className="w-4 h-4 text-red-500 shrink-0 mt-0.5" />
                      <span>
                        <strong>Vague Authorities:</strong> Can direct letters
                        to generic departments without identifying the
                        appropriate authority.
                      </span>
                    </li>
                    <li className="flex items-start gap-2.5">
                      <CircleX className="w-4 h-4 text-red-500 shrink-0 mt-0.5" />
                      <span>
                        <strong>Missing Workflow:</strong> Often stops at
                        generating text rather than guiding the citizen through
                        the next statutory step.
                      </span>
                    </li>
                    <li className="flex items-start gap-2.5">
                      <CircleX className="w-4 h-4 text-red-500 shrink-0 mt-0.5" />
                      <span>
                        <strong>Legal Uncertainty:</strong> Responses require
                        verification against the actual statute and applicable
                        authority.
                      </span>
                    </li>
                  </ul>
                </div>
              </div>

              <div className="bg-emerald-50/50 border border-emerald-200 rounded-2xl p-6 sm:p-8 flex flex-col justify-between shadow-xs">
                <div>
                  <div className="flex items-center justify-between pb-4 border-b border-emerald-200/60 mb-6">
                    <div className="flex items-center gap-2.5">
                      <Image
                        src="/nyaypath-logo.png"
                        alt="NyayPath"
                        width={110}
                        height={32}
                        className="object-contain brightness-0"
                      />
                    </div>
                    
                  </div>

                  <ul className="space-y-4 text-xs text-slate-700">
                    <li className="flex items-start gap-2.5">
                      <CheckCircle className="w-4 h-4 text-emerald-600 shrink-0 mt-0.5" />
                      <span>
                        <strong>Grievance Extraction:</strong> Converts
                        everyday descriptions into structured legal facts and
                        possible causes of action.
                      </span>
                    </li>
                    <li className="flex items-start gap-2.5">
                      <CheckCircle className="w-4 h-4 text-emerald-600 shrink-0 mt-0.5" />
                      <span>
                        <strong>Authority Mapping:</strong> Identifies the
                        likely public authority responsible for the matter.
                      </span>
                    </li>
                    <li className="flex items-start gap-2.5">
                      <CheckCircle className="w-4 h-4 text-emerald-600 shrink-0 mt-0.5" />
                      <span>
                        <strong>Legal Route:</strong> Helps distinguish
                        information requests, grievances, appeals, and other
                        available routes.
                      </span>
                    </li>
                    <li className="flex items-start gap-2.5">
                      <CheckCircle className="w-4 h-4 text-emerald-600 shrink-0 mt-0.5" />
                      <span>
                        <strong>Structured Drafting:</strong> Produces
                        documents around identified facts, authorities,
                        statutory provisions, and procedural requirements.
                      </span>
                    </li>
                  </ul>
                </div>
              </div>
            </div>
          </div>
        </section>

        {/* PDF / WORKFLOW */}
        <section
          id="export-pipeline"
          className="py-20 bg-white border-b border-slate-300 font-sans scroll-mt-24"
        >
          <div className="max-w-6xl mx-auto px-4 sm:px-6 lg:px-8">
            <div className="max-w-3xl mb-10 text-left">
              <span className="text-sm font-bold uppercase tracking-widest text-[#065F46] bg-emerald-50 px-3 py-1 rounded-full border border-emerald-200">
                Automated Export Pipeline
              </span>

              <h2 className="text-3xl sm:text-4xl font-extrabold tracking-tight text-slate-900 mt-3">
                From Legal Understanding to Action
              </h2>

              <p className="mt-2 text-slate-600 text-base sm:text-lg leading-relaxed">
                Structures raw grievances into actionable, statutory documents.
              </p>
            </div>

            <div className="grid grid-cols-1 lg:grid-cols-12 gap-8 items-stretch">
              <div className="lg:col-span-7 bg-sky-50/40 border border-sky-200 rounded-2xl p-6 sm:p-8 flex flex-col justify-between shadow-xs">
                <div>
                  <div className="flex items-center justify-between pb-4 border-b border-sky-200/60 mb-6">
                    <div>
                      <span className="text-xs bg-sky-100 text-sky-800 border border-sky-200 px-2.5 py-1 rounded font-bold uppercase">
                        Unstructured Data · RTI Act 2005
                      </span>
                      <h3 className="text-xl font-extrabold text-slate-900 uppercase mt-2">
                        Form 'A' Statutory RTI Petition
                      </h3>
                    </div>

                    <div className="text-right text-xs text-slate-500">
                      <div>Ref: RTI/2026/08/941</div>
                      <div className="text-sky-700 font-bold">STATUS: VALIDATED</div>
                    </div>
                  </div>

                  <div className="space-y-4 text-sm text-slate-800 leading-relaxed">
                    <div>
                      <span className="text-slate-400 font-bold block text-xs uppercase">
                        To Public Information Officer:
                      </span>
                      <p className="font-semibold text-slate-900 text-base">{preset.authority}</p>
                    </div>

                    <div className="p-4 bg-white rounded-lg border border-sky-200">
                      <span className="text-slate-400 text-xs font-bold block mb-1 uppercase">
                        Subject / Prayer Clauses Under Sec. 6(1):
                      </span>
                      <ul className="space-y-1.5 text-sm text-slate-700">
                        {preset.legalDraftSnippet.map((line, idx) => (
                          <li key={idx}>{line}</li>
                        ))}
                      </ul>
                    </div>
                  </div>
                </div>

                <div className="mt-6 pt-4 border-t border-sky-200/60 text-xs text-slate-500">
                  Format: A-4 Ready Statutory Document
                </div>
              </div>

              <div className="lg:col-span-5 bg-emerald-50/50 border border-emerald-200 rounded-2xl p-6 sm:p-8 flex flex-col justify-between shadow-xs">
                <div>
                  <div className="pb-4 border-b border-emerald-200/60 mb-6">
                    <div className="flex items-center gap-2">
                      <Activity className="w-5 h-5 text-emerald-600 shrink-0" />
                      <h3 className="text-lg font-bold text-slate-900">Verified Impact & Outcomes</h3>
                    </div>
                  </div>

                  <div className="space-y-5">
                    {[
                      [
                        "Statutory Jurisdiction Mapped",
                        "Successfully matched to the exact Public Information Officer (PIO) with zero misdirection.",
                      ],
                      [
                        "Strict Sec. 6(1) Compliance",
                        "Eliminated subjective language to guarantee legal admissibility and eliminate rejections.",
                      ],
                      [
                        "Sec. 20 Penalty Clause Enforced",
                        "Bound authority to mandatory 30-day response under threat of daily personal fines.",
                      ],
                      [
                        "Court-Ready File Generated",
                        "Exported a fully compliant petition ready for immediate submission or judicial appeal.",
                      ],
                    ].map(([title, description]) => (
                      <div key={title} className="flex items-start gap-3">
                        <CheckCircle className="w-5 h-5 text-emerald-600 shrink-0 mt-0.5" />
                        <div>
                          <span className="text-sm font-bold text-slate-900 block">
                            {title}
                          </span>
                          <p className="text-xs text-slate-600 leading-snug">
                            {description}
                          </p>
                        </div>
                      </div>
                    ))}
                  </div>
                </div>

                <div className="mt-8 pt-4 border-t border-emerald-200/60 text-xs text-emerald-800 font-bold text-center">
                  ✓ High-admissibility legal outcome archived
                </div>
              </div>
            </div>
          </div>
        </section>

        {/* LEGAL FOUNDATION */}
        <section
          id="the-law"
          className="py-20 sm:py-28 bg-slate-50"
        >
          <div className="max-w-6xl mx-auto px-4 sm:px-6 lg:px-8">
            <div className="max-w-3xl mb-14 text-left">
              <span className="text-xs font-bold uppercase tracking-widest text-[#065F46] bg-emerald-50 px-3 py-1 rounded-full border border-emerald-200">
                Statutory Jurisdiction
              </span>

              <h2 className="text-3xl sm:text-4xl font-extrabold tracking-tight text-slate-900 mt-3">
                The Legal Basis of the Platform
              </h2>

              <p className="mt-3 text-slate-600 text-base leading-relaxed">
                The platform is built around Indian administrative,
                transparency, grievance redressal, and consumer-protection
                frameworks.
              </p>
            </div>

            <div className="grid grid-cols-1 md:grid-cols-3 gap-8">
              <div className="bg-white border border-slate-300 rounded-2xl p-6 sm:p-8 flex flex-col justify-between shadow-2xs">
                <div>
                  <div className="w-10 h-10 rounded-xl bg-[#881337] text-white flex items-center justify-center mb-5">
                    <Landmark className="w-5 h-5 text-amber-200" />
                  </div>
                  <h3 className="text-lg font-bold tracking-tight text-slate-900 mb-2.5">
                    The Right to Information Act, 2005
                  </h3>
                  <p className="text-sm text-slate-600 leading-relaxed">
                    The system maps civic information problems to relevant RTI
                    provisions and structures requests around records held by
                    public authorities.
                  </p>
                </div>
                <div className="mt-6 pt-4 border-t border-slate-200 text-xs font-mono text-slate-500">
                  Ref: RTI Act, 2005 Sec. 6(1)
                </div>
              </div>

              <div className="bg-white border border-slate-300 rounded-2xl p-6 sm:p-8 flex flex-col justify-between shadow-2xs">
                <div>
                  <div className="w-10 h-10 rounded-xl bg-[#0F172A] text-white flex items-center justify-center mb-5">
                    <Gavel className="w-5 h-5 text-emerald-400" />
                  </div>
                  <h3 className="text-lg font-bold tracking-tight text-slate-900 mb-2.5">
                    Statutory Appeals
                  </h3>
                  <p className="text-sm text-slate-600 leading-relaxed">
                    Where an RTI request is denied or improperly handled, the
                    platform can structure the relevant appeal pathway and
                    supporting grounds.
                  </p>
                </div>
                <div className="mt-6 pt-4 border-t border-slate-200 text-xs font-mono text-slate-500">
                  Ref: RTI Act, 2005 Sec. 19 &amp; 20
                </div>
              </div>

              <div className="bg-white border border-slate-300 rounded-2xl p-6 sm:p-8 flex flex-col justify-between shadow-2xs">
                <div>
                  <div className="w-10 h-10 rounded-xl bg-[#065F46] text-white flex items-center justify-center mb-5">
                    <FileCheck className="w-5 h-5 text-white" />
                  </div>
                  <h3 className="text-lg font-bold tracking-tight text-slate-900 mb-2.5">
                    Grievance Redressal
                  </h3>
                  <p className="text-sm text-slate-600 leading-relaxed">
                    Civic issues can involve different authorities and legal
                    routes. The platform is designed to help identify the
                    appropriate route before drafting action.
                  </p>
                </div>
                <div className="mt-6 pt-4 border-t border-slate-200 text-xs font-mono text-slate-500">
                  Ref: DARPG CPGRAMS &amp; CPA 2019
                </div>
              </div>
            </div>
          </div>
        </section>
      </main>

      {/* MODAL */}
      {modalOpen && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/60 backdrop-blur-sm">
          <div className="bg-white rounded-2xl max-w-2xl w-full max-h-[90vh] flex flex-col shadow-2xl border border-slate-300 animate-in fade-in zoom-in duration-200">
            <div className="px-6 py-4 border-b border-slate-200 flex items-center justify-between bg-slate-50 rounded-t-2xl">
              <div className="flex items-center gap-2">
                <Gavel className="w-5 h-5 text-[#881337]" />
                <h3 className="font-bold text-base text-slate-900">
                  Certified RTI Statutory Petition Preview
                </h3>
              </div>
              <button
                onClick={() => setModalOpen(false)}
                className="w-8 h-8 rounded-full hover:bg-slate-200 flex items-center justify-center text-slate-500 cursor-pointer"
              >
                <X className="w-4 h-4" />
              </button>
            </div>

            <div className="p-6 overflow-y-auto font-mono text-xs text-slate-800 leading-relaxed space-y-4 bg-white">
              <div className="text-center font-bold text-sm text-[#881337] border-b pb-2 border-slate-200">
                FORM 'A' - APPLICATION UNDER SECTION 6(1) OF THE RTI ACT, 2005
              </div>
              <div>
                <p><strong>TO:</strong></p>
                <p className="pl-4">{preset.authority}</p>
              </div>
              <div className="space-y-1">
                <p><strong>1. Full Name of Applicant:</strong> [Citizen Name]</p>
                <p><strong>2. Address:</strong> [Citizen Residential Address / Ward Zone]</p>
                <p><strong>3. Citizen Status:</strong> Citizen of India (Art. 19(1)(a))</p>
              </div>
              <div className="space-y-1.5 pt-2 border-t border-slate-200">
                <p className="font-bold text-slate-900">4. PARTICULARS OF INFORMATION SOUGHT:</p>
                <p className="text-slate-600"><em>Subject Matter: {preset.tag}</em></p>
                <div className="pl-4 space-y-2 text-slate-800">
                  {preset.legalDraftSnippet.map((point, idx) => (
                    <p key={idx}>{point}</p>
                  ))}
                </div>
              </div>
              <div className="space-y-1 pt-2 border-t border-slate-200 text-[11px] text-slate-600">
                <p><strong>5. Statutory Time Limit:</strong> Mandated reply within {preset.statutoryClock} under Section 7(1).</p>
                <p><strong>6. Statutory Penalty Notice:</strong> Deliberate refusal or delay attracts penalty under Section 20(1) (₹250/day up to ₹25,000) on the Public Information Officer.</p>
                <p><strong>7. RTI Fee:</strong> ₹10/- prescribed fee remitted via Postal Order / Court Fee Stamp.</p>
              </div>
              <div className="pt-4 flex justify-between text-slate-500 text-[11px]">
                <p>Date: {new Date().toLocaleDateString("en-IN")}</p>
                <p>Signature of Applicant</p>
              </div>
            </div>

            <div className="px-6 py-4 border-t border-slate-200 bg-slate-50 rounded-b-2xl flex flex-col sm:flex-row items-center justify-between gap-3">
              <span className="text-xs text-slate-500 font-medium">
                ✓ Ready to print and dispatch
              </span>
              <div className="flex items-center gap-2 w-full sm:w-auto">
                <button
                  onClick={handleCopyDraft}
                  className="flex-1 sm:flex-none px-4 py-2 rounded-lg bg-slate-800 hover:bg-slate-700 text-white text-xs font-bold flex items-center justify-center gap-1.5 cursor-pointer"
                >
                  {copied ? <Check className="w-3.5 h-3.5 text-emerald-400" /> : <Copy className="w-3.5 h-3.5" />}
                  <span>{copied ? "Copied" : "Copy All"}</span>
                </button>
                <button
                  onClick={handlePrint}
                  className="flex-1 sm:flex-none px-4 py-2 rounded-lg btn-maroon-solid text-white text-xs font-bold flex items-center justify-center gap-1.5 cursor-pointer"
                >
                  <Printer className="w-3.5 h-3.5" />
                  <span>Print Form</span>
                </button>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* FOOTER */}
      <footer className="border-t border-slate-300 bg-[#0F172A] text-slate-300">
        <div className="max-w-6xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="py-14 grid grid-cols-1 md:grid-cols-12 gap-10">
            <div className="md:col-span-6">
              <Image
                src="/nyaypath-logo.png"
                alt="NyayPath"
                width={220}
                height={140}
                className="object-contain brightness-0 invert"
              />
              <p className="mt-5 max-w-md text-sm leading-relaxed text-slate-400">
                A civic technology platform designed to help citizens
                understand their rights, identify the appropriate legal route,
                and turn everyday grievances into structured action.
              </p>
              <div className="mt-6 inline-flex items-center gap-2 px-3 py-1.5 rounded-full border border-slate-700 bg-slate-800/60">
                <span className="w-1.5 h-1.5 rounded-full bg-emerald-400" />
              </div>
            </div>

            <div className="md:col-span-3">
              <h4 className="text-[10px] font-bold uppercase tracking-widest text-slate-500">
                Platform
              </h4>
              <div className="mt-4 flex flex-col gap-3 text-sm">
                <a href="#comparison" className="hover:text-white transition-colors">
                  Why NyayPath
                </a>
                <button onClick={handleStartIntake} className="text-left hover:text-white transition-colors cursor-pointer">
                  Legal Analysis
                </button>
                <a href="#the-law" className="hover:text-white transition-colors">
                  Legal Foundation
                </a>
              </div>
            </div>

            <div className="md:col-span-3">
              <h4 className="text-[10px] font-bold uppercase tracking-widest text-slate-500">
                Built Around
              </h4>
              <div className="mt-4 space-y-3 text-sm text-slate-400">
                <div className="flex items-center gap-2">
                  <Shield className="w-3.5 h-3.5 text-emerald-400" />
                  <span>RTI Act, 2005</span>
                </div>
                <div className="flex items-center gap-2">
                  <Gavel className="w-3.5 h-3.5 text-amber-300" />
                  <span>Statutory Appeals</span>
                </div>
                <div className="flex items-center gap-2">
                  <Landmark className="w-3.5 h-3.5 text-slate-400" />
                  <span>Public Grievance Systems</span>
                </div>
              </div>
            </div>
          </div>

          <div className="border-t border-slate-800 py-5 flex flex-col sm:flex-row items-center justify-between gap-3">
            <span className="text-[10px] font-mono text-slate-500">
              NYAYPATH · CIVIC TECHNOLOGY
            </span>
            <div className="flex items-center gap-4 text-[10px] font-mono text-slate-500">
              <span>OPEN SOURCE</span>
              <span className="text-slate-700">•</span>
              <span>INDIA</span>
              <span className="text-slate-700">•</span>
              <span>2026</span>
            </div>
          </div>
        </div>
      </footer>
    </div>
  );
}
