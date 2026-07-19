import React, { useCallback, useEffect, useState } from 'react';
import { Link, Outlet, useParams } from 'react-router-dom';
import { fetchWhatsAppChats, fetchWhatsAppStatus } from '../chattyApi';
import type { WhatsAppChat, WhatsAppStatus } from '../chattyApi';
import Badge from '../components/ui/Badge';
import Spinner from '../components/ui/Spinner';
import EmptyState from '../components/ui/EmptyState';
import { WhatsAppChatsContext } from '../hooks/useWhatsAppChats';

const CHATS_POLL_MS = 5000;

const formatChatTimestamp = (ts: string | null): string => {
  if (!ts) return '';
  const date = new Date(ts);
  const isToday = date.toDateString() === new Date().toDateString();
  return isToday
    ? date.toLocaleTimeString([], { hour: 'numeric', minute: '2-digit' })
    : date.toLocaleDateString([], { month: 'short', day: 'numeric' });
};

/** Persistent shell for /whatsapp: a left-hand chat list that stays mounted
 * across chat threads (mirrors WikiLayout's list+Outlet shape), sharing its
 * fetched chat list with the thread pane via WhatsAppChatsContext so a send/
 * managed-toggle in the thread can refresh the sidebar's preview/unread
 * count without a second independent poll. */
const WhatsAppLayout: React.FC = () => {
  const { jid: activeJid } = useParams<{ jid: string }>();
  const [chats, setChats] = useState<WhatsAppChat[] | null>(null);
  const [status, setStatus] = useState<WhatsAppStatus | null>(null);
  const [error, setError] = useState('');

  const load = useCallback(async () => {
    try {
      const [chatList, whatsappStatus] = await Promise.all([fetchWhatsAppChats(), fetchWhatsAppStatus()]);
      setChats(chatList);
      setStatus(whatsappStatus);
      setError('');
    } catch {
      setError('Failed to load WhatsApp chats.');
    }
  }, []);

  useEffect(() => {
    load();
    const interval = setInterval(load, CHATS_POLL_MS);
    return () => clearInterval(interval);
  }, [load]);

  return (
    <WhatsAppChatsContext.Provider value={{ chats: chats ?? [], refreshChats: load }}>
      <div className="mx-auto flex max-w-[1400px] items-start gap-6 px-4 py-6 md:px-6">
        <aside className="sticky top-6 flex h-[calc(100vh-72px)] w-72 shrink-0 flex-col gap-3 self-start">
          <div className="flex items-center justify-between">
            <p className="font-mono text-[11px] font-semibold uppercase tracking-wider text-muted">WhatsApp</p>
            {status && status.status !== 'connected' && (
              <Link to="/settings">
                <Badge tone={status.status === 'qr_pending' ? 'gold' : 'neutral'}>
                  {status.status === 'qr_pending' ? 'Scan QR' : status.status === 'unavailable' ? 'Bridge offline' : 'Not connected'}
                </Badge>
              </Link>
            )}
          </div>

          <div className="min-h-0 flex-1 overflow-y-auto">
            {chats === null ? (
              <Spinner size="sm" label="Loading chats…" />
            ) : error ? (
              <p className="text-sm text-alert-red">{error}</p>
            ) : chats.length === 0 ? (
              <p className="text-sm text-muted">No chats yet.</p>
            ) : (
              <div className="flex flex-col gap-0.5">
                {chats.map((chat) => {
                  const isActive = activeJid === chat.jid;
                  return (
                    <Link
                      key={chat.jid}
                      to={`/whatsapp/${encodeURIComponent(chat.jid)}`}
                      className={`flex flex-col gap-0.5 rounded-md px-2.5 py-2 ${
                        isActive ? 'bg-signal/15' : 'hover:bg-surface-dim'
                      }`}
                    >
                      <div className="flex items-center justify-between gap-2">
                        <span className={`truncate text-sm ${isActive ? 'font-semibold text-signal' : 'font-medium text-ink'}`}>
                          {chat.name || chat.jid.split('@')[0]}
                        </span>
                        <span className="shrink-0 font-mono text-[10px] text-muted">
                          {formatChatTimestamp(chat.last_message_ts)}
                        </span>
                      </div>
                      <div className="flex items-center justify-between gap-2">
                        <span className="truncate text-xs text-muted">{chat.last_message || ' '}</span>
                        <div className="flex shrink-0 items-center gap-1">
                          {chat.managed && <Badge tone="teal">Auto</Badge>}
                          {chat.unread_count > 0 && <Badge tone="gold">{chat.unread_count}</Badge>}
                        </div>
                      </div>
                    </Link>
                  );
                })}
              </div>
            )}
          </div>
        </aside>

        <div className="min-w-0 flex-1">
          <Outlet />
        </div>
      </div>
    </WhatsAppChatsContext.Provider>
  );
};

export const WhatsAppEmpty: React.FC = () => (
  <EmptyState title="Select a chat" description="Pick a conversation from the list to read and reply to it." />
);

export default WhatsAppLayout;
