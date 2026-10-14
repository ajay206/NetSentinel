import React from 'react';
import { FAULT_LABELS } from '../types.fault';

interface FaultBadgeProps {
  prediction?: {
    faultType: string;
    confidence: number;
  };
  isLoading?: boolean;
  isError?: boolean;
}

export const FaultBadge: React.FC<FaultBadgeProps> = ({
  prediction,
  isLoading,
  isError,
}) => {
  if (isLoading) {
    return (
      <span
        className="inline-flex items-center rounded-full px-2.5 py-0.5 text-xs font-medium bg-slate-200 text-slate-800"
        data-testid="fault-badge"
      >
        classifying…
      </span>
    );
  }

  if (isError) {
    return (
      <span
        className="inline-flex items-center rounded-full px-2.5 py-0.5 text-xs font-medium bg-red-200 text-red-800"
        data-testid="fault-badge"
      >
        model unavailable
      </span>
    );
  }

  if (!prediction) {
    return null;
  }

  const { faultType, confidence } = prediction;
  const label = FAULT_LABELS[faultType] ?? faultType;
  const percent = Math.round(confidence * 100);
  let bg = 'bg-slate-200 text-slate-800';
  if (confidence >= 0.7) {
    bg = 'bg-emerald-200 text-emerald-800';
  } else if (confidence >= 0.4) {
    bg = 'bg-amber-200 text-amber-800';
  }

  return (
    <span
      className={`inline-flex items-center rounded-full px-2.5 py-0.5 text-xs font-medium ${bg}`}
      data-testid="fault-badge"
    >
      {label} {percent}%
    </span>
  );
};
