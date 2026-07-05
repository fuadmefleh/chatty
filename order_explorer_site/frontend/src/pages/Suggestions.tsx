import React, { useEffect, useState, useCallback } from 'react';
import { Link } from 'react-router-dom';
import {
  fetchTrendingSuggestions,
  scanTrendingSuggestions,
  implementTrendingSuggestion,
  dismissTrendingSuggestion,
  deleteTrendingSuggestion,
} from '../chattyApi';
import type { TrendingSuggestion, TrendingSuggestionStatus } from '../chattyApi';
import { useToast } from '../hooks/useToast';
import PageHeader from '../components/ui/PageHeader';
import Card from '../components/ui/Card';
import Badge from '../components/ui/Badge';
import Spinner from '../components/ui/Spinner';
import EmptyState from '../components/ui/EmptyState';

type Filter = 'pending' | 'implemented' | 'dismissed' | 'all';

const statusTone: Record<TrendingSuggestionStatus, 'gold' | 'teal' | 'neutral'> = {
  pending: 'gold',
  implemented: 'teal',
  dismissed: 'neutral',
};

const FILTERS: Filter[] = ['pending', 'implemented', 'dismissed', 'all'];

const Suggestions: React.FC = () => {
  const { showToast } = useToast();
  const [suggestions, setSuggestions] = useState<TrendingSuggestion[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [scanning, setScanning] = useState(false);
  const [filter, setFilter] = useState<Filter>('pending');
  const [expanded, setExpanded] = useState<Set<string>>(new Set());
  const [actingId, setActingId] = useState<string | null>(null);

  const load = useCallback(async () => {
    try {
      const data = await fetchTrendingSuggestions();
      setSuggestions(data);
      setError('');
    } catch {
      setError('Failed to load suggestions');
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { load(); }, [load]);

  const handleScan = async () => {
    setScanning(true);
    try {
      const data = await scanTrendingSuggestions();
      setSuggestions(data);
      showToast('Scan complete.', 'signal');
    } catch {
      showToast('Scan failed.', 'red');
    } finally {
      setScanning(false);
    }
  };

  const handleImplement = async (s: TrendingSuggestion) => {
    setActingId(s.id);
    try {
      const updated = await implementTrendingSuggestion(s.id);
      setSuggestions((prev) => prev.map((x) => (x.id === updated.id ? updated : x)));
      showToast('Routed to feature requests.', 'green');
    } catch {
      showToast('Failed to implement suggestion.', 'red');
    } finally {
      setActingId(null);
    }
  };

  const handleDismiss = async (s: TrendingSuggestion) => {
    setActingId(s.id);
    try {
      const updated = await dismissTrendingSuggestion(s.id);
      setSuggestions((prev) => prev.map((x) => (x.id === updated.id ? updated : x)));
    } catch {
      showToast('Failed to dismiss suggestion.', 'red');
    } finally {
      setActingId(null);
    }
  };

  const handleDelete = async (id: string) => {
    if (!confirm('Remove this suggestion?')) return;
    try {
      await deleteTrendingSuggestion(id);
      setSuggestions((prev) => prev.filter((s) => s.id !== id));
    } catch {
      showToast('Failed to remove suggestion.', 'red');
    }
  };

  const toggleExpanded = (id: string) => {
    setExpanded((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  };

  const visible = suggestions.filter((s) => filter === 'all' || s.status === filter);
  const pendingCount = suggestions.filter((s) => s.status === 'pending').length;

  return (
    <div className="mx-auto max-w-[860px] px-4 py-6 md:px-6">
      <PageHeader
        eyebrow="Assistant / Suggestions"
        eyebrowColor="var(--signal)"
        title="Self-Improve Suggestions"
        actions={
          <button
            type="button"
            onClick={handleScan}
            disabled={scanning}
            className={`rounded-lg px-4 py-2 text-sm font-bold ${
              scanning ? 'bg-surface-dim text-muted' : 'bg-signal text-white'
            }`}
          >
            {scanning ? <Spinner size="sm" label="Scanning…" /> : 'Scan now'}
          </button>
        }
      />
      <p className="-mt-4 mb-6 text-sm text-muted">
        Every few hours, Chatty scans GitHub's trending Python, TypeScript, and JavaScript
        repos and curates a short list of ideas worth considering. Nothing is built
        automatically - pick <strong>Implement</strong> to route an idea through the same
        Pi coding-agent pipeline as a feature request, or <strong>Dismiss</strong> to hide it.
      </p>

      <div className="mb-5 flex flex-wrap gap-2">
        {FILTERS.map((f) => (
          <button
            key={f}
            type="button"
            onClick={() => setFilter(f)}
            className={`rounded-md px-3 py-1 text-xs font-semibold capitalize ${
              filter === f ? 'bg-signal text-white' : 'bg-surface-dim text-ink-dim'
            }`}
          >
            {f}
            {f === 'pending' && pendingCount > 0 ? ` (${pendingCount})` : ''}
          </button>
        ))}
      </div>

      {error && <p className="mb-4 text-alert-red">{error}</p>}

      {loading ? (
        <Spinner label="Loading suggestions…" />
      ) : visible.length === 0 ? (
        <EmptyState
          title={filter === 'pending' ? 'No pending suggestions' : `No ${filter} suggestions`}
          description={
            filter === 'pending'
              ? 'Click "Scan now" to check GitHub trending right away, or wait for the next heartbeat cycle.'
              : undefined
          }
        />
      ) : (
        <div className="flex flex-col gap-3">
          {visible.map((s) => (
            <Card key={s.id}>
              <div className="mb-2.5 flex items-start justify-between gap-3">
                <div>
                  <a
                    href={s.repo_url}
                    target="_blank"
                    rel="noreferrer"
                    className="font-mono text-sm font-bold text-ink hover:underline"
                  >
                    {s.repo}
                  </a>
                  <div className="mt-1 flex flex-wrap gap-1.5">
                    <Badge tone="teal">{s.language}</Badge>
                    <Badge tone="gold">★ {s.stars}</Badge>
                  </div>
                </div>
                <Badge tone={statusTone[s.status]}>{s.status}</Badge>
              </div>

              {s.description && (
                <p className="m-0 mb-2 text-sm leading-relaxed text-ink">{s.description}</p>
              )}
              {s.rationale && (
                <p className="m-0 mb-2 text-sm italic leading-relaxed text-ink-dim">{s.rationale}</p>
              )}

              <div className="flex flex-wrap items-center justify-between gap-2">
                <span className="font-mono text-xs text-muted">
                  {new Date(s.created_at).toLocaleString()}
                </span>
                <div className="flex gap-2">
                  {s.integration_prompt && (
                    <button
                      type="button"
                      onClick={() => toggleExpanded(s.id)}
                      className="rounded-md bg-surface-dim px-3 py-1 text-xs font-semibold text-ink-dim"
                    >
                      {expanded.has(s.id) ? 'Hide prompt' : 'Show prompt'}
                    </button>
                  )}

                  {s.status === 'pending' && (
                    <>
                      <button
                        type="button"
                        onClick={() => handleDismiss(s)}
                        disabled={actingId === s.id}
                        className="rounded-md border border-line bg-transparent px-3 py-1 text-xs font-semibold text-ink-dim disabled:opacity-60"
                      >
                        Dismiss
                      </button>
                      <button
                        type="button"
                        onClick={() => handleImplement(s)}
                        disabled={actingId === s.id}
                        className="rounded-md bg-signal px-3 py-1 text-xs font-bold text-white disabled:opacity-60"
                      >
                        {actingId === s.id ? 'Implementing…' : 'Implement'}
                      </button>
                    </>
                  )}

                  {s.status === 'implemented' && s.request_id && (
                    <Link
                      to="/requests"
                      className="rounded-md bg-surface-dim px-3 py-1 text-xs font-semibold text-signal"
                    >
                      View request →
                    </Link>
                  )}

                  {s.status === 'dismissed' && (
                    <button
                      type="button"
                      onClick={() => handleDelete(s.id)}
                      className="rounded-md border border-line bg-transparent px-3 py-1 text-xs font-semibold text-alert-red"
                    >
                      Delete
                    </button>
                  )}
                </div>
              </div>

              {expanded.has(s.id) && s.integration_prompt && (
                <pre className="mt-3 max-h-80 overflow-y-auto overflow-x-auto whitespace-pre-wrap break-words rounded-lg border border-line bg-surface-dim p-3.5 font-mono text-xs leading-relaxed text-ink-dim">
                  {s.integration_prompt}
                </pre>
              )}
            </Card>
          ))}
        </div>
      )}
    </div>
  );
};

export default Suggestions;
