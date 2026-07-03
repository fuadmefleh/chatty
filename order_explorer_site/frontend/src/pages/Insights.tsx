import React, { useEffect, useState } from 'react';
import {
  fetchWatchlist,
  createWatchTopic,
  deleteWatchTopic,
  fetchInsights,
  deleteInsight,
} from '../chattyApi';
import type { ChattyWatchTopic, ChattyInsight, WatchTopicKind } from '../chattyApi';
import PageHeader from '../components/ui/PageHeader';
import Card from '../components/ui/Card';

const formatLastRun = (lastRunAt: string | null): string => {
  if (!lastRunAt) return 'not yet checked';
  return `checked ${new Date(lastRunAt).toLocaleString()}`;
};

const KIND_LABELS: Record<WatchTopicKind, string> = {
  news: '📰 news',
  stock: '📈 stock',
  github: '🐙 github',
};

const KIND_PLACEHOLDERS: Record<WatchTopicKind, string> = {
  news: 'Keep an eye on…',
  stock: 'Ticker symbol, e.g. AAPL',
  github: 'owner/repo, e.g. anthropics/claude-code',
};

const Insights: React.FC = () => {
  const [topics, setTopics] = useState<ChattyWatchTopic[]>([]);
  const [insights, setInsights] = useState<ChattyInsight[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [newTopic, setNewTopic] = useState('');
  const [newKind, setNewKind] = useState<WatchTopicKind>('news');
  const [saving, setSaving] = useState(false);

  const load = async () => {
    setLoading(true);
    try {
      const [t, i] = await Promise.all([fetchWatchlist(), fetchInsights()]);
      setTopics(t);
      setInsights(i);
    } catch {
      setError('Failed to load insights');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => { load(); }, []);

  const handleAddTopic = async () => {
    const topic = newTopic.trim();
    if (!topic) return;
    setSaving(true);
    try {
      const created = await createWatchTopic(topic, newKind);
      setTopics((prev) => [created, ...prev]);
      setNewTopic('');
    } catch {
      setError('Failed to add watch topic');
    } finally {
      setSaving(false);
    }
  };

  const handleRemoveTopic = async (id: string) => {
    if (!confirm('Stop watching this topic?')) return;
    try {
      await deleteWatchTopic(id);
      setTopics((prev) => prev.filter((t) => t.id !== id));
    } catch {
      setError('Failed to remove watch topic');
    }
  };

  const handleDeleteInsight = async (id: string) => {
    if (!confirm('Delete this insight?')) return;
    try {
      await deleteInsight(id);
      setInsights((prev) => prev.filter((i) => i.id !== id));
    } catch {
      setError('Failed to delete insight');
    }
  };

  return (
    <div style={{ maxWidth: 760, margin: '0 auto', padding: '24px 24px 48px' }}>
      <PageHeader eyebrow="Assistant / Insights" eyebrowColor="var(--stamp-teal)" title="Insights" />

      {error && <p style={{ color: 'var(--danger)', marginBottom: 16 }}>{error}</p>}

      {/* Watchlist management */}
      <Card style={{ marginBottom: 28 }}>
        <div style={{ fontSize: 13, fontWeight: 700, color: 'var(--paper)', marginBottom: 12 }}>
          Watched topics
        </div>
        <div style={{ display: 'flex', gap: 8, marginBottom: topics.length ? 14 : 0 }}>
          <select
            value={newKind}
            onChange={(e) => setNewKind(e.target.value as WatchTopicKind)}
            style={{
              padding: '8px 10px', borderRadius: 8, border: '1px solid var(--ink-600)',
              fontSize: 13.5, fontFamily: 'inherit', outline: 'none',
              background: 'var(--ink-900)', color: 'var(--paper)',
            }}
          >
            <option value="news">News</option>
            <option value="stock">Stock</option>
            <option value="github">GitHub repo</option>
          </select>
          <input
            type="text"
            placeholder={KIND_PLACEHOLDERS[newKind]}
            value={newTopic}
            onChange={(e) => setNewTopic(e.target.value)}
            onKeyDown={(e) => { if (e.key === 'Enter') handleAddTopic(); }}
            style={{
              flex: 1, padding: '8px 12px', borderRadius: 8, border: '1px solid var(--ink-600)',
              fontSize: 14, fontFamily: 'inherit', outline: 'none',
              background: 'var(--ink-900)', color: 'var(--paper)',
            }}
          />
          <button
            onClick={handleAddTopic}
            disabled={saving || !newTopic.trim()}
            style={btnStyle('var(--stamp-teal)', saving || !newTopic.trim())}
          >
            {saving ? 'Saving…' : '+ Watch'}
          </button>
        </div>
        {topics.length > 0 && (
          <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
            {topics.map((topic) => (
              <div
                key={topic.id}
                style={{
                  display: 'flex', justifyContent: 'space-between', alignItems: 'center',
                  padding: '8px 12px', borderRadius: 8, background: 'var(--ink-900)',
                }}
              >
                <div>
                  <div style={{ fontSize: 14, color: 'var(--paper)' }}>
                    {topic.topic}
                    <span style={{
                      marginLeft: 8, fontSize: 10.5, fontFamily: 'var(--font-mono)', color: 'var(--muted)',
                      textTransform: 'uppercase', letterSpacing: '0.06em',
                    }}>
                      {KIND_LABELS[topic.kind] ?? topic.kind}
                    </span>
                  </div>
                  <div style={{ fontSize: 11.5, fontFamily: 'var(--font-mono)', color: 'var(--muted)' }}>
                    {formatLastRun(topic.last_run_at)}
                  </div>
                </div>
                <button onClick={() => handleRemoveTopic(topic.id)} style={btnSmall('transparent', 'var(--danger)')}>
                  Remove
                </button>
              </div>
            ))}
          </div>
        )}
      </Card>

      {/* Insight feed */}
      {loading ? (
        <p style={{ color: 'var(--muted)' }}>Loading insights…</p>
      ) : insights.length === 0 ? (
        <p style={{ color: 'var(--muted)', textAlign: 'center', marginTop: 40 }}>
          No insights yet. Watched topics are checked periodically in the background.
        </p>
      ) : (
        <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
          {insights.map((insight) => (
            <Card key={insight.id}>
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: 8 }}>
                <span style={{
                  fontFamily: 'var(--font-mono)', fontSize: 11, letterSpacing: '0.08em', textTransform: 'uppercase',
                  color: 'var(--stamp-teal)',
                }}>
                  {insight.topic}
                </span>
                <button onClick={() => handleDeleteInsight(insight.id)} style={btnSmall('transparent', 'var(--danger)')}>
                  Delete
                </button>
              </div>
              <p style={{ margin: '0 0 12px', fontSize: 14.5, whiteSpace: 'pre-wrap', color: 'var(--paper)', lineHeight: 1.6 }}>
                {insight.summary}
              </p>
              {insight.sources.length > 0 && (
                <div style={{ display: 'flex', flexDirection: 'column', gap: 4, marginBottom: 10 }}>
                  {insight.sources.map((source) => (
                    <a
                      key={source.url}
                      href={source.url}
                      target="_blank"
                      rel="noreferrer"
                      style={{ fontSize: 12.5, color: 'var(--stamp-gold)', textDecoration: 'none' }}
                    >
                      {source.title}
                    </a>
                  ))}
                </div>
              )}
              <span style={{ fontSize: 12, fontFamily: 'var(--font-mono)', color: 'var(--muted)' }}>
                {new Date(insight.created_at).toLocaleString()}
              </span>
            </Card>
          ))}
        </div>
      )}
    </div>
  );
};

const btnStyle = (color: string, disabled: boolean): React.CSSProperties => ({
  padding: '8px 18px', borderRadius: 8, border: 'none',
  background: disabled ? 'var(--ink-700)' : color,
  color: disabled ? 'var(--muted)' : color === 'var(--ink-700)' ? 'var(--paper)' : 'var(--ink-900)',
  fontWeight: 700, fontSize: 13,
});

const btnSmall = (bg: string, fg: string): React.CSSProperties => ({
  padding: '4px 12px', borderRadius: 6, border: bg === 'transparent' ? '1px solid var(--ink-600)' : 'none',
  background: bg, color: fg, fontWeight: 600,
  fontSize: 12,
});

export default Insights;
