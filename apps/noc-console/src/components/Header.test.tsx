import { describe, expect, it, vi } from 'vitest';
import { fireEvent, render, screen } from '@testing-library/react';
import { Header } from './Header';

describe('Header (W11)', () => {
  it('shows the signed-in user, role and a sign-out button', () => {
    const onLogout = vi.fn();
    render(
      <Header wsStatus="open" user={{ username: 'viewer', role: 'viewer' }} onLogout={onLogout} />,
    );
    const badge = screen.getByTestId('user-badge');
    expect(badge).toHaveTextContent('viewer');
    fireEvent.click(screen.getByRole('button', { name: /sign out/i }));
    expect(onLogout).toHaveBeenCalledOnce();
  });

  it('has no user badge without a session', () => {
    render(<Header wsStatus="open" />);
    expect(screen.queryByTestId('user-badge')).toBeNull();
  });
});
