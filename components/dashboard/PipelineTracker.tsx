'use client';
import { motion } from 'framer-motion'
import { CheckCircle2, Circle, Loader2 } from 'lucide-react'

const STAGES = [
  { id: 'IDLE',                label: 'New Case' },
  { id: 'INITIALIZING',        label: 'Initializing' },
  { id: 'CLASSIFYING',         label: 'Classifying' },
  { id: 'RTI_GATHERING',       label: 'Info Gathering' },
  { id: 'GRIEVANCE_GATHERING', label: 'Info Gathering' },
  { id: 'PREDICTING',          label: 'Risk Analysis' },
  { id: 'IMPROVING',           label: 'Remolding RTI' },
  { id: 'GRIEVANCE_ANALYZING', label: 'Legal Analysis' },
  { id: 'COMPLETE',            label: 'Complete' },
]

// Map each stage to an ordered pipeline index for display
const RTI_PIPELINE = [
  'IDLE', 'INITIALIZING', 'CLASSIFYING', 'RTI_GATHERING', 'PREDICTING', 'IMPROVING', 'COMPLETE',
]
const GRIEVANCE_PIPELINE = [
  'IDLE', 'INITIALIZING', 'CLASSIFYING', 'GRIEVANCE_GATHERING', 'GRIEVANCE_ANALYZING', 'COMPLETE',
]
const OTHER_PIPELINE = ['IDLE', 'INITIALIZING', 'CLASSIFYING', 'COMPLETE']

const LABELS = {
  IDLE:                'New Case',
  INITIALIZING:        'Initializing',
  CLASSIFYING:         'Classifying',
  RTI_GATHERING:       'Info Gathering',
  GRIEVANCE_GATHERING: 'Info Gathering',
  PREDICTING:          'Risk Analysis',
  IMPROVING:           'Remolding RTI',
  GRIEVANCE_ANALYZING: 'Legal Analysis',
  COMPLETE:            'Complete',
}

export default function PipelineTracker({ stage, route }) {
  const pipeline =
    route === 'RTI'
      ? RTI_PIPELINE
      : route === 'Rights/Grievance'
      ? GRIEVANCE_PIPELINE
      : OTHER_PIPELINE

  const current = pipeline.indexOf(stage)

  return (
    <div className="flex items-center gap-1 overflow-x-auto pb-1">
      {pipeline.map((s, i) => {
        const done    = i < current
        const active  = i === current
        const pending = i > current

        return (
          <div key={s} className="flex items-center gap-1 flex-shrink-0">
            <motion.div
              initial={{ scale: 0.8, opacity: 0 }}
              animate={{ scale: 1, opacity: 1 }}
              transition={{ delay: i * 0.05 }}
              className={`flex items-center gap-1.5 px-3 py-1.5 rounded-full text-xs font-medium transition-all duration-300 ${
                done
                  ? 'bg-emerald-500/20 text-emerald-400 border border-emerald-500/30'
                  : active
                  ? 'bg-brand-blue/20 text-blue-400 border border-brand-blue/40'
                  : 'bg-white/5 text-slate-600 border border-white/5'
              }`}
            >
              {done ? (
                <CheckCircle2 size={12} />
              ) : active ? (
                <Loader2 size={12} className="animate-spin" />
              ) : (
                <Circle size={12} />
              )}
              <span className="hidden sm:inline">{LABELS[s]}</span>
            </motion.div>
            {i < pipeline.length - 1 && (
              <div
                className={`h-px w-4 flex-shrink-0 transition-all duration-500 ${
                  i < current ? 'bg-emerald-500/50' : 'bg-white/10'
                }`}
              />
            )}
          </div>
        )
      })}
    </div>
  )
}
