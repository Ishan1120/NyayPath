'use client';
import { motion } from 'framer-motion'
import { MapPin, Building, CheckCircle2 } from 'lucide-react'

export default function RTIConfirmationCard({ departmentInfo, onConfirm }) {
  if (!departmentInfo) return null
  return (
    <motion.div
      initial={{ opacity: 0, y: 10 }}
      animate={{ opacity: 1, y: 0 }}
      className="glass-card p-5 border-l-4 border-l-blue-600 shadow-md"
    >
      <div className="flex items-start gap-3 mb-4">
        <MapPin className="text-blue-600 flex-shrink-0 mt-1" size={18} />
        <div>
          <h3 className="font-bold text-slate-900">Jurisdiction Verified</h3>
          <p className="text-sm text-slate-600 mt-1">
            Based on your location, this RTI application should be filed with:
          </p>
        </div>
      </div>
      <div className="bg-slate-50 p-4 rounded-xl mb-5 border border-slate-200">
        <div className="flex items-center gap-2 mb-2">
          <Building size={16} className="text-blue-600" />
          <span className="font-bold text-slate-800">{departmentInfo.public_authority_name || departmentInfo.department_name}</span>
        </div>
        <p className="text-sm text-slate-600 leading-relaxed font-medium">{departmentInfo.suggested_address_template || departmentInfo.address}</p>
      </div>
      <button
        onClick={onConfirm}
        className="btn-primary w-full justify-center py-3"
      >
        <CheckCircle2 size={16} /> Confirm & Run Risk Analysis
      </button>
    </motion.div>
  )
}
