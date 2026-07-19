import React, { useCallback, useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import {
  fetchLinkedInStatus, fetchLinkedInConversations, fetchLinkedInConversationMessages,
  fetchLinkedInFeed, fetchLinkedInConnections,
} from '../chattyApi';
import type {
  LinkedInStatus, LinkedInConversation, LinkedInMessage, LinkedInPost, LinkedInConnection,
} from '../chattyApi';
import PageHeader from '../components/ui/PageHeader';
import Card from '../components/ui/Card';
import Badge from '../components/ui/Badge';
import Spinner from '../components/ui/Spinner';
import EmptyState from '../components/ui/EmptyState';

// Read-only dashboard for LinkedIn (see Settings.tsx's LinkedInCard for the
// connect flow). Lower-volume than WhatsApp's chat browser, so this stays a
// single tabbed page rather than a chat-list-plus-thread layout — no polling
// interval either, since there's no live session to keep in sync with, just
// a "refresh" the user triggers themselves.
type Tab = 'messages' | 'feed' | 'connections';

const NotConnectedNotice: React.FC = () => (
  <EmptyState
    title="LinkedIn isn't connected"
    description="Connect it from the Settings page to see messages, feed, and connections here."
    action={
      <Link
        to="/settings"
        className="rounded-md bg-signal px-3 py-1.5 text-xs font-semibold text-white hover:opacity-90"
      >
        Go to Settings
      </Link>
    }
  />
);

const ConversationsPanel: React.FC = () => {
  const [conversations, setConversations] = useState<LinkedInConversation[] | null>(null);
  const [selected, setSelected] = useState<string | null>(null);
  const [messages, setMessages] = useState<LinkedInMessage[] | null>(null);
  const [error, setError] = useState('');

  useEffect(() => {
    fetchLinkedInConversations()
      .then(setConversations)
      .catch(() => setError('Failed to load conversations.'));
  }, []);

  useEffect(() => {
    if (!selected) return;
    setMessages(null);
    fetchLinkedInConversationMessages(selected)
      .then(setMessages)
      .catch(() => setError('Failed to load this conversation.'));
  }, [selected]);

  if (conversations === null) return <Spinner size="sm" label="Loading conversations…" />;
  if (error) return <p className="text-sm text-alert-red">{error}</p>;
  if (conversations.length === 0) return <p className="text-sm text-muted">No conversations found.</p>;

  return (
    <div className="flex gap-4">
      <div className="flex w-64 shrink-0 flex-col gap-1">
        {conversations.map((c) => (
          <button
            key={c.conversation_id}
            onClick={() => setSelected(c.conversation_id)}
            className={`flex flex-col gap-0.5 rounded-md px-2.5 py-2 text-left ${
              selected === c.conversation_id ? 'bg-signal/15' : 'hover:bg-surface-dim'
            }`}
          >
            <div className="flex items-center justify-between gap-2">
              <span className="truncate text-sm font-medium text-ink">
                {c.participants.join(', ') || 'Unknown'}
              </span>
              {c.unread_count > 0 && <Badge tone="gold">{c.unread_count}</Badge>}
            </div>
            <span className="truncate text-xs text-muted">{c.last_message || ' '}</span>
          </button>
        ))}
      </div>
      <div className="min-w-0 flex-1">
        {!selected ? (
          <p className="text-sm text-muted">Select a conversation to read it.</p>
        ) : messages === null ? (
          <Spinner size="sm" label="Loading messages…" />
        ) : messages.length === 0 ? (
          <p className="text-sm text-muted">No messages in this conversation.</p>
        ) : (
          <div className="flex flex-col gap-2">
            {messages.map((m, i) => (
              <div key={i} className="rounded-lg bg-surface-dim px-3 py-2">
                <div className="mb-0.5 text-xs font-semibold text-ink">{m.sender || 'Unknown'}</div>
                <p className="whitespace-pre-wrap text-sm text-ink">{m.message}</p>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
};

const FeedPanel: React.FC = () => {
  const [posts, setPosts] = useState<LinkedInPost[] | null>(null);
  const [error, setError] = useState('');

  useEffect(() => {
    fetchLinkedInFeed().then(setPosts).catch(() => setError('Failed to load your feed.'));
  }, []);

  if (posts === null) return <Spinner size="sm" label="Loading feed…" />;
  if (error) return <p className="text-sm text-alert-red">{error}</p>;
  if (posts.length === 0) return <p className="text-sm text-muted">No feed posts found.</p>;

  return (
    <div className="flex flex-col gap-3">
      {posts.map((p, i) => (
        <Card key={i} padding="14px 18px">
          <div className="mb-1 flex items-center justify-between gap-2">
            <span className="text-sm font-bold text-ink">{p.author || 'Unknown'}</span>
            {p.posted_at && <span className="text-xs text-muted">{p.posted_at}</span>}
          </div>
          <p className="whitespace-pre-wrap text-sm text-ink">{p.text}</p>
          {p.url && (
            <a href={p.url} target="_blank" rel="noreferrer" className="mt-1.5 inline-block text-xs text-signal">
              View on LinkedIn →
            </a>
          )}
        </Card>
      ))}
    </div>
  );
};

const ConnectionsPanel: React.FC = () => {
  const [connections, setConnections] = useState<LinkedInConnection[] | null>(null);
  const [error, setError] = useState('');

  useEffect(() => {
    fetchLinkedInConnections().then(setConnections).catch(() => setError('Failed to load connections.'));
  }, []);

  if (connections === null) return <Spinner size="sm" label="Loading connections…" />;
  if (error) return <p className="text-sm text-alert-red">{error}</p>;
  if (connections.length === 0) return <p className="text-sm text-muted">No connections found.</p>;

  return (
    <div className="grid grid-cols-1 gap-2 sm:grid-cols-2 lg:grid-cols-3">
      {connections.map((c, i) => (
        <Card key={i} padding="12px 16px">
          <div className="text-sm font-bold text-ink">{c.name || 'Unknown'}</div>
          {c.title && <div className="text-xs text-muted">{c.title}</div>}
          {c.location && <div className="text-xs text-muted">{c.location}</div>}
        </Card>
      ))}
    </div>
  );
};

const TABS: { id: Tab; label: string }[] = [
  { id: 'messages', label: 'Messages' },
  { id: 'feed', label: 'Feed' },
  { id: 'connections', label: 'Connections' },
];

const LinkedInLayout: React.FC = () => {
  const [status, setStatus] = useState<LinkedInStatus | null>(null);
  const [tab, setTab] = useState<Tab>('messages');

  const loadStatus = useCallback(() => {
    fetchLinkedInStatus().then(setStatus).catch(() => setStatus(null));
  }, []);

  useEffect(() => { loadStatus(); }, [loadStatus]);

  return (
    <div className="mx-auto max-w-[1100px] px-4 pb-12 pt-6 md:px-6">
      <PageHeader eyebrow="Assistant / LinkedIn" eyebrowColor="var(--signal)" title="LinkedIn" />

      {status === null ? (
        <Spinner size="sm" label="Loading…" />
      ) : status.status !== 'connected' ? (
        <NotConnectedNotice />
      ) : (
        <>
          <div className="mb-5 flex gap-2 border-b border-line">
            {TABS.map((t) => (
              <button
                key={t.id}
                onClick={() => setTab(t.id)}
                className={`px-3 py-2 text-sm font-semibold ${
                  tab === t.id ? 'border-b-2 border-signal text-signal' : 'text-muted hover:text-ink'
                }`}
              >
                {t.label}
              </button>
            ))}
          </div>
          {tab === 'messages' && <ConversationsPanel />}
          {tab === 'feed' && <FeedPanel />}
          {tab === 'connections' && <ConnectionsPanel />}
        </>
      )}
    </div>
  );
};

export default LinkedInLayout;
