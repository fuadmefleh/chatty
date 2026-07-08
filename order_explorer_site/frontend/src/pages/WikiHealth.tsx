import React, { useEffect, useState } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { fetchWikiHealth, triggerWikiLint, resolveWikiContradiction } from '../chattyApi';
import type { WikiHealth as WikiHealthData, WikiHealthCoverageGap, WikiHealthContradiction } from '../chattyApi';
import PageHeader from '../components/ui/PageHeader';
import Spinner from '../components/ui/Spinner';
import EmptyState from '../components/ui/EmptyState';
import Card from '../components/ui/Card';
import Badge from '../components/ui/Badge';

const ContradictionCard: React.FC<{
  contradiction: WikiHealthContradiction;
  onDismiss: () => void;
}> = ({ contradiction, onDismiss }) => {
  const [guidance, setGuidance] = useState('');
  const [resolving, setResolving] = useState(false);
  const [response, setResponse] = useState('');
  const [error, setError] = useState('');

  const handleSend = async () => {
    if (!guidance.trim()) return;
    setResolving(true);
    setError('');
    try {
      setResponse(await resolveWikiContradiction(contradiction, guidance.trim()));
      setGuidance('');
    } catch {
      setError('Failed to send to Chatty.');
    } finally {
      setResolving(false);
    }
  };

  return (
    <Card>
      <p className="mb-2 flex flex-wrap items-center gap-2 text-sm font-semibold text-ink">
        <Link to={`/memory/${contradiction.page_a.type}/${contradiction.page_a.slug}`} className="text-signal hover:underline">{contradiction.page_a.title}</Link>
        <span className="text-muted">vs.</span>
        <Link to={`/memory/${contradiction.page_b.type}/${contradiction.page_b.slug}`} className="text-signal hover:underline">{contradiction.page_b.title}</Link>
      </p>
      <p className="mb-3 text-sm text-muted">{contradiction.description}</p>

      {response && (
        <div className="mb-3 rounded-lg border border-line bg-surface-dim px-3 py-2.5 text-sm text-ink">
          <p className="mb-1 flex items-center justify-between gap-2 font-mono text-[11px] font-semibold uppercase tracking-wider text-signal">
            Chatty
            <button type="button" onClick={onDismiss} className="normal-case text-muted hover:text-ink">
              Dismiss
            </button>
          </p>
          {response}
        </div>
      )}

      <div className="flex flex-col gap-2 sm:flex-row">
        <textarea
          value={guidance}
          onChange={(e) => setGuidance(e.target.value)}
          placeholder="Tell Chatty how to resolve this, e.g. &quot;There are only 2 children - fix Important Facts&quot;…"
          rows={2}
          disabled={resolving}
          className="w-full flex-1 resize-vertical rounded-lg border border-line bg-surface px-3 py-2 text-sm text-ink outline-none transition-colors focus:border-signal disabled:opacity-60"
        />
        <button
          type="button"
          onClick={handleSend}
          disabled={resolving || !guidance.trim()}
          className="h-9 shrink-0 self-start rounded-lg bg-signal px-4 text-sm font-bold text-white disabled:opacity-60 sm:self-end"
        >
          {resolving ? 'Sending…' : 'Send to Chatty'}
        </button>
      </div>
      {resolving && <p className="mt-2 text-xs text-muted">This runs Chatty's full tool loop and can take a couple of minutes.</p>}
      {error && <p className="mt-2 text-sm text-alert-red">{error}</p>}
    </Card>
  );
};

const WikiHealth: React.FC = () => {
  const navigate = useNavigate();
  const [health, setHealth] = useState<WikiHealthData | undefined>(undefined);
  const [error, setError] = useState('');
  const [linting, setLinting] = useState(false);

  const load = async () => {
    setError('');
    try {
      setHealth(await fetchWikiHealth());
    } catch {
      setError('Failed to load wiki health.');
    }
  };

  useEffect(() => { load(); }, []);

  const runLint = async () => {
    setLinting(true);
    try {
      await triggerWikiLint();
      await load();
    } catch {
      setError('Lint run failed.');
    } finally {
      setLinting(false);
    }
  };

  const createPageForGap = (gap: WikiHealthCoverageGap) => {
    navigate('/memory', { state: { createPage: { type: gap.suggested_type, title: gap.suggested_title } } });
  };

  const lintButton = (
    <button
      type="button"
      onClick={runLint}
      disabled={linting}
      className="rounded-md border border-line bg-surface-dim px-3 py-1 text-sm font-semibold text-ink disabled:opacity-50"
    >
      {linting ? 'Running lint…' : 'Run lint now'}
    </button>
  );

  return (
    <>
      <PageHeader eyebrow="Assistant / Memory" eyebrowColor="var(--signal)" title="Wiki Health" actions={lintButton} />

      {error && <p className="mb-4 text-sm text-alert-red">{error}</p>}

      {health === undefined ? (
        <Spinner label="Loading wiki health…" />
      ) : health.generated_at === null ? (
        <EmptyState
          title="Lint hasn't run yet"
          description="Trigger it below or wait for the next heartbeat (runs automatically every 15 minutes)."
          action={lintButton}
        />
      ) : (
        <div className="flex flex-col gap-6">
          <div className="flex flex-wrap items-center gap-2">
            <Badge tone="ember">{health.contradictions.length} contradiction{health.contradictions.length === 1 ? '' : 's'}</Badge>
            <Badge tone="gold">{health.coverage_gaps.length} coverage gap{health.coverage_gaps.length === 1 ? '' : 's'}</Badge>
            <Badge tone="neutral">{health.orphans.length} orphan{health.orphans.length === 1 ? '' : 's'}</Badge>
            <span className="ml-auto font-mono text-[11px] text-muted">
              Last checked: {new Date(health.generated_at).toLocaleString()} · {health.total_pages} page{health.total_pages === 1 ? '' : 's'}
            </span>
          </div>

          <section className="flex flex-col gap-2.5">
            <h2 className="text-xs font-semibold uppercase tracking-wide text-muted">Contradictions</h2>
            {health.contradictions.length === 0 ? (
              <p className="text-sm text-muted">No contradictions flagged.</p>
            ) : (
              health.contradictions.map((c, i) => (
                <ContradictionCard
                  key={i}
                  contradiction={c}
                  onDismiss={() => setHealth((h) => h && {
                    ...h,
                    contradictions: h.contradictions.filter((_, j) => j !== i),
                  })}
                />
              ))
            )}
          </section>

          <section className="flex flex-col gap-2.5">
            <h2 className="text-xs font-semibold uppercase tracking-wide text-muted">Coverage gaps</h2>
            {health.coverage_gaps.length === 0 ? (
              <p className="text-sm text-muted">No coverage gaps flagged.</p>
            ) : (
              health.coverage_gaps.map((g, i) => (
                <Card key={i}>
                  <div className="mb-2 flex flex-wrap items-center justify-between gap-2">
                    <p className="flex items-center gap-2 text-sm font-semibold text-ink">
                      {g.suggested_title}
                      <Badge tone="teal">{g.suggested_type}</Badge>
                    </p>
                    <button
                      type="button"
                      onClick={() => createPageForGap(g)}
                      className="rounded-md border border-line px-3 py-1 text-xs font-semibold text-ink-dim"
                    >
                      Create page
                    </button>
                  </div>
                  <p className="text-sm text-muted">{g.description}</p>
                </Card>
              ))
            )}
          </section>

          <section className="flex flex-col gap-2.5">
            <h2 className="text-xs font-semibold uppercase tracking-wide text-muted">Orphan pages</h2>
            {health.orphans.length === 0 ? (
              <p className="text-sm text-muted">No orphan pages - every page has at least one inbound link.</p>
            ) : (
              <div className="flex flex-col gap-2">
                {health.orphans.map((o) => (
                  <Link
                    key={`${o.type}/${o.slug}`}
                    to={`/memory/${o.type}/${o.slug}`}
                    className="flex items-center justify-between gap-3 rounded-lg border border-line bg-surface px-4 py-2.5 hover:bg-surface-dim"
                  >
                    <span className="font-semibold text-ink">{o.title}</span>
                    <Badge tone="neutral">{o.type}</Badge>
                  </Link>
                ))}
              </div>
            )}
          </section>
        </div>
      )}
    </>
  );
};

export default WikiHealth;
