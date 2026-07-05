import React, { useEffect, useId, useState } from 'react';
import type { ReactNode } from 'react';
import { getStoredApiKey, setStoredApiKey, CHATTY_API_BASE } from '../chattyApi';
import Card from './ui/Card';
import Input from './ui/form/Input';
import { NAV_GROUPS, navColorTextClass } from './layout/nav-config';

interface AuthGateProps {
  children: ReactNode;
}

const GROUP_BLURB: Record<string, string> = {
  ledger: 'Household spending, orders, budgets and recurring charges, tracked automatically.',
  training: 'Workouts, exercises and progress, logged and charted over time.',
  assistant: "Chat, notes, transcriptions, memory and reminders — Chatty's own brain.",
};

type HealthState = 'checking' | 'online' | 'offline';

const AuthGate: React.FC<AuthGateProps> = ({ children }) => {
  const [apiKey, setApiKey] = useState(getStoredApiKey);
  const [inputKey, setInputKey] = useState('');
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);
  const [retryAfter, setRetryAfter] = useState(0);
  const [health, setHealth] = useState<HealthState>('checking');
  const inputId = useId();

  useEffect(() => {
    if (apiKey) return;
    let cancelled = false;
    fetch(`${CHATTY_API_BASE}/api/chatty/health`)
      .then((res) => {
        if (!cancelled) setHealth(res.ok ? 'online' : 'offline');
      })
      .catch(() => {
        if (!cancelled) setHealth('offline');
      });
    return () => {
      cancelled = true;
    };
  }, [apiKey]);

  // Server locks the key out after too many bad guesses (429 + Retry-After).
  // Count the local cooldown down so the button re-enables on its own.
  useEffect(() => {
    if (retryAfter <= 0) return;
    const id = setInterval(() => setRetryAfter((s) => Math.max(0, s - 1)), 1000);
    return () => clearInterval(id);
  }, [retryAfter]);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (retryAfter > 0) return;
    setLoading(true);
    setError('');
    try {
      const res = await fetch(`${CHATTY_API_BASE}/api/chatty/notes`, {
        headers: { 'X-API-Key': inputKey },
      });
      if (res.status === 429) {
        const seconds = Number(res.headers.get('Retry-After')) || 60;
        setRetryAfter(seconds);
        setError(`Too many attempts — locked for ${seconds}s.`);
      } else if (res.status === 401) {
        setError('Invalid key — try again.');
      } else {
        setStoredApiKey(inputKey);
        setApiKey(inputKey);
      }
    } catch {
      setError('Cannot reach the Chatty API server. Make sure it is running on port 8016.');
    } finally {
      setLoading(false);
    }
  };

  if (apiKey) {
    return <>{children}</>;
  }

  return (
    <div className="flex min-h-dvh flex-col items-center justify-center gap-10 bg-bg px-4 py-12">
      <div className="flex flex-col items-center text-center">
        <div className="mx-auto mb-5 flex h-11 w-11 flex-col justify-center gap-1.5 rounded-lg border-2 border-alert-amber px-2">
          <span className="h-0.5 bg-alert-amber" />
          <span className="h-0.5 bg-signal" />
          <span className="h-0.5 w-3/5 bg-alert-red" />
        </div>
        <h1 className="mb-1.5 font-display text-[26px] font-bold tracking-wide text-ink">Chatty</h1>
        <p className="max-w-md font-mono text-xs uppercase tracking-wider text-muted">
          Personal assistant &amp; household dashboard
        </p>
        <div className="mt-3 flex items-center gap-1.5 font-mono text-[11px] uppercase tracking-wider text-muted">
          <span
            className={`h-1.5 w-1.5 rounded-full ${
              health === 'online' ? 'bg-alert-green' : health === 'offline' ? 'bg-alert-red' : 'bg-muted'
            }`}
          />
          {health === 'checking' ? 'Checking server…' : health === 'online' ? 'Server online' : 'Server unreachable'}
        </div>
      </div>

      <div className="grid w-full max-w-3xl grid-cols-1 gap-3 sm:grid-cols-3">
        {NAV_GROUPS.map((group) => {
          const Icon = group.icon;
          return (
            <Card key={group.id} padding="18px" className="text-left">
              <Icon className={`mb-2 h-5 w-5 ${navColorTextClass[group.color]}`} />
              <h2 className="font-display text-sm font-semibold text-ink">{group.caption}</h2>
              <p className="mt-1 text-xs text-muted">{GROUP_BLURB[group.id]}</p>
            </Card>
          );
        })}
      </div>

      <Card padding="44px 40px" className="w-full max-w-[380px] text-center">
        <p className="mb-5 font-mono text-xs uppercase tracking-wider text-muted">Enter access key</p>
        <form onSubmit={handleSubmit} className="flex flex-col gap-3.5 text-left">
          <label htmlFor={inputId} className="sr-only">
            API key
          </label>
          <Input
            id={inputId}
            type="password"
            placeholder="API key"
            value={inputKey}
            onChange={(e) => setInputKey(e.target.value)}
            className="text-center font-mono"
            autoFocus
            disabled={retryAfter > 0}
          />
          {error && (
            <p className="text-sm text-alert-red" role="alert">
              {error}
            </p>
          )}
          <button
            type="submit"
            disabled={loading || !inputKey || retryAfter > 0}
            className="w-full rounded-lg bg-alert-amber p-3 text-sm font-bold text-white disabled:bg-surface-dim disabled:text-muted"
          >
            {retryAfter > 0 ? `Locked (${retryAfter}s)` : loading ? 'Checking…' : 'Unlock'}
          </button>
        </form>
      </Card>
    </div>
  );
};

export default AuthGate;
