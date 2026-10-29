import React, { useState, useEffect } from 'react';
import { motion } from 'framer-motion';
import { RadialBarChart, RadialBar, PolarAngleAxis, ResponsiveContainer, Cell } from 'recharts';
import { TrendingUp, TrendingDown, Minus } from 'lucide-react';

const COLORS: Record<string, string> = {
  full_disclosure: '#059669',
  partial_disclosure: '#d97706',
  rejection: '#dc2626',
};

const LABELS: Record<string, string> = {
  full_disclosure: 'Full Disclosure',
  partial_disclosure: 'Partial Disclosure',
  rejection: 'Rejection',
};

function AnimatedNumber({ value }: { value: number }) {
  const [display, setDisplay] = useState(0);

  useEffect(() => {
    let start = 0;
    const target = Math.round(value * 100);
    const step = Math.ceil(target / 40);
    const timer = setInterval(() => {
      start = Math.min(start + step, target);
      setDisplay(start);
      if (start >= target) clearInterval(timer);
    }, 25);
    return () => clearInterval(timer);
  }, [value]);

  return <>{display}</>;
}

interface RiskMeterProps {
  prediction?: string;
  probabilities?: Record<string, number>;
}

export default function RiskMeter({ prediction = 'PARTIAL', probabilities }: RiskMeterProps) {
  const [mounted, setMounted] = useState(false);

  useEffect(() => {
    setMounted(true);
  }, []);

  if (!probabilities) return null;

  const data = Object.entries(probabilities).map(([key, val]) => ({
    key,
    name: LABELS[key] || key,
    value: Math.round(val * 100),
    fill: COLORS[key] || '#2563eb',
  }));

  const dominant = Object.entries(probabilities).reduce((a, b) => (b[1] > a[1] ? b : a), [
    'partial_disclosure',
    0,
  ]);
  const dominantColor = COLORS[dominant[0]] || '#2563eb';

  const PREDICTION_ICON: Record<string, any> = {
    FULL: TrendingUp,
    PARTIAL: Minus,
    REJECTION: TrendingDown,
  };
  const PredIcon = PREDICTION_ICON[prediction] || Minus;

  return (
    <motion.div initial={{ opacity: 0, scale: 0.95 }} animate={{ opacity: 1, scale: 1 }} className="space-y-4">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2 px-3 py-1.5 bg-slate-50 border border-slate-200 rounded-full shadow-sm">
          <PredIcon size={16} style={{ color: dominantColor }} />
          <span className="text-xs font-bold uppercase tracking-wider" style={{ color: dominantColor }}>
            {prediction} LIKELY
          </span>
        </div>
      </div>

      <div className="h-48">
        {mounted ? (
          <ResponsiveContainer width="100%" height="100%">
            <RadialBarChart
              cx="50%"
              cy="50%"
              innerRadius="35%"
              outerRadius="85%"
              data={data}
              startAngle={90}
              endAngle={-270}
            >
              <PolarAngleAxis type="number" domain={[0, 100]} tick={false} />
              <RadialBar dataKey="value" cornerRadius={6} background={{ fill: '#f1f5f9' }}>
                {data.map((entry) => (
                  <Cell key={entry.key} fill={entry.fill} />
                ))}
              </RadialBar>
            </RadialBarChart>
          </ResponsiveContainer>
        ) : (
          <div className="h-full w-full flex items-center justify-center bg-slate-50 rounded-xl">
            <span className="text-xs text-slate-400 font-mono">Loading metrics...</span>
          </div>
        )}
      </div>

      <div className="space-y-3 bg-slate-50 p-4 rounded-xl border border-slate-200">
        {data.map((item) => (
          <div key={item.key} className="flex items-center gap-3">
            <div className="w-3 h-3 rounded-full shadow-sm" style={{ background: item.fill }} />
            <span className="text-sm font-semibold text-slate-700 flex-1">{item.name}</span>
            <div className="flex items-center gap-3">
              <div className="w-24 h-2 bg-slate-200 rounded-full overflow-hidden shadow-inner">
                <motion.div
                  initial={{ width: 0 }}
                  animate={{ width: `${item.value}%` }}
                  transition={{ duration: 0.8, ease: 'easeOut', delay: 0.2 }}
                  className="h-full rounded-full"
                  style={{ background: item.fill }}
                />
              </div>
              <span className="text-sm font-bold w-10 text-right" style={{ color: item.fill }}>
                <AnimatedNumber value={probabilities[item.key]} />%
              </span>
            </div>
          </div>
        ))}
      </div>
    </motion.div>
  );
}
