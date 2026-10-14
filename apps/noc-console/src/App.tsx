import React from 'react';
import { Header } from './components/Header';
import { LiveAlarms } from './components/LiveAlarms';
import { ServiceHealth } from './components/ServiceHealth';
import { PlaceholderPanel } from './components/PlaceholderPanel';
import { useAlarmFeed } from './hooks/useAlarmFeed';
import { useHealth } from './hooks/useHealth';

export const App: React.FC = () => {
  const { alarms, status } = useAlarmFeed();
  const { data: health, isError } = useHealth();

  return (
    <div className="min-h-screen bg-slate-950 text-slate-200 flex flex-col">
      <Header wsStatus={status} />
      <main className="flex-1 p-4 grid grid-cols-1 lg:grid-cols-3 gap-4">
        <div className="lg:col-span-2">
          <LiveAlarms alarms={alarms} />
        </div>
        <div>
          <ServiceHealth health={health} isError={isError} />
        </div>
        <div className="lg:col-span-3 grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
          <PlaceholderPanel title="Network map" week={3} />
          <PlaceholderPanel title="KPI charts" week={5} />
          <PlaceholderPanel title="Anomalies" week={6} />
          <PlaceholderPanel title="Copilot" week={9} />
        </div>
      </main>
    </div>
  );
};

export default App;
