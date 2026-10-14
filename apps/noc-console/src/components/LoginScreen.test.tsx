import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { LoginScreen } from './LoginScreen';

describe('components/LoginScreen', () => {
  beforeEach(() => {
    vi.stubGlobal('fetch', vi.fn());
  });

  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it('calls onLogin with session on successful login', async () => {
    const onLogin = vi.fn();

    vi.mocked(fetch).mockResolvedValueOnce(
      new Response(
        JSON.stringify({
          accessToken: 'abc123',
          expiresIn: 3600,
          username: 'operator',
          role: 'operator',
        }),
        { status: 200, headers: { 'Content-Type': 'application/json' } },
      ),
    );

    render(<LoginScreen onLogin={onLogin} />);

    fireEvent.change(screen.getByLabelText('Username'), {
      target: { value: 'operator' },
    });
    fireEvent.change(screen.getByLabelText('Password'), {
      target: { value: 'operator' },
    });
    fireEvent.click(screen.getByRole('button', { name: /sign in/i }));

    await waitFor(() =>
      expect(onLogin).toHaveBeenCalledWith(
        expect.objectContaining({ token: 'abc123', username: 'operator', role: 'operator' }),
      ),
    );
  });

  it('shows error alert on 401', async () => {
    const onLogin = vi.fn();

    vi.mocked(fetch).mockResolvedValueOnce(
      new Response(JSON.stringify({ message: 'Unauthorized' }), {
        status: 401,
      }),
    );

    render(<LoginScreen onLogin={onLogin} />);

    fireEvent.change(screen.getByLabelText('Username'), {
      target: { value: 'wrong' },
    });
    fireEvent.change(screen.getByLabelText('Password'), {
      target: { value: 'wrong' },
    });
    fireEvent.click(screen.getByRole('button', { name: /sign in/i }));

    await waitFor(() => {
      expect(screen.getByRole('alert')).toHaveTextContent('Invalid username or password');
    });
    expect(onLogin).not.toHaveBeenCalled();
  });

  it('shows error alert on 429', async () => {
    const onLogin = vi.fn();

    vi.mocked(fetch).mockResolvedValueOnce(
      new Response(JSON.stringify({ message: 'Too many requests' }), {
        status: 429,
      }),
    );

    render(<LoginScreen onLogin={onLogin} />);

    fireEvent.change(screen.getByLabelText('Username'), {
      target: { value: 'viewer' },
    });
    fireEvent.change(screen.getByLabelText('Password'), {
      target: { value: 'viewer' },
    });
    fireEvent.click(screen.getByRole('button', { name: /sign in/i }));

    await waitFor(() => {
      expect(screen.getByRole('alert')).toHaveTextContent('Too many attempts, wait a minute');
    });
  });

  it('disables button while pending', async () => {
    const onLogin = vi.fn();
    let resolveFetch: (value: Response) => void;
    const fetchPromise = new Promise<Response>((resolve) => {
      resolveFetch = resolve;
    });
    vi.mocked(fetch).mockReturnValueOnce(fetchPromise);

    render(<LoginScreen onLogin={onLogin} />);

    fireEvent.change(screen.getByLabelText('Username'), {
      target: { value: 'admin' },
    });
    fireEvent.change(screen.getByLabelText('Password'), {
      target: { value: 'admin' },
    });
    fireEvent.click(screen.getByRole('button', { name: /sign in/i }));
    const button = await screen.findByRole('button', { name: /signing in/i });
    expect(button).toBeDisabled();

    resolveFetch!(
      new Response(
        JSON.stringify({
          accessToken: 'token',
          expiresIn: 3600,
          username: 'admin',
          role: 'admin',
        }),
        { status: 200 },
      ),
    );

    await waitFor(() => expect(onLogin).toHaveBeenCalled());
  });
});
