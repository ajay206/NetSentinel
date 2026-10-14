import React from 'react';
import { render } from '@testing-library/react';
import { NetworkMap } from './NetworkMap';
import type { Topology, PerceivedSeverity } from '../types';

const fixtureTopology: Topology = {
  seed: 1,
  small: true,
  regions: ['North'],
  counts: {
    regions: 1,
    sites: 2,
    nodes: 2,
    cells: 2,
    links: 1,
  },
  sites: [
    {
      siteId: 'SITE-001',
      name: 'Alpha',
      region: 'North',
      kind: 'core',
      lat: 10,
      lon: 10,
      nodes: [
        { nodeId: 'N1', kind: 'router', cells: ['C1'] },
        { nodeId: 'N2', kind: 'router', cells: ['C2'] },
      ],
    },
    {
      siteId: 'SITE-002',
      name: 'Beta',
      region: 'North',
      kind: 'access',
      lat: 20,
      lon: 20,
      nodes: [{ nodeId: 'N3', kind: 'router', cells: [] }],
    },
  ],
  links: [
    {
      linkId: 'L1',
      a: 'SITE-001',
      b: 'SITE-002',
      kind: 'fibre',
      role: 'core',
    },
  ],
};

const severityBySite: Record<string, PerceivedSeverity> = {
  'SITE-001': 'critical',
  'SITE-002': 'cleared',
};

test('renders network map with correct severity colors and link count', () => {
  render(
    <NetworkMap
      topology={fixtureTopology}
      isLoading={false}
      isError={false}
      severityBySite={severityBySite}
    />,
  );

  // critical site should have fill #ef4444
  const siteSvg = document.querySelector('[data-site-id="SITE-001"]');
  expect(siteSvg).toBeInTheDocument();
  expect(siteSvg).toHaveAttribute('fill', '#ef4444');

  // link count
  const links = document.querySelectorAll('[data-link-id]');
  expect(links).toHaveLength(fixtureTopology.links.length);
});
