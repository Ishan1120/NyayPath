'use client';
import { motion } from 'framer-motion'
import { AlertTriangle, AlertCircle, Info } from 'lucide-react'

const SEVERITY = {
  HIGH:   { bg: 'bg-red-50',    border: 'border-red-200',   text: 'text-red-700',   icon: AlertTriangle, label: 'HIGH' },
  MEDIUM: { bg: 'bg-amber-50',  border: 'border-amber-200', text: 'text-amber-700', icon: AlertCircle,   label: 'MEDIUM' },
  LOW:    { bg: 'bg-blue-50',   border: 'border-blue-200',  text: 'text-blue-700',  icon: Info,          label: 'LOW' },
}

export default function RiskCard({ risk, index = 0 }) {
  const s = SEVERITY[risk.severity] || SEVERITY.MEDIUM
  const Icon = s.icon

  return (
    <motion.div
      initial={{ opacity: 0, y: 12 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ delay: index * 0.1 }}
      className={`p-4 rounded-xl border shadow-sm ${s.bg} ${s.border}`}
    >
      <div className="flex items-start gap-3">
        <Icon size={18} className={`${s.text} mt-0.5 flex-shrink-0`} />
        <div>
          <div className="flex items-center gap-2 mb-1">
            <span className={`text-xs font-bold uppercase tracking-wider ${s.text}`}>
              {s.label}
            </span>
            <span className="text-xs text-slate-500 font-mono bg-white px-2 py-0.5 rounded border border-slate-200">
              {risk.risk_code}
            </span>
          </div>
          <p className="text-sm text-slate-800 font-medium leading-relaxed mt-1">{risk.description}</p>
        </div>
      </div>
    </motion.div>
  )
}
