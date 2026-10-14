import React, { useState } from 'react';
import { AnomaliesPanel } from './AnomaliesPanel';
import { useAnomalyList } from '../hooks/useAnomalies';

export const AnomaliesContainer: React.FC = () => {
  const [kpi, setKpi] = useState<string>('dlThroughputMbps');
  const hours = 24;

  const { data, isLoading, isError } = useAnomalyList(kpi, hours);

  return (
    <AnomaliesPanel
      data={data}
      isLoading={isLoading}
      isError={isError}
      kpi={kpi}
      onKpiChange={setKpi}
    />
  );
};
