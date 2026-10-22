import React from 'react';

interface SparklineProps {
  values: number[];
  label: string;
  stroke?: string;
  width?: number;
  height?: number;
}

/** W22: tiny inline SVG trend line (no chart library). */
export const Sparkline: React.FC<SparklineProps> = ({ values, label, stroke = '#0E7C86', width = 72, height = 18 }) => {
  if (values.length < 2) return null;
  const max = Math.max(...values, 1e-9);
  const step = width / (values.length - 1);
  const pts = values.map((v, i) => `${(i * step).toFixed(1)},${(height - 1 - (v / max) * (height - 2)).toFixed(1)}`).join(' ');
  return (
    <svg role="img" aria-label={label} width={width} height={height} viewBox={`0 0 ${width} ${height}`} className="shrink-0">
      <title>{label}</title>
      <polyline points={pts} fill="none" stroke={stroke} strokeWidth="1.5" strokeLinejoin="round" />
    </svg>
  );
};
