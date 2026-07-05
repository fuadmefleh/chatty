import React, { useId, useState } from 'react';
import type { ReactNode } from 'react';
import { getStoredApiKey, setStoredApiKey, CHATTY_API_BASE } from '../chattyApi';
import Card from './ui/Card';
import Input from './ui/form/Input';

interface AuthGateProps {
  children: ReactNode;
}

const AuthGate: React.FC<AuthGateProps> = ({ children }) => {
  const [apiKey, setApiKey] = useState(getStoredApiKey);
  const [inputKey, setInputKey] = useState('');
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);
  const inputId = useId();

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setLoading(true);
    setError('');
    try {
      const res = await fetch(`${CHATTY_API_BASE}/api/chatty/notes`, {
        headers: { 'X-API-Key': inputKey },
      });
      if (res.status === 401) {
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
    <div className="flex min-h-dvh items-center justify-center bg-bg px-4">
      <Card padding="44px 40px" className="w-full max-w-[380px] text-center">
        <div className="mx-auto mb-5 flex h-11 w-11 flex-col justify-center gap-1.5 rounded-lg border-2 border-alert-amber px-2">
          <span className="h-0.5 bg-alert-amber" />
          <span className="h-0.5 bg-signal" />
          <span className="h-0.5 w-3/5 bg-alert-red" />
        </div>
        <h1 className="mb-1.5 font-display text-[22px] font-bold tracking-wide text-ink">Chatty</h1>
        <p className="mb-7 font-mono text-xs uppercase tracking-wider text-muted">Enter access key</p>
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
          />
          {error && (
            <p className="text-sm text-alert-red" role="alert">
              {error}
            </p>
          )}
          <button
            type="submit"
            disabled={loading || !inputKey}
            className="w-full rounded-lg bg-alert-amber p-3 text-sm font-bold text-white disabled:bg-surface-dim disabled:text-muted"
          >
            {loading ? 'Checking…' : 'Unlock'}
          </button>
        </form>
      </Card>
    </div>
  );
};

export default AuthGate;
