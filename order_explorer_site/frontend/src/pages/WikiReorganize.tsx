import React, { useState } from 'react';
import { Link } from 'react-router-dom';
import { proposeWikiReorganization, applyWikiReorganization } from '../chattyApi';
import type { ReorganizeTargetPage } from '../chattyApi';
import PageHeader from '../components/ui/PageHeader';
import Spinner from '../components/ui/Spinner';
import EmptyState from '../components/ui/EmptyState';
import Card from '../components/ui/Card';
import Badge from '../components/ui/Badge';
import { useToast } from '../hooks/useToast';
import { useWikiSidebar } from '../hooks/useWikiSidebar';

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

  const [proposing, setProposing] = useState(false);
  const [proposeError, setProposeError] = useState('');
  const [targetPages, setTargetPages] = useState<ReorganizeTargetPage[] | null>(null);
  const [selected, setSelected] = useState<Set<number>>(new Set());

  const [applying, setApplying] = useState(false);
  const [applyResult, setApplyResult] = useState('');

  const runPropose = async () => {
    setProposing(true);
    setProposeError('');
    setApplyResult('');
    try {
      const proposal = await proposeWikiReorganization();
      if (proposal.error) {
        setProposeError(proposal.error);
        setTargetPages(null);
      } else {
        setTargetPages(proposal.target_pages);
        setSelected(new Set(proposal.target_pages.map((_, i) => i)));
      }
    } catch {
      setProposeError('Failed to propose a reorganization.');
    } finally {
      setProposing(false);
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
    if (!targetPages) return;
    const chosen = targetPages.filter((_, i) => selected.has(i));
    if (chosen.length === 0) return;
    setApplying(true);
    setApplyResult('');
    try {
      const result = await applyWikiReorganization(chosen);
      setApplyResult(result);
      showToast('Reorganization applied', 'signal');
      refreshPages();
    } catch {
      setApplyResult('Reorganization failed.');
      showToast('Reorganization failed', 'red');
    } finally {
      setApplying(false);
    }
  };

  const proposeButton = (
    <button
      type="button"
      onClick={runPropose}
      disabled={proposing}
      className="rounded-md border border-line bg-surface-dim px-3 py-1 text-sm font-semibold text-ink disabled:opacity-50"
    >
      {proposing ? 'Analyzing wiki…' : targetPages ? 'Re-propose' : 'Propose reorganization'}
    </button>
  );

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
        compare old and new and remove the stale lumped pages yourself once you're satisfied.
      </p>

      {proposeError && <p className="mb-4 text-sm text-alert-red">{proposeError}</p>}

      {proposing ? (
        <div className="flex flex-col items-start gap-2">
          <Spinner label="Analyzing the wiki for a better page structure…" />
          <p className="text-xs text-muted">
            Usually well under a minute, but can take longer on a large wiki or under load. Stay on this
            page - navigating away loses this request; nothing is saved until you review and apply below.
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
            {targetPages.map((t, i) => (
              <Card key={`${t.type}/${t.slug}/${i}`}>
                <label className="flex cursor-pointer items-start gap-3">
                  <input
                    type="checkbox"
                    checked={selected.has(i)}
                    onChange={() => toggleSelected(i)}
                    className="mt-1 h-4 w-4 shrink-0 accent-signal"
                  />
                  <div className="min-w-0 flex-1">
                    <p className="mb-1 flex flex-wrap items-center gap-2 text-sm font-semibold text-ink">
                      {t.title}
                      <Badge tone="teal">{t.type}</Badge>
                      {t.already_exists && <Badge tone="gold">will update existing page</Badge>}
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
            ))}
          </div>

          {applyResult && (
            <div className="rounded-lg border border-line bg-surface-dim px-3 py-2.5 text-sm text-ink">
              {applyResult}
            </div>
          )}

          <div className="flex items-center gap-3">
            <button
              type="button"
              onClick={runApply}
              disabled={applying || selected.size === 0}
              className="h-9 rounded-lg bg-signal px-4 text-sm font-bold text-white disabled:opacity-60"
            >
              {applying ? 'Applying…' : `Apply ${selected.size} selected page${selected.size === 1 ? '' : 's'}`}
            </button>
            {applying && <span className="text-xs text-muted">This can take a little while - one LLM call drafting all selected pages.</span>}
          </div>
        </div>
      )}
    </>
  );
};

export default WikiReorganize;
