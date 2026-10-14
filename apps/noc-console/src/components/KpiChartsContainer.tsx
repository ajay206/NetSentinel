import React, { useState, useEffect } from 'react';
import { KpiCharts } from './KpiCharts';
import { useKpiCells, useKpiSeries } from '../hooks/useKpiSeries';
import { useCellAnomalies } from '../hooks/useAnomalies';
import type { KpiName } from '../types.kpi';

export const KpiChartsContainer: React.FC = () => {
  const { data: cells, isLoading: cellsLoading, isError: cellsError } = useKpiCells();

  const [cellId, setCellId] = useState<string | null>(null);
  const [kpi, setKpi] = useState<KpiName>('dlThroughputMbps');
  const [agg, setAgg] = useState<'15m' | '1h' | '1d'>('1h');
  const [hours, setHours] = useState<number>(24);

  // set default cell when cells load
  useEffect(() => {
    if (Array.isArray(cells) && cells.length && !cells.some((c) => c.cellId === cellId)) {
      setCellId(cells[0].cellId);
    }
  }, [cells, cellId]);

  const {
    data: series,
    isLoading: seriesLoading,
    isError: seriesError,
  } = useKpiSeries(cellId, agg, hours);

  const { data: cellAnomalies } = useCellAnomalies(cellId, kpi, hours);

  const isLoading = cellsLoading || seriesLoading;
  const isError = cellsError || seriesError;

  return (
    <KpiCharts
      cells={Array.isArray(cells) ? cells : []}
      series={series}
      isLoading={isLoading}
      isError={isError}
      cellId={cellId}
      onCellChange={setCellId}
      kpi={kpi}
      onKpiChange={setKpi}
      agg={agg}
      onAggChange={setAgg}
      hours={hours}
      onHoursChange={setHours}
      anomalyTs={Array.isArray(cellAnomalies?.anomalies) ? cellAnomalies.anomalies.map((a) => a.ts) : []}
    />
  );
};
