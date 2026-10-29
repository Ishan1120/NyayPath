'use client';
import { useState } from 'react'
import { motion } from 'framer-motion'
import { Hash, Copy, Check } from 'lucide-react'

export default function CaseIdBadge({ caseId }) {
  const [copied, setCopied] = useState(false)

  if (!caseId) return null

  const handleCopy = () => {
    navigator.clipboard.writeText(caseId)
    setCopied(true)
    setTimeout(() => setCopied(false), 2000)
  }

  return (
    <motion.div
      initial={{ scale: 0.7, opacity: 0, y: -10 }}
      animate={{ scale: 1, opacity: 1, y: 0 }}
      transition={{ type: 'spring', stiffness: 300, damping: 20 }}
      onClick={handleCopy}
      title="Click to copy Passkey"
      className="inline-flex items-center gap-2 px-3 py-1.5 bg-slate-100 border border-slate-200 rounded-full shadow-sm cursor-pointer hover:bg-slate-200 transition-colors"
    >
      {copied ? <Check size={13} className="text-emerald-600" /> : <Hash size={13} className="text-slate-400" />}
      <span className="text-xs font-mono font-bold text-slate-700 tracking-widest">{caseId}</span>
      <Copy size={12} className="text-slate-400 ml-1" />
    </motion.div>
  )
}
