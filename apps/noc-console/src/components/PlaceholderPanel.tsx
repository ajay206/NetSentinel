import React from 'react';

interface PlaceholderPanelProps {
  title: string;
  week: number;
}

export const PlaceholderPanel: React.FC<PlaceholderPanelProps> = ({ title, week }) => {
  return (
    <div className="bg-white border border-bento-border border-dashed rounded-lg p-4 h-full flex items-center justify-center">
      <div className="text-center">
        <h3 className="text-slate-600 font-semibold">{title}</h3>
        <p className="text-slate-600 text-sm mt-1">Arrives in Week {week}</p>
      </div>
    </div>
  );
};
