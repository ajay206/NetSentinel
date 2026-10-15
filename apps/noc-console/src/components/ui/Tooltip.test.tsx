import { act, fireEvent, render, screen } from '@testing-library/react';
import { afterEach, describe, expect, it, vi } from 'vitest';
import { InfoIcon, Tip, Tooltip } from './Tooltip';

afterEach(() => vi.useRealTimers());

describe('Tooltip', () => {
  it('links the trigger to the tip with aria-describedby and starts hidden', () => {
    render(
      <Tooltip content="Explains the thing">
        <button type="button">Do it</button>
      </Tooltip>,
    );
    const btn = screen.getByRole('button', { name: 'Do it' });
    const id = btn.getAttribute('aria-describedby');
    expect(id).toBeTruthy();
    const tip = document.getElementById(id!)!;
    expect(tip).toHaveAttribute('role', 'tooltip');
    expect(tip).toHaveTextContent('Explains the thing');
    expect(tip).not.toBeVisible();
    // buttons are already focusable: no extra tabIndex
    expect(btn).not.toHaveAttribute('tabindex');
  });

  it('shows on hover after the delay and hides on mouse leave', () => {
    vi.useFakeTimers();
    render(
      <Tooltip content="Hover help" delay={100}>
        <span>label</span>
      </Tooltip>,
    );
    const el = screen.getByText('label');
    fireEvent.mouseEnter(el);
    expect(screen.getByRole('tooltip', { hidden: true })).not.toBeVisible();
    act(() => vi.advanceTimersByTime(120));
    expect(screen.getByRole('tooltip')).toHaveTextContent('Hover help');
    fireEvent.mouseLeave(el);
    expect(screen.queryByRole('tooltip')).toBeNull();
  });

  it('makes plain elements keyboard-focusable, shows on focus and hides on Escape', () => {
    render(
      <Tooltip content="Focus help">
        <span>chip</span>
      </Tooltip>,
    );
    const el = screen.getByText('chip');
    expect(el).toHaveAttribute('tabindex', '0');
    fireEvent.focus(el);
    expect(screen.getByRole('tooltip')).toHaveTextContent('Focus help');
    fireEvent.keyDown(document, { key: 'Escape' });
    expect(screen.queryByRole('tooltip')).toBeNull();
  });

  it('keeps the child handlers working', () => {
    const onFocus = vi.fn();
    render(
      <Tooltip content="x">
        <button type="button" onFocus={onFocus}>
          b
        </button>
      </Tooltip>,
    );
    fireEvent.focus(screen.getByRole('button'));
    expect(onFocus).toHaveBeenCalled();
  });

  it('Tip and InfoIcon expose accessible help text', () => {
    render(
      <>
        <Tip tip="Column help">Severity</Tip>
        <InfoIcon text="Panel help" label="Audit log" />
      </>,
    );
    const icon = screen.getByRole('button', { name: 'About Audit log' });
    fireEvent.focus(icon);
    expect(screen.getByRole('tooltip')).toHaveTextContent('Panel help');
    const tipId = screen.getByText('Severity').getAttribute('aria-describedby');
    expect(document.getElementById(tipId!)).toHaveTextContent('Column help');
  });
});
