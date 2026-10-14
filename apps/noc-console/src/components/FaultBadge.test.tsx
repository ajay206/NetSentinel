import { describe, it, expect } from 'vitest';
import { render, screen } from '@testing-library/react';
import { FaultBadge } from './FaultBadge';

describe('FaultBadge', () => {
  it('renders loading state', () => {
    render(<FaultBadge isLoading />);
    expect(screen.getByTestId('fault-badge')).toHaveTextContent('classifying…');
  });

  it('renders error state', () => {
    render(<FaultBadge isError />);
    expect(screen.getByTestId('fault-badge')).toHaveTextContent('model unavailable');
  });

  it('renders prediction with correct label and percent', () => {
    const pred = { faultType: 'power_failure', confidence: 0.85 };
    render(<FaultBadge prediction={pred} />);
    const badge = screen.getByTestId('fault-badge');
    expect(badge).toHaveTextContent('Power failure 85%');
    expect(badge).toHaveClass('bg-emerald-200');
  });

  it('uses fallback label when unknown fault type', () => {
    const pred = { faultType: 'unknown_fault', confidence: 0.5 };
    render(<FaultBadge prediction={pred} />);
    expect(screen.getByTestId('fault-badge')).toHaveTextContent('unknown_fault 50%');
  });

  it('applies amber colour for medium confidence', () => {
    const pred = { faultType: 'congestion', confidence: 0.55 };
    render(<FaultBadge prediction={pred} />);
    expect(screen.getByTestId('fault-badge')).toHaveClass('bg-amber-200');
  });
});
