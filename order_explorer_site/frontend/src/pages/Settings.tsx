import React, { useCallback, useEffect, useState } from 'react';
import { useSearchParams } from 'react-router-dom';
import {
  fetchGmailStatus, fetchGmailConnectUrl, disconnectGmail,
  fetchWhatsAppStatus, disconnectWhatsApp,
  fetchLinkedInStatus, connectLinkedIn, disconnectLinkedIn,
} from '../chattyApi';
import type { GmailStatus, WhatsAppStatus, LinkedInStatus } from '../chattyApi';
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

const WHATSAPP_STATUS_LABEL: Record<WhatsAppStatus['status'], string> = {
  connected: 'Connected',
  qr_pending: 'Scan to connect',
  disconnected: 'Not connected',
  unavailable: 'Bridge offline',
};

const WHATSAPP_STATUS_TONE: Record<WhatsAppStatus['status'], 'teal' | 'gold' | 'neutral'> = {
  connected: 'teal',
  qr_pending: 'gold',
  disconnected: 'neutral',
  unavailable: 'neutral',
};

// Polls the bridge's status the whole time this card is mounted (cheap local
// call) rather than only while disconnected, so a QR scan on the phone or an
// unexpected drop both surface within a few seconds without extra plumbing.
const WHATSAPP_POLL_MS = 4000;

const WhatsAppCard: React.FC = () => {
  const [status, setStatus] = useState<WhatsAppStatus | null>(null);
  const [loading, setLoading] = useState(true);
  const [disconnecting, setDisconnecting] = useState(false);
  const { showToast } = useToast();

  const load = useCallback(async () => {
    try {
      setStatus(await fetchWhatsAppStatus());
    } catch {
      showToast('Failed to load WhatsApp status', 'red');
    } finally {
      setLoading(false);
    }
  }, [showToast]);

  useEffect(() => {
    load();
    const interval = setInterval(load, WHATSAPP_POLL_MS);
    return () => clearInterval(interval);
  }, [load]);

  const handleDisconnect = async () => {
    setDisconnecting(true);
    try {
      await disconnectWhatsApp();
      showToast('WhatsApp disconnected', 'green');
      await load();
    } catch {
      showToast('Failed to disconnect WhatsApp', 'red');
    } finally {
      setDisconnecting(false);
    }
  };

  return (
    <Card padding="18px 22px">
      <div className="flex items-center justify-between gap-4">
        <div>
          <div className="mb-1 flex items-center gap-2.5">
            <span className="text-sm font-bold text-ink">WhatsApp</span>
            {loading ? (
              <Spinner size="sm" label="" />
            ) : (
              status && <Badge tone={WHATSAPP_STATUS_TONE[status.status]}>{WHATSAPP_STATUS_LABEL[status.status]}</Badge>
            )}
          </div>
          <p className="text-xs leading-snug text-muted">
            {status?.status === 'connected' && status.phone
              ? `Lets the assistant read, search, and send messages as +${status.phone}.`
              : 'Lets the assistant read, search, and send WhatsApp messages. Scan the QR code with WhatsApp → Linked Devices to connect.'}
          </p>
          {status?.status === 'unavailable' && (
            <p className="mt-1.5 text-xs leading-snug text-alert-amber">
              The whatsapp-bridge service isn't running on the server.
            </p>
          )}
        </div>
        {status?.status === 'connected' && (
          <div className="flex shrink-0 gap-2">
            <button
              onClick={handleDisconnect}
              disabled={disconnecting}
              className="rounded-md border border-line px-3 py-1.5 text-xs font-semibold text-ink-dim hover:border-alert-red hover:text-alert-red disabled:opacity-50"
            >
              {disconnecting ? 'Disconnecting…' : 'Disconnect'}
            </button>
          </div>
        )}
      </div>
      {status?.status === 'qr_pending' && status.qr && (
        <div className="mt-4 flex justify-center rounded-md border border-line bg-white p-4">
          <img src={status.qr} alt="WhatsApp QR code" className="h-48 w-48" />
        </div>
      )}
    </Card>
  );
};

const LINKEDIN_STATUS_LABEL: Record<LinkedInStatus['status'], string> = {
  connected: 'Connected',
  disconnected: 'Not connected',
};

const LINKEDIN_STATUS_TONE: Record<LinkedInStatus['status'], 'teal' | 'neutral'> = {
  connected: 'teal',
  disconnected: 'neutral',
};

