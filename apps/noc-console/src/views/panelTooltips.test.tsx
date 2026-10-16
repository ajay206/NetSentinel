import { fireEvent, render, screen } from '@testing-library/react';
import { describe, expect, it } from 'vitest';
import { Header } from '../components/Header';
import { TIPS } from '../lib/tooltips';
import { TraceView } from './TraceView';

const tipFor = (el: HTMLElement) => {
  const id = el.getAttribute('aria-describedby');
  expect(id).toBeTruthy();
  return document.getElementById(id!.split(' ').pop()!)!;
};

describe('panel tooltips', () => {
  it('Agent trace has an (i) icon that explains the panel', () => {
    render(<TraceView run={null} />);
    const icon = screen.getByRole('button', { name: 'About Agent trace' });
    fireEvent.focus(icon);
    expect(screen.getByRole('tooltip')).toHaveTextContent(String(TIPS.panelTrace));
  });

  it('header chips explain live status, synthetic data, clock and role', () => {
    render(<Header wsStatus="open" user={{ username: 'ops1', role: 'operator' }} />);
    expect(tipFor(screen.getByTestId('live-status'))).toHaveTextContent(TIPS.chipLive);
    expect(tipFor(screen.getByText('Synthetic data'))).toHaveTextContent(TIPS.chipSynthetic);
    expect(tipFor(screen.getByText(/IST$/))).toHaveTextContent(TIPS.chipClock);
    expect(tipFor(screen.getByRole('button', { name: /ops1/ }))).toHaveTextContent(
      TIPS.chipRole,
    );
  });

  it('every tooltip string is short plain English', () => {
    for (const [key, text] of Object.entries(TIPS)) {
      expect(text.length, key).toBeGreaterThan(10);
      expect(text.length, key).toBeLessThanOrEqual(220);
    }
  });
});
