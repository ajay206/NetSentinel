import React from 'react';
import { useModelInfo } from '../hooks/useObs';

/** W24: which fault-classifier version is serving, and did it pass the eval gate? */
export const ModelVersionChip: React.FC = () => {
  const info = useModelInfo().data;
  if (!info || !info.version) return null;
  const gate = info.gate;
  const tone = !gate ? 'bg-slate-500/10 text-slate-700' : gate.passed ? 'bg-emerald-500/15 text-emerald-700' : 'bg-red-500/15 text-red-700';
  const gateText = !gate ? 'not gated' : gate.passed ? 'gate pass' : 'gate blocked';
  const f1 = info.metrics?.macro_f1;
  const tip = [
    `Fault classifier ${info.version}`,
    f1 !== undefined ? `macro F1 ${f1.toFixed(3)}` : null,
    gate && !gate.passed ? `Blocked: ${gate.reasons.join('; ')}` : null,
    !gate ? 'Dev model trained at start-up; CI gates release models.' : null,
  ].filter(Boolean).join(' · ');
  return (
    <span data-testid="model-version-chip" title={tip} className={`inline-flex max-w-full items-center gap-1 truncate rounded-full px-2.5 py-0.5 text-[11px] font-semibold ${tone}`}>
      <span className="truncate">model {info.version}</span>
      <span aria-hidden>·</span>
      <span>{gateText}</span>
    </span>
  );
};
