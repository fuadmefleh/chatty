import React, { useCallback, useEffect, useState } from 'react';
import { useSearchParams } from 'react-router-dom';
import { fetchGmailStatus, fetchGmailConnectUrl, disconnectGmail } from '../chattyApi';
import type { GmailStatus } from '../chattyApi';
import PageHeader from '../components/ui/PageHeader';
import Card from '../components/ui/Card';
import Badge from '../components/ui/Badge';
import Spinner from '../components/ui/Spinner';
import { useToast } from '../hooks/useToast';

const STATUS_LABEL: Record<GmailStatus['status'], string> = {
  connected: 'Connected',
  expired: 'Token expired',
  disconnected: 'Not connected',
  not_configured: 'Not connected',
};

const STATUS_TONE: Record<GmailStatus['status'], 'teal' | 'gold' | 'neutral'> = {
  connected: 'teal',
  expired: 'gold',
  disconnected: 'neutral',
  not_configured: 'neutral',
};

const GmailCard: React.FC = () => {
  const [status, setStatus] = useState<GmailStatus | null>(null);
  const [loading, setLoading] = useState(true);
  const [connecting, setConnecting] = useState(false);
  const [disconnecting, setDisconnecting] = useState(false);
  const [searchParams, setSearchParams] = useSearchParams();
  const { showToast } = useToast();

  const load = useCallback(async () => {
    setLoading(true);
    try {
      setStatus(await fetchGmailStatus());
    } catch {
      showToast('Failed to load Gmail status', 'red');
    } finally {
      setLoading(false);
    }
  }, [showToast]);

  useEffect(() => { load(); }, [load]);

  // Land here after the OAuth round trip: gmail_callback (chatty_web_server.py)
  // redirects the browser back to /settings?gmail=connected|error once Google's
  // consent screen completes. Surface it once, then drop the param so a page
  // refresh doesn't replay the toast.
  useEffect(() => {
    const result = searchParams.get('gmail');
    if (!result) return;
    if (result === 'connected') {
      showToast('Gmail connected', 'green');
      load();
    } else if (result === 'error') {
      showToast('Gmail connection failed — try again', 'red');
    }
    const next = new URLSearchParams(searchParams);
    next.delete('gmail');
    setSearchParams(next, { replace: true });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const handleConnect = async () => {
    setConnecting(true);
    try {
      window.location.href = await fetchGmailConnectUrl();
    } catch {
      showToast('Gmail reconnect isn’t set up on the server yet', 'red');
      setConnecting(false);
    }
  };

  const handleDisconnect = async () => {
    setDisconnecting(true);
    try {
      setStatus(await disconnectGmail());
      showToast('Gmail disconnected', 'green');
    } catch {
      showToast('Failed to disconnect Gmail', 'red');
    } finally {
      setDisconnecting(false);
    }
  };

  return (
    <Card padding="18px 22px" className="flex items-center justify-between gap-4">
      <div>
        <div className="mb-1 flex items-center gap-2.5">
          <span className="text-sm font-bold text-ink">Gmail</span>
          {loading ? (
            <Spinner size="sm" label="" />
          ) : (
            status && <Badge tone={STATUS_TONE[status.status]}>{STATUS_LABEL[status.status]}</Badge>
          )}
        </div>
        <p className="text-xs leading-snug text-muted">
          Lets the assistant read and manage your inbox. Reconnect here after the token expires,
          instead of re-running the auth flow on the server by hand.
        </p>
        {status && !status.reconnect_available && (
          <p className="mt-1.5 text-xs leading-snug text-alert-amber">
            Reconnect isn't configured on the server — a "Web application" OAuth client needs to be
            added in Google Cloud Console first.
          </p>
        )}
      </div>
      <div className="flex shrink-0 gap-2">
        {status?.status === 'connected' && (
          <button
            onClick={handleDisconnect}
            disabled={disconnecting}
            className="rounded-md border border-line px-3 py-1.5 text-xs font-semibold text-ink-dim hover:border-alert-red hover:text-alert-red disabled:opacity-50"
          >
            {disconnecting ? 'Disconnecting…' : 'Disconnect'}
          </button>
        )}
        {status?.status !== 'connected' && (
          <button
            onClick={handleConnect}
            disabled={connecting || !status?.reconnect_available}
            className="rounded-md bg-signal px-3 py-1.5 text-xs font-semibold text-white hover:opacity-90 disabled:opacity-50"
          >
            {connecting ? 'Redirecting…' : status?.status === 'expired' ? 'Reconnect' : 'Connect'}
          </button>
        )}
      </div>
    </Card>
  );
};

const Settings: React.FC = () => (
  <div className="mx-auto max-w-[900px] px-4 pb-12 pt-6 md:px-6">
    <PageHeader eyebrow="Assistant / Settings" eyebrowColor="var(--signal)" title="Settings" />
    <section>
      <h3 className="mb-3.5 font-mono text-[13px] uppercase tracking-wider text-muted">
        Integrations
      </h3>
      <div className="flex flex-col gap-3">
        <GmailCard />
      </div>
    </section>
  </div>
);

export default Settings;
