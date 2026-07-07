import React, { useEffect, useState, useRef, useCallback } from 'react';
import {
  fetchFeatureRequests,
  createFeatureRequest,
  deleteFeatureRequest,
  retryPendingMerges,
} from '../chattyApi';
import type { FeatureRequest, FeatureRequestStatus } from '../chattyApi';
import PageHeader from '../components/ui/PageHeader';
import Card from '../components/ui/Card';
import Badge from '../components/ui/Badge';
import Spinner from '../components/ui/Spinner';
import PulseDot from '../components/ui/PulseDot';
import EmptyState from '../components/ui/EmptyState';
import { useToast } from '../hooks/useToast';

const POLL_MS = 3000;

const statusTone: Record<FeatureRequestStatus, 'neutral' | 'teal' | 'gold' | 'ember'> = {
  queued: 'neutral',
  running: 'teal',
  testing: 'gold',
  merge_pending: 'gold',
  completed: 'teal',
  error: 'ember',
};

const StatusBadge: React.FC<{ status: FeatureRequestStatus }> = ({ status }) => (
  <Badge tone={statusTone[status]}>{status}</Badge>
);

const Requests: React.FC = () => {
  const [requests, setRequests] = useState<FeatureRequest[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [prompt, setPrompt] = useState('');
  const [submitting, setSubmitting] = useState(false);
  const [expanded, setExpanded] = useState<Set<string>>(new Set());
  const [retryingId, setRetryingId] = useState<string | null>(null);
  const [retryingMerges, setRetryingMerges] = useState(false);
  const pollRef = useRef<ReturnType<typeof setInterval> | null>(null);
  const { showToast } = useToast();

  const load = useCallback(async () => {
    try {
      const data = await fetchFeatureRequests();
      setRequests(data);
      setError('');
    } catch {
      setError('Failed to load requests');
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { load(); }, [load]);

  // Poll while anything is queued/running/testing/waiting on a clean main to
  // merge into; stop once everything has settled.
  const pending = requests.some((r) =>
    r.status === 'queued' || r.status === 'running' || r.status === 'testing' || r.status === 'merge_pending'
  );
  const pendingMerges = requests.filter((r) => r.status === 'merge_pending');

  useEffect(() => {
    if (pending && !pollRef.current) {
      pollRef.current = setInterval(load, POLL_MS);
    } else if (!pending && pollRef.current) {
      clearInterval(pollRef.current);
      pollRef.current = null;
    }

    return () => {
      if (pollRef.current) {
        clearInterval(pollRef.current);
        pollRef.current = null;
      }
    };
  }, [pending, load]);

  const handleSubmit = async () => {
    const text = prompt.trim();
    if (!text) return;
    setSubmitting(true);
    try {
      const created = await createFeatureRequest(text);
      setRequests((prev) => [created, ...prev]);
      setPrompt('');
    } catch {
      setError('Failed to submit request');
    } finally {
      setSubmitting(false);
    }
  };

  const handleRetry = async (r: FeatureRequest) => {
    setRetryingId(r.id);
    try {
      const created = await createFeatureRequest(r.prompt);
      setRequests((prev) => [created, ...prev]);
    } catch {
      setError('Failed to retry request');
    } finally {
      setRetryingId(null);
    }
  };

  const handleRetryMerges = async () => {
    setRetryingMerges(true);
    try {
      const { summaries } = await retryPendingMerges();
      await load();
      if (summaries.length > 0) {
        showToast(summaries.join(' · '), 'green');
      } else {
        showToast('Still waiting on a clean main - will retry again automatically.', 'amber');
      }
    } catch {
      showToast('Failed to retry merges', 'red');
    } finally {
      setRetryingMerges(false);
    }
  };

  const handleDelete = async (id: string) => {
    if (!confirm('Delete this request?')) return;
    try {
      await deleteFeatureRequest(id);
      setRequests((prev) => prev.filter((r) => r.id !== id));
    } catch {
      setError('Failed to delete request');
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

  return (
    <div className="mx-auto max-w-[860px] px-4 py-6 md:px-6">
      <PageHeader
        eyebrow="Assistant / Requests"
        eyebrowColor="var(--signal)"
        title="Feature requests"
        actions={pending ? <PulseDot tone="signal" label="Live" /> : undefined}
      />
      <p className="-mt-4 mb-6 text-sm text-muted">
        Describe a feature or fix. It's routed to the local Pi coding agent (qwen3.6-27b),
        which edits the Chatty codebase directly. Entries marked 🤖 self-upgrade were proposed by
        Chatty's own heartbeat - those run in an isolated branch, must pass the test suite, and
        only then auto-merge and restart the affected services on their own.
      </p>

      {pendingMerges.length > 0 && (
        <Card className="mb-6 flex flex-wrap items-center justify-between gap-3 border-signal/40">
          <p className="m-0 text-sm text-ink">
            {pendingMerges.length} change{pendingMerges.length === 1 ? '' : 's'} waiting for a clean
            main to merge - retried automatically every heartbeat, or right now:
          </p>
          <button
            type="button"
            onClick={handleRetryMerges}
            disabled={retryingMerges}
            className="shrink-0 rounded-lg bg-signal px-4 py-2 text-sm font-bold text-white disabled:opacity-60"
          >
            {retryingMerges ? 'Retrying…' : 'Retry now'}
          </button>
        </Card>
      )}

      {/* Submit */}
      <Card className="mb-7">
        <textarea
          placeholder="e.g. Add a /weather command that shows tomorrow's forecast too…"
          value={prompt}
          onChange={(e) => setPrompt(e.target.value)}
          rows={3}
          className="w-full resize-y rounded-lg border border-line bg-surface px-3.5 py-2.5 text-sm text-ink outline-none focus:border-signal"
          onKeyDown={(e) => { if (e.key === 'Enter' && e.metaKey) handleSubmit(); }}
        />
        <div className="mt-2.5 flex justify-end">
          <button
            type="button"
            onClick={handleSubmit}
            disabled={submitting || !prompt.trim()}
            className={`rounded-lg px-5 py-2 text-sm font-bold ${
              submitting || !prompt.trim() ? 'bg-surface-dim text-muted' : 'bg-signal text-white'
            }`}
          >
            {submitting ? 'Submitting…' : 'Submit request'}
          </button>
        </div>
      </Card>

      {error && <p className="mb-4 text-alert-red">{error}</p>}

      {loading ? (
        <Spinner label="Loading requests…" />
      ) : requests.length === 0 ? (
        <EmptyState title="No requests yet" description="Describe a feature above to get started." />
      ) : (
        <div className="flex flex-col gap-3">
          {requests.map((r) => (
            <Card key={r.id}>
              <div className="mb-2.5 flex items-start justify-between gap-3">
                <div>
                  {r.source === 'self_upgrade' && (
                    <div className="mb-1.5 font-mono text-[10.5px] font-bold uppercase tracking-wider text-alert-red">
                      🤖 self-upgrade{r.branch ? ` · ${r.branch}` : ''}
                    </div>
                  )}
                  {r.source === 'github_trending' && (
                    <div className="mb-1.5 font-mono text-[10.5px] font-bold uppercase tracking-wider text-signal">
                      🐙 from trending scan
                    </div>
                  )}
                  <p className="m-0 whitespace-pre-wrap text-sm leading-relaxed text-ink">
                    {r.prompt}
                  </p>
                </div>
                <StatusBadge status={r.status} />
              </div>

              <div className="flex flex-wrap items-center justify-between gap-2">
                <span className="font-mono text-xs text-muted">
                  {new Date(r.created_at).toLocaleString()}
                </span>
                <div className="flex gap-2">
                  {r.log.length > 0 && (
                    <button type="button" onClick={() => toggleExpanded(r.id)} className="rounded-md bg-surface-dim px-3 py-1 text-xs font-semibold text-ink-dim">
                      {expanded.has(r.id) ? 'Hide log' : 'Show log'}
                    </button>
                  )}
                  {r.status === 'error' && (
                    <button
                      type="button"
                      onClick={() => handleRetry(r)}
                      disabled={retryingId === r.id}
                      className="rounded-md bg-signal px-3 py-1 text-xs font-bold text-white disabled:opacity-60"
                    >
                      {retryingId === r.id ? 'Retrying…' : 'Try again'}
                    </button>
                  )}
                  {r.status !== 'running' && (
                    <button
                      type="button"
                      onClick={() => handleDelete(r.id)}
                      className="rounded-md border border-line bg-transparent px-3 py-1 text-xs font-semibold text-alert-red"
                    >
                      Delete
                    </button>
                  )}
                </div>
              </div>

              {r.summary && (
                <p className={`mt-2.5 text-sm ${r.status === 'error' ? 'text-alert-red' : 'text-ink-dim'}`}>
                  {r.summary}
                </p>
              )}

              {r.files_changed.length > 0 && (
                <div className="mt-2.5 flex flex-wrap gap-1.5">
                  {r.files_changed.map((f) => (
                    <span key={f} className="rounded-md bg-surface-dim px-2 py-0.5 font-mono text-xs text-alert-amber">
                      {f}
                    </span>
                  ))}
                </div>
              )}

              {expanded.has(r.id) && r.log.length > 0 && (
                <pre className="mt-3 max-h-80 overflow-y-auto overflow-x-auto whitespace-pre-wrap break-words rounded-lg border border-line bg-surface-dim p-3.5 font-mono text-xs leading-relaxed text-ink-dim">
                  {r.log.join('\n')}
                </pre>
              )}
            </Card>
          ))}
        </div>
      )}
    </div>
  );
};

export default Requests;
