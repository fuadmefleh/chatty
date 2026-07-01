import React, { useState } from 'react';
import type { ReactNode } from 'react';
import { getStoredApiKey, setStoredApiKey, API_KEY_STORAGE, CHATTY_API_BASE } from '../chattyApi';

interface AuthGateProps {
  children: ReactNode;
}

const AuthGate: React.FC<AuthGateProps> = ({ children }) => {
  const [apiKey, setApiKey] = useState(getStoredApiKey);
  const [inputKey, setInputKey] = useState('');
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);

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

  const handleLogout = () => {
    localStorage.removeItem(API_KEY_STORAGE);
    setApiKey('');
    setInputKey('');
  };

  if (apiKey) {
    return (
      <>
        <div style={{ position: 'fixed', top: 10, right: 16, zIndex: 9999 }}>
          <button
            onClick={handleLogout}
            style={{
              background: 'var(--ink-800)',
              color: 'var(--muted)',
              border: '1px solid var(--ink-600)',
              borderRadius: 6,
              padding: '4px 12px',
              cursor: 'pointer',
              fontSize: 12,
              fontFamily: 'var(--font-mono)',
            }}
          >
            lock
          </button>
        </div>
        {children}
      </>
    );
  }

  return (
    <div
      style={{
        minHeight: '100vh',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        background: 'var(--ink-900)',
      }}
    >
      <div
        style={{
          background: 'var(--ink-800)',
          border: '1px solid var(--ink-700)',
          borderRadius: 12,
          padding: '44px 40px',
          width: 360,
          textAlign: 'center',
        }}
      >
        <div
          style={{
            width: 44,
            height: 44,
            margin: '0 auto 20px',
            border: '2px solid var(--stamp-gold)',
            borderRadius: 8,
            display: 'flex',
            flexDirection: 'column',
            justifyContent: 'center',
            gap: 5,
            padding: '0 8px',
          }}
        >
          <span style={{ height: 2, background: 'var(--stamp-gold)' }} />
          <span style={{ height: 2, background: 'var(--stamp-teal)' }} />
          <span style={{ height: 2, background: 'var(--stamp-ember)', width: '60%' }} />
        </div>
        <h1
          style={{
            fontFamily: 'var(--font-display)',
            margin: '0 0 6px',
            fontSize: 22,
            fontWeight: 700,
            color: 'var(--paper)',
            letterSpacing: '0.01em',
          }}
        >
          Chatty
        </h1>
        <p
          style={{
            fontFamily: 'var(--font-mono)',
            color: 'var(--muted)',
            marginBottom: 28,
            fontSize: 12,
            letterSpacing: '0.06em',
            textTransform: 'uppercase',
          }}
        >
          Enter access key
        </p>
        <form onSubmit={handleSubmit}>
          <input
            type="password"
            placeholder="API key"
            value={inputKey}
            onChange={(e) => setInputKey(e.target.value)}
            style={{
              width: '100%',
              padding: '12px 14px',
              borderRadius: 8,
              border: '1px solid var(--ink-600)',
              background: 'var(--ink-900)',
              color: 'var(--paper)',
              fontSize: 14,
              fontFamily: 'var(--font-mono)',
              outline: 'none',
              boxSizing: 'border-box',
              marginBottom: 14,
            }}
            autoFocus
          />
          {error && (
            <p style={{ color: 'var(--danger)', fontSize: 13, marginBottom: 14 }}>{error}</p>
          )}
          <button
            type="submit"
            disabled={loading || !inputKey}
            style={{
              width: '100%',
              padding: '12px',
              background: loading || !inputKey ? 'var(--ink-700)' : 'var(--stamp-gold)',
              color: loading || !inputKey ? 'var(--muted)' : 'var(--ink-900)',
              border: 'none',
              borderRadius: 8,
              fontSize: 14,
              fontWeight: 700,
              cursor: loading ? 'not-allowed' : 'pointer',
            }}
          >
            {loading ? 'Checking…' : 'Unlock'}
          </button>
        </form>
      </div>
    </div>
  );
};

export default AuthGate;
