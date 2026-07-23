import React, { useCallback, useEffect, useMemo, useState } from 'react';
import { useParams } from 'react-router-dom';
import {
  fetchWhatsAppThread, sendWhatsAppChatMessage, markWhatsAppChatRead,
  setWhatsAppChatManaged, unsetWhatsAppChatManaged,
} from '../chattyApi';
import type { WhatsAppMessage } from '../chattyApi';
import Card from '../components/ui/Card';
import Badge from '../components/ui/Badge';
import Spinner from '../components/ui/Spinner';
import { useToast } from '../hooks/useToast';
import { useWhatsAppChats } from '../hooks/useWhatsAppChats';

const THREAD_POLL_MS = 4000;
const GROUP_JID_SUFFIX = '@g.us';

const BUBBLE_CLASS: Record<WhatsAppMessage['direction'], string> = {
  in: 'self-start bg-surface-dim text-ink',
  out: 'self-end bg-signal text-white',
  auto: 'self-end bg-signal/70 text-white',
};

const formatTimestamp = (ts: string): string => new Date(ts).toLocaleString([], {
  month: 'short', day: 'numeric', hour: 'numeric', minute: '2-digit',
});

const WhatsAppThread: React.FC = () => {
  const { jid } = useParams<{ jid: string }>();
  const { chats, refreshChats } = useWhatsAppChats();
  const { showToast } = useToast();

  const [messages, setMessages] = useState<WhatsAppMessage[] | null>(null);
  const [error, setError] = useState('');
  const [composeText, setComposeText] = useState('');
  const [sending, setSending] = useState(false);
  const [managing, setManaging] = useState(false);
  const [instructionsDraft, setInstructionsDraft] = useState('');
  const [savingManaged, setSavingManaged] = useState(false);

  const chat = useMemo(() => chats.find((c) => c.jid === jid), [chats, jid]);
  const isGroup = jid?.endsWith(GROUP_JID_SUFFIX) ?? false;

  const load = useCallback(async () => {
    if (!jid) return;
    try {
      setMessages(await fetchWhatsAppThread(jid));
      setError('');
    } catch {
      setError('Failed to load this chat.');
    }
  }, [jid]);

  useEffect(() => {
    setMessages(null);
    load();
    const interval = setInterval(load, THREAD_POLL_MS);
    return () => clearInterval(interval);
  }, [load]);

  // Mark read once per chat open, not on every poll tick.
  useEffect(() => {
    if (!jid) return;
    markWhatsAppChatRead(jid).then(refreshChats).catch(() => {});
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [jid]);

  const handleSend = async () => {
    if (!jid || !composeText.trim()) return;
    setSending(true);
    try {
      await sendWhatsAppChatMessage(jid, composeText.trim());
      setComposeText('');
      await load();
      refreshChats();
    } catch {
      showToast('Failed to send message', 'red');
    } finally {
      setSending(false);
    }
  };

  const handleEnableManaged = async () => {
    if (!jid) return;
    setSavingManaged(true);
    try {
      await setWhatsAppChatManaged(jid, chat?.name ?? null, instructionsDraft.trim());
      showToast('Atlas will now auto-reply in this chat', 'green');
      setManaging(false);
      setInstructionsDraft('');
      refreshChats();
    } catch {
      showToast('Failed to enable auto-reply for this chat', 'red');
    } finally {
      setSavingManaged(false);
    }
  };

  const handleDisableManaged = async () => {
    if (!jid) return;
    try {
      await unsetWhatsAppChatManaged(jid);
      showToast('Auto-reply turned off for this chat', 'green');
      refreshChats();
    } catch {
      showToast('Failed to turn off auto-reply', 'red');
    }
  };

  if (!jid) return null;

  return (
    <div className="flex h-[calc(100vh-72px)] flex-col gap-3">
      <Card padding="14px 18px" className="flex shrink-0 items-center justify-between gap-3">
        <div>
          <div className="flex items-center gap-2">
            <span className="text-sm font-bold text-ink">{chat?.name || jid.split('@')[0]}</span>
            {chat?.managed && <Badge tone="teal">Auto-reply on</Badge>}
            {isGroup && <Badge tone="neutral">Group</Badge>}
          </div>
        </div>
        {chat?.managed ? (
          <button
            onClick={handleDisableManaged}
            className="rounded-md border border-line px-3 py-1.5 text-xs font-semibold text-ink-dim hover:border-alert-red hover:text-alert-red"
          >
            Stop managing
          </button>
        ) : (
          <button
            onClick={() => setManaging((v) => !v)}
            className="rounded-md bg-signal px-3 py-1.5 text-xs font-semibold text-white hover:opacity-90"
          >
            Manage with Atlas
          </button>
        )}
      </Card>

      {managing && !chat?.managed && (
        <Card padding="14px 18px" className="flex shrink-0 flex-col gap-2">
          <p className="text-xs leading-snug text-muted">
            Atlas will read and reply in this chat on its own during heartbeat runs, with no approval per
            message{isGroup ? ' — and everyone in this group will see what it sends, not just one person' : ''}.
            Optionally tell it how to handle this chat:
          </p>
          <textarea
            value={instructionsDraft}
            onChange={(e) => setInstructionsDraft(e.target.value)}
            placeholder="e.g. Reply casually as me, keep it short. If they ask about money, say I'll call them."
            rows={2}
            className="w-full rounded-md border border-line bg-surface px-2.5 py-1.5 text-sm text-ink outline-none focus:border-signal"
          />
          <div className="flex justify-end gap-2">
            <button
              onClick={() => setManaging(false)}
              className="rounded-md border border-line px-3 py-1.5 text-xs font-semibold text-ink-dim"
            >
              Cancel
            </button>
            <button
              onClick={handleEnableManaged}
              disabled={savingManaged}
              className="rounded-md bg-signal px-3 py-1.5 text-xs font-semibold text-white hover:opacity-90 disabled:opacity-50"
            >
              {savingManaged ? 'Enabling…' : 'Enable auto-reply'}
            </button>
          </div>
        </Card>
      )}

      <Card padding="14px 18px" className="flex min-h-0 flex-1 flex-col overflow-y-auto">
        {messages === null ? (
          <Spinner size="sm" label="Loading messages…" />
        ) : error ? (
          <p className="text-sm text-alert-red">{error}</p>
        ) : messages.length === 0 ? (
          <p className="text-sm text-muted">No messages yet.</p>
        ) : (
          <div className="flex flex-col gap-2">
            {messages.map((m, i) => (
              <div key={i} className={`flex max-w-[75%] flex-col gap-0.5 rounded-lg px-3 py-2 ${BUBBLE_CLASS[m.direction]}`}>
                {m.direction === 'auto' && (
                  <span className="font-mono text-[10px] uppercase tracking-wider opacity-80">🤖 auto-reply</span>
                )}
                <span className="whitespace-pre-wrap text-sm">{m.message}</span>
                <span className="self-end text-[10px] opacity-70">{formatTimestamp(m.timestamp)}</span>
              </div>
            ))}
          </div>
        )}
      </Card>

      <Card padding="10px 14px" className="flex shrink-0 items-end gap-2">
        <textarea
          value={composeText}
          onChange={(e) => setComposeText(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === 'Enter' && !e.shiftKey) {
              e.preventDefault();
              handleSend();
            }
          }}
          placeholder="Type a message…"
          rows={1}
          className="min-w-0 flex-1 resize-none rounded-md border border-line bg-surface px-2.5 py-1.5 text-sm text-ink outline-none focus:border-signal"
        />
        <button
          onClick={handleSend}
          disabled={sending || !composeText.trim()}
          className="shrink-0 rounded-md bg-signal px-3 py-1.5 text-xs font-semibold text-white hover:opacity-90 disabled:opacity-50"
        >
          {sending ? 'Sending…' : 'Send'}
        </button>
      </Card>
    </div>
  );
};

export default WhatsAppThread;
