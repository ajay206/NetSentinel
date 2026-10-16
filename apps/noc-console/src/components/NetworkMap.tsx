import React, { useMemo } from 'react';
import { TIPS } from '../lib/tooltips';
import { CardHeader } from './ui/Card';
import type { Topology, PerceivedSeverity } from '../types';

type Props = {
  topology?: Topology;
  isLoading: boolean;
  isError: boolean;
  severityBySite: Record<string, PerceivedSeverity>;
  /** Step 14: impact radius from the RCA graph panel (sites that lose service). */
  impactedSiteIds?: ReadonlySet<string>;
  /** Step 14: the simulated failure (drawn red). */
  failedLinkId?: string | null;
  failedSiteId?: string | null;
};

const IMPACT = '#f97316';
const FAILED = '#ef4444';

const severityColor: Record<PerceivedSeverity, string> = {
  critical: '#ef4444',
  major: '#f97316',
  minor: '#f59e0b',
  warning: '#6DCFF6',
  cleared: '#10b981',
};

export const NetworkMap: React.FC<Props> = ({
  topology,
  isLoading,
  isError,
  severityBySite,
  impactedSiteIds,
  failedLinkId = null,
  failedSiteId = null,
}) => {
  const viewBox = '0 0 600 380';
  const padding = 20; // px padding inside viewBox

  const { sites, links, counts } = topology ?? {};

  // compute projection
  const projection = useMemo(() => {
    if (!sites?.length) return null;
    const lats = sites.map((s) => s.lat);
    const lons = sites.map((s) => s.lon);
    const minLat = Math.min(...lats);
    const maxLat = Math.max(...lats);
    const minLon = Math.min(...lons);
    const maxLon = Math.max(...lons);
    const latRange = maxLat - minLat || 1;
    const lonRange = maxLon - minLon || 1;

    return (lat: number, lon: number) => {
      const x = padding + ((lon - minLon) / lonRange) * (600 - 2 * padding);
      // higher lat = up (smaller y)
      const y = padding + ((maxLat - lat) / latRange) * (380 - 2 * padding);
      return { x, y };
    };
  }, [sites]);

  if (isLoading) {
    return (
      <div className="flex items-center justify-center py-8">
        <span className="text-slate-400">Loading network map…</span>
      </div>
    );
  }

  if (isError) {
    return (
      <div className="flex items-center justify-center py-8 text-red-500">
        Failed to load network map.
      </div>
    );
  }

  if (!topology) {
    return null;
  }

  // helper to get worst severity for a site
  const siteSeverity = (siteId: string): PerceivedSeverity => {
    const sev = severityBySite[siteId];
    return sev ?? 'cleared';
  };

  // render links
  const renderLinks = () => {
    if (!links) return null;
    return links.map((link) => {
      if (!projection) return null;
      const a = sites?.find((s) => s.siteId === link.a);
      const b = sites?.find((s) => s.siteId === link.b);
      if (!a || !b) return null;
      const pA = projection(a.lat, a.lon);
      const pB = projection(b.lat, b.lon);
      const isMicrowave = link.kind === 'microwave';
      const role = link.role;
      const strokeWidth = role === 'core' ? 2.5 : role === 'ring' ? 1.5 : 1;
      const strokeColor =
        role === 'core'
          ? '#2A4A73' // navy mid
          : role === 'ring'
            ? '#1677A0' // deck cyan dark
            : '#5A5566'; // muted mauve
      const failed = link.linkId === failedLinkId;
      const dashArray = failed ? '5 3' : isMicrowave ? '4 2' : undefined;

      return (
        <line
          key={link.linkId}
          data-link-id={link.linkId}
          x1={pA.x}
          y1={pA.y}
          x2={pB.x}
          y2={pB.y}
          stroke={failed ? FAILED : strokeColor}
          strokeWidth={failed ? 3.5 : strokeWidth}
          strokeDasharray={dashArray}
          data-failed={failed || undefined}
        />
      );
    });
  };

  // render sites
  const renderSites = () => {
    if (!sites) return null;
    return sites.map((site) => {
      if (!projection) return null;
      const { x, y } = projection(site.lat, site.lon);
      const sev = siteSeverity(site.siteId);
      const fill = severityColor[sev];
      const commonProps = {
        key: site.siteId,
        'data-site-id': site.siteId,
        fill,
        stroke: '#111',
        strokeWidth: 0.5,
      };
      const title = `${site.siteId} · ${site.region} · ${site.kind} · ${site.nodes.length} nodes / ${site.nodes.reduce(
        (c, n) => c + n.cells.length,
        0,
      )} cells · ${sev}`;

      const shape =
        site.kind === 'core' ? (
          <rect {...commonProps} x={x - 5} y={y - 5} width={10} height={10} />
        ) : site.kind === 'hub' ? (
          <polygon
            {...commonProps}
            points={`${x},${y - 6} ${x + 6},${y} ${x},${y + 6} ${x - 6},${y}`}
          />
        ) : (
          <circle {...commonProps} cx={x} cy={y} r={5} />
        );

      return (
        <g key={site.siteId}>
          {(impactedSiteIds?.has(site.siteId) || site.siteId === failedSiteId) && (
            <circle
              data-impacted={site.siteId}
              cx={x}
              cy={y}
              r={10}
              fill="none"
              stroke={site.siteId === failedSiteId ? FAILED : IMPACT}
              strokeWidth={2}
              strokeDasharray="3 2"
            />
          )}
          {shape}
          <title>{title}</title>
          {sev === 'critical' && (
            <circle cx={x} cy={y} r={8} fill="none" stroke={fill} strokeWidth={2}>
              <animate attributeName="r" from="8" to="12" dur="1s" repeatCount="indefinite" />
              <animate
                attributeName="opacity"
                from="0.7"
                to="0"
                dur="1s"
                repeatCount="indefinite"
              />
            </circle>
          )}
        </g>
      );
    });
  };

  // region labels
  const renderRegions = () => {
    if (!topology?.regions?.length) return null;
    return topology.regions.map((region) => {
      const regionSites = sites?.filter((s) => s.region === region && s.kind !== 'core');
      if (!regionSites?.length) return null;
      const avgLat = regionSites.reduce((acc, s) => acc + s.lat, 0) / regionSites.length;
      const p = projection?.(avgLat, 0);
      if (!p) return null;
      return (
        <text
          key={region}
          x={padding + 4}
          y={p.y}
          textAnchor="start"
          className="text-[11px] uppercase tracking-widest fill-deck-navy"
        >
          {region}
        </text>
      );
    });
  };

  return (
    <section className="ns-card">
      <CardHeader
        title="Network map"
        subtitle="Sites coloured by their worst active alarm."
        info={TIPS.panelMap}
        actions={
          <div className="flex items-center gap-3 text-xs text-slate-400">
            <span>{counts?.sites ?? 0} sites</span>
            <span>{counts?.nodes ?? 0} nodes</span>
            <span>{counts?.cells ?? 0} cells</span>
            <span>{counts?.links ?? 0} links</span>
          </div>
        }
      />

      {/* Legend */}
      <div className="flex flex-wrap gap-x-3 gap-y-1 mb-2 text-xs text-slate-400">
        <span className="flex items-center gap-1">
          <svg className="w-4 h-4">
            <rect width="10" height="10" fill="#2A4A73" />
          </svg>
          Core link
        </span>
        <span className="flex items-center gap-1">
          <svg className="w-4 h-4">
            <line x1="0" y1="5" x2="10" y2="5" stroke="#1677A0" strokeWidth="1.5" />
          </svg>
          Ring link
        </span>
        <span className="flex items-center gap-1">
          <svg className="w-4 h-4">
            <line x1="0" y1="5" x2="10" y2="5" stroke="#5A5566" strokeWidth="1" />
          </svg>
          Access link
        </span>
        <span className="flex items-center gap-1">
          <svg className="w-4 h-4">
            <line
              x1="0"
              y1="5"
              x2="10"
              y2="5"
              stroke="#5A5566"
              strokeWidth="1"
              strokeDasharray="4 2"
            />
          </svg>
          Microwave
        </span>
        {(['critical', 'major', 'minor', 'warning', 'cleared'] as const).map((sev) => (
          <span key={sev} className="flex items-center gap-1">
            <svg className="w-4 h-4">
              <circle cx="5" cy="5" r="4" fill={severityColor[sev]} />
            </svg>
            {sev === 'cleared' ? 'no active alarm' : sev}
          </span>
        ))}
      </div>

      <svg
        viewBox={viewBox}
        className="w-full h-auto max-h-[min(380px,50vh)] bg-slate-950 border border-slate-700 rounded"
      >
        {renderRegions()}
        {renderLinks()}
        {renderSites()}
      </svg>
    </section>
  );
};

export default NetworkMap;
