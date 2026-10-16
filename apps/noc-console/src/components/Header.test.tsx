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
    // Step 13b: sign out lives in the profile menu
    fireEvent.click(screen.getByRole('button', { name: /viewer/i }));
    fireEvent.click(screen.getByRole('menuitem', { name: /sign out/i }));
    expect(onLogout).toHaveBeenCalledOnce();
  });

  it('has no user badge without a session', () => {
    render(<Header wsStatus="open" />);
    expect(screen.queryByTestId('user-badge')).toBeNull();
  });

  it('profile menu offers Change password and shows a role badge (13b)', () => {
    const onChangePassword = vi.fn();
    render(
      <Header
        wsStatus="open"
        user={{ username: 'ops1', role: 'operator' }}
        onChangePassword={onChangePassword}
        onLogout={vi.fn()}
      />,
    );
    expect(screen.getByTestId('role-badge')).toHaveTextContent('operator');
    expect(screen.queryByRole('menu')).toBeNull();
    fireEvent.click(screen.getByRole('button', { name: /ops1/ }));
    expect(screen.getByRole('menu')).toHaveTextContent(/acknowledge/);
    fireEvent.click(screen.getByRole('menuitem', { name: 'Change password' }));
    expect(onChangePassword).toHaveBeenCalledOnce();
    expect(screen.queryByRole('menu')).toBeNull();
  });

  it('shows dashboard tabs only when more than one view is offered', () => {
    const onSelectView = vi.fn();
    const { rerender } = render(
      <Header wsStatus="open" views={[{ id: 'ops', label: 'Operations' }]} />,
    );
    expect(screen.queryByRole('navigation', { name: 'Dashboards' })).toBeNull();
    rerender(
      <Header
        wsStatus="open"
        views={[
          { id: 'ops', label: 'Operations' },
          { id: 'admin', label: 'Admin' },
        ]}
        activeView="ops"
        onSelectView={onSelectView}
      />,
    );
    expect(screen.getByRole('button', { name: 'Operations' })).toHaveAttribute(
      'aria-current',
      'page',
    );
    fireEvent.click(screen.getByRole('button', { name: 'Admin' }));
    expect(onSelectView).toHaveBeenCalledWith('admin');
  });
});
