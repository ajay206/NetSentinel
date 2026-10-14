import React, { useEffect, useState } from 'react';
import type { ConnectionStatus } from '../hooks/useAlarmFeed';
import { formatIST } from '../lib/time';

interface HeaderProps {
  wsStatus: ConnectionStatus;
}

export const Header: React.FC<HeaderProps> = ({ wsStatus }) => {
  const [istTime, setIstTime] = useState(() => formatIST(new Date()));

  useEffect(() => {
    const timer = setInterval(() => {
      setIstTime(formatIST(new Date()));
    }, 1000);
    return () => clearInterval(timer);
  }, []);

  const statusColor = {
    connecting: 'bg-yellow-400',
    open: 'bg-emerald-400',
    closed: 'bg-red-400',
  }[wsStatus];

  return (
    <header className="bg-slate-900 border-b border-slate-700 px-4 py-2 flex items-center justify-between text-sm">
      <div className="flex items-center space-x-4">
        <span className="font-mono text-slate-300">NetSentinel</span>
        <span className="text-slate-400">NOC Console</span>
        <span className="px-2 py-0.5 text-xs font-mono bg-slate-800 text-sky-300 rounded">
          LOCAL · SYNTHETIC DATA
        </span>
      </div>
      <div className="flex items-center space-x-4">
        <div className="flex items-center space-x-1">
          <span className={`w-2 h-2 rounded-full ${statusColor} animate-pulse`}></span>
          <span className="text-slate-400 font-mono">WS: {wsStatus}</span>
        </div>
        <span className="text-slate-400 font-mono">IST: {istTime}</span>
      </div>
    </header>
  );
};