// Unlike Gmail/WhatsApp there's no OAuth redirect or QR scan: LinkedIn grants
// no third-party API access to messaging/feed/connections, so this connects
// with a session cookie pair (`li_at` + JSESSIONID) the user copies out of
// their own logged-in browser's devtools. This is unofficial and against
// LinkedIn's terms - see skills/linkedin_messages/linkedin_client.py.
const LinkedInCard: React.FC = () => {
  const [status, setStatus] = useState<LinkedInStatus | null>(null);
  const [loading, setLoading] = useState(true);
  const [connecting, setConnecting] = useState(false);
  const [disconnecting, setDisconnecting] = useState(false);
  const [showForm, setShowForm] = useState(false);
  const [liAt, setLiAt] = useState('');
  const [jsessionid, setJsessionid] = useState('');
  const { showToast } = useToast();

  const load = useCallback(async () => {
    try {
      setStatus(await fetchLinkedInStatus());
    } catch {
      showToast('Failed to load LinkedIn status', 'red');
    } finally {
      setLoading(false);
    }
  }, [showToast]);

  useEffect(() => { load(); }, [load]);

  const handleConnect = async () => {
    setConnecting(true);
    try {
      setStatus(await connectLinkedIn(liAt, jsessionid));
      showToast('LinkedIn connected', 'green');
      setShowForm(false);
      setLiAt('');
      setJsessionid('');
    } catch {
      showToast('LinkedIn rejected that cookie - it may be expired or incomplete', 'red');
    } finally {
      setConnecting(false);
    }
  };

  const handleDisconnect = async () => {
    setDisconnecting(true);
    try {
      await disconnectLinkedIn();
      showToast('LinkedIn disconnected', 'green');
      await load();
    } catch {
      showToast('Failed to disconnect LinkedIn', 'red');
    } finally {
      setDisconnecting(false);
    }
  };

  return (
    <Card padding="18px 22px">
      <div className="flex items-center justify-between gap-4">
        <div>
          <div className="mb-1 flex items-center gap-2.5">
            <span className="text-sm font-bold text-ink">LinkedIn</span>
            {loading ? (
              <Spinner size="sm" label="" />
            ) : (
              status && <Badge tone={LINKEDIN_STATUS_TONE[status.status]}>{LINKEDIN_STATUS_LABEL[status.status]}</Badge>
            )}
          </div>
          <p className="text-xs leading-snug text-muted">
            {status?.status === 'connected'
              ? `Lets the assistant read messages, feed, and connections as ${status.name ?? 'you'}.`
              : "Lets the assistant read (never send/post) LinkedIn messages, feed, and connections. Unofficial — uses a session cookie copied from your browser."}
          </p>
        </div>
        <div className="flex shrink-0 gap-2">
          {status?.status === 'connected' ? (
            <button
              onClick={handleDisconnect}
              disabled={disconnecting}
              className="rounded-md border border-line px-3 py-1.5 text-xs font-semibold text-ink-dim hover:border-alert-red hover:text-alert-red disabled:opacity-50"
            >
              {disconnecting ? 'Disconnecting…' : 'Disconnect'}
            </button>
          ) : (
            <button
              onClick={() => setShowForm((v) => !v)}
              className="rounded-md bg-signal px-3 py-1.5 text-xs font-semibold text-white hover:opacity-90"
            >
              Connect
            </button>
          )}
        </div>
      </div>
      {showForm && status?.status !== 'connected' && (
        <div className="mt-4 flex flex-col gap-2 rounded-md border border-line bg-surface-dim p-3">
          <p className="text-xs leading-snug text-muted">
            While logged into linkedin.com in your browser, open devtools → Application → Cookies →
            linkedin.com, and copy the <code>li_at</code> and <code>JSESSIONID</code> values here.
          </p>
          <input
            type="password"
            autoComplete="off"
            value={liAt}
            onChange={(e) => setLiAt(e.target.value)}
            placeholder="li_at cookie value"
            className="w-full rounded-md border border-line bg-surface px-2.5 py-1.5 text-sm text-ink outline-none focus:border-signal"
          />
          <input
            type="password"
            autoComplete="off"
            value={jsessionid}
            onChange={(e) => setJsessionid(e.target.value)}
            placeholder="JSESSIONID cookie value"
            className="w-full rounded-md border border-line bg-surface px-2.5 py-1.5 text-sm text-ink outline-none focus:border-signal"
          />
          <div className="flex justify-end gap-2">
            <button
              onClick={() => setShowForm(false)}
              className="rounded-md border border-line px-3 py-1.5 text-xs font-semibold text-ink-dim"
            >
              Cancel
            </button>
            <button
              onClick={handleConnect}
              disabled={connecting || !liAt.trim() || !jsessionid.trim()}
              className="rounded-md bg-signal px-3 py-1.5 text-xs font-semibold text-white hover:opacity-90 disabled:opacity-50"
            >
              {connecting ? 'Connecting…' : 'Connect'}
            </button>
          </div>
        </div>
      )}
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
        <WhatsAppCard />
        <LinkedInCard />
      </div>
    </section>
  </div>
);

export default Settings;
