'use client';
import { useState } from 'react';
import { motion } from 'framer-motion';
import { useRouter } from 'next/navigation';
import { 
  Scale, 
  Upload, 
  FileText, 
  User, 
  MapPin, 
  Building2, 
  ArrowRight, 
  Loader2, 
  CheckCircle,
  TriangleAlert,
  ArrowLeft
} from 'lucide-react';
import useCaseStore from '@/store/caseStore';
import { grievanceGenerate } from '@/lib/api';

export default function GrievanceFormView() {
  const router = useRouter();
  const { caseId, userProblem, formData, setFormData, classifyResult, setGrievanceResult, language, setStage } = useCaseStore();
  
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [files, setFiles] = useState<File[]>([]);

  const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    if (e.target.files) {
      setFiles(Array.from(e.target.files));
    }
  };

  const handleGenerate = async (e: React.FormEvent) => {
    e.preventDefault();
    setLoading(true);
    setError(null);
    
    try {
      const payload = {
        case_id: caseId,
        problem_text: userProblem,
        language: language || 'English',
        form_data: {
          ...formData,
        }
      };

      const result = await grievanceGenerate(payload);
      setGrievanceResult(result);
      setStage('GRIEVANCE_COMPLETED');
      router.push('/dashboard/grievance/result');
      
    } catch (err: any) {
      console.error("Grievance Generation Error:", err);
      setError(err?.response?.data?.detail || "Failed to generate grievance. Please try again.");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div 
      className="min-h-screen p-4 sm:p-6 lg:p-8 font-sans flex items-center justify-center bg-cover bg-center bg-no-repeat relative"
      style={{ backgroundImage: "url('/bg.image.png')" }}
    >
      <div className="w-full max-w-3xl space-y-6 relative z-10">
        
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 mb-4 bg-white/95 backdrop-blur-sm p-4 rounded-2xl border border-slate-300 shadow-sm">
          <div className="flex items-center gap-3">
            <button 
              onClick={() => router.push('/dashboard')}
              className="p-2.5 rounded-xl bg-white border border-slate-300 text-slate-600 hover:text-ashoka-navy hover:bg-slate-50 transition shadow-sm cursor-pointer"
            >
              <ArrowLeft size={18} />
            </button>
            <div>
              <div className="flex items-center gap-2">
                <Scale className="w-5 h-5 text-court-maroon" />
                <h1 className="text-xl sm:text-2xl font-extrabold text-ashoka-navy tracking-tight drop-shadow-sm">
                  Grievance & Relief Setup
                </h1>
              </div>
              <p className="text-sm text-slate-600 mt-1 font-medium">
                Review your details before generating the legal notice.
              </p>
            </div>
          </div>
          {caseId && (
            <div className="hidden sm:flex items-center gap-2 px-4 py-2 bg-slate-50 border border-slate-200 rounded-xl shadow-sm text-xs font-bold text-slate-600 uppercase tracking-wider">
              ID: {caseId}
            </div>
          )}
        </div>

        <motion.form 
          initial={{ opacity: 0, y: 10 }}
          animate={{ opacity: 1, y: 0 }}
          onSubmit={handleGenerate} 
          className="space-y-6"
        >
          <div className="bg-white/95 backdrop-blur-sm rounded-3xl p-6 sm:p-8 border border-slate-300 shadow-xl">
            <h2 className="text-sm font-bold font-sans tracking-tight uppercase text-court-maroon mb-6 flex items-center gap-2">
              <User size={16} className="text-court-maroon" />
              1. Complainant Details
            </h2>
            
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-5">
              <div className="space-y-2 text-left">
                <label className="text-xs font-bold text-slate-600 uppercase tracking-wide">Full Name</label>
                <input 
                  type="text"
                  required
                  value={formData.applicant_name || ''}
                  onChange={e => setFormData({ ...formData, applicant_name: e.target.value })}
                  placeholder="e.g. Rahul Sharma"
                  className="w-full bg-[#F8FAFC] border border-slate-300 rounded-xl p-3.5 text-sm text-ashoka-navy font-medium placeholder-slate-400 focus:outline-none focus:border-[#FF9933] focus:ring-1 focus:ring-[#FF9933] transition-all"
                />
              </div>
              
              <div className="space-y-2 text-left">
                <label className="text-xs font-bold text-slate-600 uppercase tracking-wide">Contact Details</label>
                <input 
                  type="text"
                  value={formData.applicant_contact || ''}
                  onChange={e => setFormData({ ...formData, applicant_contact: e.target.value })}
                  placeholder="Phone or Email"
                  className="w-full bg-[#F8FAFC] border border-slate-300 rounded-xl p-3.5 text-sm text-ashoka-navy font-medium placeholder-slate-400 focus:outline-none focus:border-[#FF9933] focus:ring-1 focus:ring-[#FF9933] transition-all"
                />
              </div>
              
              <div className="space-y-2 sm:col-span-2 text-left">
                <label className="text-xs font-bold text-slate-600 uppercase tracking-wide">City / District</label>
                <div className="relative">
                  <MapPin size={16} className="absolute left-3.5 top-3.5 text-slate-400" />
                  <input 
                    type="text"
                    required
                    value={formData.applicant_city || ''}
                    onChange={e => setFormData({ ...formData, applicant_city: e.target.value })}
                    placeholder="e.g. Jaipur, Rajasthan"
                    className="w-full bg-[#F8FAFC] border border-slate-300 rounded-xl p-3.5 pl-10 text-sm text-ashoka-navy font-medium placeholder-slate-400 focus:outline-none focus:border-[#FF9933] focus:ring-1 focus:ring-[#FF9933] transition-all"
                  />
                </div>
              </div>
            </div>
          </div>

          <div className="bg-white/95 backdrop-blur-sm rounded-3xl p-6 sm:p-8 border border-slate-300 shadow-xl">
            <h2 className="text-sm font-bold font-sans tracking-tight uppercase text-court-maroon mb-6 flex items-center gap-2">
              <Building2 size={16} className="text-court-maroon" />
              2. Respondent Details
            </h2>
            
            <div className="space-y-2 text-left">
              <label className="text-xs font-bold text-slate-600 uppercase tracking-wide">Target Department / Company</label>
              <input 
                type="text"
                required
                value={formData.target_department || classifyResult?.sub_category || ''}
                onChange={e => setFormData({ ...formData, target_department: e.target.value })}
                placeholder="e.g. Municipal Corporation / E-Commerce Platform"
                className="w-full bg-[#F8FAFC] border border-slate-300 rounded-xl p-3.5 text-sm text-ashoka-navy font-bold placeholder-slate-400 focus:outline-none focus:border-[#FF9933] focus:ring-1 focus:ring-[#FF9933] transition-all tracking-tight"
              />
              <p className="text-xs text-slate-500 mt-1.5 font-medium">
                The AI will use this to direct your legal notice to the correct authority.
              </p>
            </div>
          </div>

          <div className="bg-white/95 backdrop-blur-sm rounded-3xl p-6 sm:p-8 border border-slate-300 shadow-xl">
            <h2 className="text-sm font-bold font-sans tracking-tight uppercase text-court-maroon mb-6 flex items-center gap-2">
              <FileText size={16} className="text-court-maroon" />
              3. Evidence & Proofs (Optional)
            </h2>
            
            <label className="border-2 border-dashed border-slate-300 bg-slate-50 hover:bg-slate-100 transition-colors rounded-2xl p-8 flex flex-col items-center justify-center cursor-pointer group text-center shadow-inner">
              <div className="w-12 h-12 bg-white rounded-full flex items-center justify-center shadow-sm border border-slate-200 mb-3 group-hover:scale-110 transition-transform">
                <Upload size={20} className="text-ashoka-navy" />
              </div>
              <span className="text-sm font-bold text-ashoka-navy">Click to upload files</span>
              <span className="text-xs text-slate-500 mt-1 font-medium">Images, PDFs, or Receipts (Max 5MB)</span>
              <input 
                type="file" 
                multiple 
                onChange={handleFileChange}
                className="hidden" 
              />
            </label>
            
            {files.length > 0 && (
              <div className="mt-4 space-y-2 text-left">
                <h4 className="text-xs font-bold text-slate-500 uppercase tracking-wider mb-2">Attached Files:</h4>
                {files.map((file, idx) => (
                  <div key={idx} className="flex items-center gap-2 text-sm text-slate-700 font-medium bg-[#F8FAFC] p-3 rounded-xl border border-slate-200 shadow-sm">
                    <CheckCircle size={16} className="text-emerald-600 shrink-0" />
                    <span className="truncate">{file.name}</span>
                  </div>
                ))}
              </div>
            )}
          </div>

          {error && (
            <motion.div 
              initial={{ opacity: 0, scale: 0.95 }}
              animate={{ opacity: 1, scale: 1 }}
              className="p-4 bg-red-50 text-red-700 text-sm font-medium rounded-xl border border-red-200 flex items-start gap-3 shadow-sm text-left"
            >
              <TriangleAlert size={18} className="shrink-0 mt-0.5" />
              <p>{error}</p>
            </motion.div>
          )}

          <div className="pt-2">
            <button 
              type="submit" 
              disabled={loading}
              className="btn-primary w-full justify-center text-lg py-4 cursor-pointer bg-gradient-to-r from-court-maroon via-rose-700 to-court-maroon hover:from-rose-700 hover:to-rose-800 transition-colors text-white disabled:opacity-70 shadow-md rounded-2xl flex items-center gap-2 font-bold tracking-tight"
            >
              {loading ? (
                <>
                  <Loader2 size={20} className="animate-spin" />
                  <span>Drafting Legal Notice...</span>
                </>
              ) : (
                <>
                  <span>Generate Grievance Draft</span>
                  <ArrowRight size={20} />
                </>
              )}
            </button>
            <p className="text-center text-xs text-slate-500 mt-4 font-medium">
              You will be able to review and edit the draft on the next page before downloading.
            </p>
          </div>
        </motion.form>
      </div>
    </div>
  );
}
