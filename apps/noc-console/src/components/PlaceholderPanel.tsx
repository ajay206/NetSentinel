import React from 'react';

interface PlaceholderPanelProps {
  title: string;
  week: number;
}

export const PlaceholderPanel: React.FC<PlaceholderPanelProps> = ({ title, week }) => {
  return (
    <div className="bg-slate-900 border border-slate-700 border-dashed rounded-lg p-4 h-full flex items-center justify-center">
      <div className="text-center">
        <h3 className="text-slate-300 font-semibold">{title}</h3>
        <p className="text-slate-500 text-sm mt-1">Arrives in Week {week}</p>
      </div>
    </div>
  );
};
