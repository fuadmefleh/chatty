import React, { useCallback, useEffect, useRef, useState } from 'react';
import { Link } from 'react-router-dom';
import { getReorganizeStatus, proposeWikiReorganization, applyWikiReorganization } from '../chattyApi';
import type { ReorganizeState } from '../chattyApi';
import PageHeader from '../components/ui/PageHeader';
import Spinner from '../components/ui/Spinner';
import EmptyState from '../components/ui/EmptyState';
import Card from '../components/ui/Card';
import Badge from '../components/ui/Badge';
import { useToast } from '../hooks/useToast';
import { useWikiSidebar } from '../hooks/useWikiSidebar';

const POLL_MS = 3000;

const pageKey = (t: { type: string; slug: string }): string => `${t.type}/${t.slug}`;

const sourceRefLabel = (ref: string): string => {
  const [, slug] = ref.split('/');
  return slug ? slug.replace(/-/g, ' ') : ref;
};

const sourceRefHref = (ref: string): string => {
  const [typeDir, slug] = ref.split('/');
  const type = typeDir === 'entities' || typeDir === 'entity' ? 'entity' : 'concept';
  return `/memory/${type}/${slug}`;
};

const WikiReorganize: React.FC = () => {
  const { showToast } = useToast();
  const { refreshPages } = useWikiSidebar();

  const [state, setState] = useState<ReorganizeState | null>(null);
  const [loading, setLoading] = useState(true);
  const [loadError, setLoadError] = useState('');
  const [selected, setSelected] = useState<Set<number>>(new Set());
  const pollRef = useRef<ReturnType<typeof setInterval> | null>(null);
  const lastProposalKeyRef = useRef<string>('');

  const applyIncoming = useCallback((next: ReorganizeState) => {
    setState(next);
    // A fresh proposal (new target_pages) starts fully selected, minus
    // anything already applied from it; re-fetching the same proposal
    // (e.g. on page reload) doesn't clobber whatever's still selected.
    const proposalKey = JSON.stringify(next.target_pages);
    if (next.status === 'proposed' && proposalKey !== lastProposalKeyRef.current) {
      lastProposalKeyRef.current = proposalKey;
      const appliedSet = new Set(next.applied_keys);
      setSelected(
        new Set(
          (next.target_pages || [])
            .map((t, i) => [i, t] as const)
            .filter(([, t]) => !appliedSet.has(pageKey(t)))
            .map(([i]) => i),
        ),
      );
    }
  }, []);

  const load = useCallback(async () => {
    try {
      const data = await getReorganizeStatus();
      applyIncoming(data);
      setLoadError('');
    } catch {
      setLoadError('Failed to load reorganization status.');
    } finally {
      setLoading(false);
    }
  }, [applyIncoming]);

  useEffect(() => {
    load();
  }, [load]);

  // Poll while a job is running - this survives navigating away and back,
  // since the job itself runs server-side regardless of who's watching.
  const isActive = state?.status === 'proposing' || state?.status === 'applying';
  useEffect(() => {
    if (isActive && !pollRef.current) {
      pollRef.current = setInterval(load, POLL_MS);
    } else if (!isActive && pollRef.current) {
      clearInterval(pollRef.current);
      pollRef.current = null;
    }
    return () => {
      if (pollRef.current) {
        clearInterval(pollRef.current);
        pollRef.current = null;
      }
    };
  }, [isActive, load]);

  const runPropose = async () => {
    try {
      const next = await proposeWikiReorganization();
      applyIncoming(next);
    } catch {
      setLoadError('Failed to start a reorganization proposal.');
    }
  };

  const toggleSelected = (i: number) => {
    setSelected((prev) => {
      const next = new Set(prev);
      if (next.has(i)) next.delete(i);
      else next.add(i);
      return next;
    });
  };

  const runApply = async () => {
    if (!state?.target_pages) return;
    const chosen = state.target_pages.filter((_, i) => selected.has(i));
    if (chosen.length === 0) return;
    try {
      const next = await applyWikiReorganization(chosen);
      applyIncoming(next);
      showToast('Applying in the background - come back anytime to check progress', 'signal');
    } catch {
      setLoadError('Failed to start applying the reorganization.');
    }
  };

  // Once an apply finishes, refresh the sidebar/wiki once so newly-written
  // pages show up without a manual reload.
  const prevStatusRef = useRef<ReorganizeState['status'] | undefined>(undefined);
  useEffect(() => {
    if (prevStatusRef.current === 'applying' && state?.status === 'applied') {
      refreshPages();
      showToast('Reorganization applied', 'signal');
    } else if (prevStatusRef.current === 'applying' && state?.status === 'apply_error') {
      showToast('Reorganization failed', 'red');
    }
    prevStatusRef.current = state?.status;
  }, [state?.status, refreshPages, showToast]);

  const proposeButton = (
    <button
      type="button"
      onClick={runPropose}
      disabled={state?.status === 'proposing'}
      className="rounded-md border border-line bg-surface-dim px-3 py-1 text-sm font-semibold text-ink disabled:opacity-50"
    >
      {state?.status === 'proposing' ? 'Analyzing wiki…' : state?.target_pages ? 'Re-propose' : 'Propose reorganization'}
    </button>
  );

  const targetPages = state?.target_pages ?? null;
  const appliedSet = new Set(state?.applied_keys ?? []);

  return (
    <>
      <PageHeader
        eyebrow="Assistant / Memory"
        eyebrowColor="var(--signal)"
        title="Reorganize Wiki"
        actions={proposeButton}
      />

      <p className="mb-5 max-w-[65ch] text-sm text-ink-dim">
        Splits lumped pages (e.g. a single "Relationships" page) into dedicated pages per person, child,
        or place. Chatty drafts the new pages from your existing content - nothing is deleted, so you can
        compare old and new and remove the stale lumped pages yourself once you're satisfied. Both steps
        run in the background - feel free to leave this page and check back later.
      </p>

      {loadError && <p className="mb-4 text-sm text-alert-red">{loadError}</p>}
      {state?.status === 'propose_error' && state.error && (
        <p className="mb-4 text-sm text-alert-red">Proposal failed: {state.error}</p>
      )}

      {loading ? (
        <Spinner label="Loading…" />
      ) : state?.status === 'proposing' ? (
        <div className="flex flex-col items-start gap-2">
          <Spinner label="Analyzing the wiki for a better page structure…" />
          <p className="text-xs text-muted">
            Usually well under a minute, but can take longer on a large wiki or under load. This runs on
            the server - feel free to navigate away; come back anytime and this page will show the result.
          </p>
        </div>
      ) : targetPages === null ? (
        <EmptyState
          title="No proposal yet"
          description="Click &quot;Propose reorganization&quot; to have Chatty suggest a more granular page structure."
          action={proposeButton}
        />
      ) : targetPages.length === 0 ? (
        <EmptyState title="Already well-structured" description="Chatty didn't find any lumped pages worth splitting." />
      ) : (
        <div className="flex flex-col gap-4">
          <div className="flex flex-col gap-2.5">
            {targetPages.map((t, i) => {
              const applied = appliedSet.has(pageKey(t));
              return (
                <Card key={`${t.type}/${t.slug}/${i}`}>
                  <label className={`flex items-start gap-3 ${applied ? '' : 'cursor-pointer'}`}>
                    <input
                      type="checkbox"
                      checked={applied || selected.has(i)}
                      disabled={applied}
                      onChange={() => toggleSelected(i)}
                      className="mt-1 h-4 w-4 shrink-0 accent-signal disabled:opacity-50"
                    />
                    <div className="min-w-0 flex-1">
                      <p className="mb-1 flex flex-wrap items-center gap-2 text-sm font-semibold text-ink">
                        {t.title}
                        <Badge tone="teal">{t.type}</Badge>
                        {applied && <Badge tone="teal">applied</Badge>}
                        {!applied && t.already_exists && <Badge tone="gold">will update existing page</Badge>}
                      </p>
                      {t.summary && <p className="mb-2 text-sm text-muted">{t.summary}</p>}
                      {t.source_pages.length > 0 && (
                        <p className="flex flex-wrap items-center gap-1.5 text-xs text-muted">
                          Draws from:
                          {t.source_pages.map((ref) => (
                            <Link key={ref} to={sourceRefHref(ref)} className="text-signal hover:underline">
                              {sourceRefLabel(ref)}
                            </Link>
                          ))}
                        </p>
                      )}
                    </div>
                  </label>
                </Card>
              );
            })}
          </div>

          {state?.status === 'apply_error' && state.error && (
            <div className="rounded-lg border border-alert-red/40 bg-surface-dim px-3 py-2.5 text-sm text-alert-red">
              Apply failed: {state.error}
            </div>
          )}
          {state?.status === 'applied' && state.apply_result && (
            <div className="rounded-lg border border-line bg-surface-dim px-3 py-2.5 text-sm text-ink">
              {state.apply_result}
            </div>
          )}

          <div className="flex items-center gap-3">
            <button
              type="button"
              onClick={runApply}
              disabled={state?.status === 'applying' || selected.size === 0}
              className="h-9 rounded-lg bg-signal px-4 text-sm font-bold text-white disabled:opacity-60"
            >
              {state?.status === 'applying' ? 'Applying…' : `Apply ${selected.size} selected page${selected.size === 1 ? '' : 's'}`}
            </button>
            {state?.status === 'applying' && (
              <span className="text-xs text-muted">
                Running in the background - feel free to navigate away and check back later.
              </span>
            )}
          </div>
        </div>
      )}
    </>
  );
};

export default WikiReorganize;
