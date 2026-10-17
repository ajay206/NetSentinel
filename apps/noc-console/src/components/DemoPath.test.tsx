import React from 'react';
import { fireEvent, render, screen, within } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';
import { DemoPath, type ConsolePage } from './DemoPath';

describe('Console page navigation', () => {
  it('shows five focused pages and marks the active page', () => {
    const onNavigate = vi.fn();
    render(<DemoPath activePage="overview" onNavigate={onNavigate} />);

    expect(screen.getByRole('navigation', { name: 'Console pages' })).toBeInTheDocument();
    expect(within(screen.getByRole('navigation', { name: 'Console pages' })).getAllByRole('button', { name: /^(Overview|Alarms|Network|Performance|Investigation):/ })).toHaveLength(5);
    expect(screen.getByRole('button', { name: /Overview:/ })).toHaveAttribute('aria-current', 'page');
    expect(screen.getByRole('button', { name: /Performance:/ })).toBeInTheDocument();

    fireEvent.click(screen.getByRole('button', { name: /Investigation:/ }));
    expect(onNavigate).toHaveBeenCalledWith('investigation' satisfies ConsolePage);
  });
});
