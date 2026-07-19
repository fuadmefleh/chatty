import React, { useEffect, useMemo, useState } from 'react';
import { useParams, Link, useNavigate } from 'react-router-dom';
import { fetchWikiPage, fetchWikiBacklinks, updateWikiPage, deleteWikiPage } from '../chattyApi';
import type { WikiPage, WikiBacklink } from '../chattyApi';
import PageHeader from '../components/ui/PageHeader';
import Spinner from '../components/ui/Spinner';
import EmptyState from '../components/ui/EmptyState';
import Badge from '../components/ui/Badge';
import Card from '../components/ui/Card';
import Modal from '../components/ui/Modal';
import MarkdownContent from '../components/ui/MarkdownContent';
import WikiPageEditor from '../components/wiki/WikiPageEditor';
import MergeConfirmPanel from '../components/wiki/MergeConfirmPanel';
import { slugifyHeading } from '../lib/slugifyHeading';
import { useToast } from '../hooks/useToast';
import { useWikiSidebar } from '../hooks/useWikiSidebar';

interface TocEntry {
  level: 2 | 3;
  text: string;
  id: string;
}

const HEADING_RE = /^(#{2,3})\s+(.+)$/gm;

const parseToc = (body: string): TocEntry[] => {
  const entries: TocEntry[] = [];
  for (const match of body.matchAll(HEADING_RE)) {
    const level = match[1].length === 2 ? 2 : 3;
    const text = match[2].trim();
    entries.push({ level, text, id: slugifyHeading(text) });
  }
  return entries;
};

const WikiArticle: React.FC = () => {
  const { type, slug } = useParams<{ type: string; slug: string }>();
  const navigate = useNavigate();
  const { showToast } = useToast();
  const { refreshPages, pages } = useWikiSidebar();
  const [page, setPage] = useState<WikiPage | null | undefined>(undefined);
  const [error, setError] = useState('');
  const [backlinks, setBacklinks] = useState<WikiBacklink[] | null>(null);
  const [editing, setEditing] = useState(false);
  const [saving, setSaving] = useState(false);
  const [pendingDelete, setPendingDelete] = useState(false);
  const [deleting, setDeleting] = useState(false);
  const [merging, setMerging] = useState(false);
  const [mergeFilter, setMergeFilter] = useState('');
  const [mergeTarget, setMergeTarget] = useState<WikiPage | null>(null);

  useEffect(() => {
    if (!type || !slug) return;
    setPage(undefined);
    setError('');
    setBacklinks(null);
    setEditing(false);
    fetchWikiPage(type, slug)
      .then(setPage)
      .catch(() => setError('Failed to load this page.'));
    fetchWikiBacklinks(type, slug)
      .then(setBacklinks)
      .catch(() => setBacklinks([]));
  }, [type, slug]);

  const toc = useMemo(() => (page ? parseToc(page.body) : []), [page]);

  const handleSave = async (value: { title: string; summary: string; tags: string[]; body: string }) => {
    if (!type || !slug) return;
    setSaving(true);
    try {
      const updated = await updateWikiPage(type, slug, value);
      setPage(updated);
      setEditing(false);
      showToast('Page saved', 'signal');
      refreshPages();
    } catch {
      showToast('Failed to save page', 'red');
      throw new Error('save failed');
    } finally {
      setSaving(false);
    }
  };

  const confirmDelete = async () => {
    if (!type || !slug) return;
    setDeleting(true);
    try {
      await deleteWikiPage(type, slug);
      showToast('Page deleted', 'signal');
      navigate('/memory');
    } catch {
      showToast('Failed to delete page', 'red');
      setDeleting(false);
    }
  };

  const closeMerge = () => {
    setMerging(false);
    setMergeTarget(null);
    setMergeFilter('');
  };

  const mergeCandidates = useMemo(() => {
    if (!type || !slug) return [];
    const term = mergeFilter.trim().toLowerCase();
    return pages
      .filter((p) => !(p.type === type && p.slug === slug))
      .filter((p) => !term || p.title.toLowerCase().includes(term))
      .slice(0, 20);
  }, [pages, type, slug, mergeFilter]);

  const handleMerged: React.ComponentProps<typeof MergeConfirmPanel>['onMerged'] = (kept, removed) => {
    if (!type || !slug) return;
    closeMerge();
    if (removed.type === type && removed.slug === slug) {
      showToast(`Merged into "${kept.title}"`, 'signal');
      navigate(`/memory/${kept.type}/${kept.slug}`);
    } else {
      setPage(kept);
      refreshPages();
      showToast(`Merged "${removed.title}" into this page`, 'signal');
    }
  };

  if (page === undefined) {
    if (error) {
      return <EmptyState title="Something went wrong" description={error} />;
    }
    return <Spinner label="Loading article…" />;
  }

  if (page === null) {
    return (
      <EmptyState
        title="Page not found"
        description={`No wiki page found for ${type}/${slug}.`}
      />
    );
  }

  return (
    <>
      <div className="mb-6 border-b border-line pb-5">
        <PageHeader
          eyebrow="Assistant / Memory"
          eyebrowColor="var(--signal)"
          title={page.title}
          titleClassName="font-serif text-4xl"
          actions={
            !editing && (
              <div className="flex items-center gap-2">
                <button
                  type="button"
                  onClick={() => setEditing(true)}
                  className="rounded-md border border-line px-3 py-1 text-xs font-semibold text-ink-dim"
                >
                  Edit
                </button>
                <button
                  type="button"
                  onClick={() => setMerging(true)}
                  className="rounded-md border border-line px-3 py-1 text-xs font-semibold text-ink-dim"
                >
                  Merge…
                </button>
                <button
                  type="button"
                  onClick={() => setPendingDelete(true)}
                  className="rounded-md border border-line px-3 py-1 text-xs font-semibold text-alert-red"
                >
                  Delete
                </button>
              </div>
            )
          }
        />
        {page.summary && <p className="-mt-5 mb-4 italic text-muted">{page.summary}</p>}
        <div className="flex flex-wrap items-center gap-2">
          <Badge tone="teal">{page.type}</Badge>
          {page.tags.map((tag) => (
            <Link
              key={tag}
              to={`/memory?tag=${encodeURIComponent(tag)}`}
              className="transition-opacity hover:opacity-80"
            >
              <Badge tone="neutral">{tag}</Badge>
            </Link>
          ))}
          <span className="ml-auto font-mono text-[11px] text-muted">
            Last updated: {new Date(page.updated).toLocaleString()}
          </span>
        </div>
      </div>

      {editing ? (
        <WikiPageEditor
          mode="edit"
          initial={{ type: page.type, slug: page.slug, title: page.title, summary: page.summary, tags: page.tags, body: page.body }}
          onSave={handleSave}
          onCancel={() => setEditing(false)}
          saving={saving}
        />
      ) : (
        <div className="flex flex-col gap-8 md:flex-row md:items-start">
          <div className="min-w-0 flex-1">
            <MarkdownContent content={page.body} anchorHeadings />
          </div>

          <div className="flex w-full shrink-0 flex-col gap-4 md:w-64">
            {toc.length >= 2 && (
              <Card padding={16}>
                <p className="mb-2 font-mono text-[11px] font-semibold uppercase tracking-wider text-muted">
                  Contents
                </p>
                <ol className="flex flex-col gap-1.5 text-sm">
                  {toc.map((entry, i) => (
                    <li key={entry.id} className={entry.level === 3 ? 'ml-3' : ''}>
                      <a href={`#${entry.id}`} className="text-signal hover:underline">
                        {i + 1}. {entry.text}
                      </a>
                    </li>
                  ))}
                </ol>
              </Card>
            )}

            <Card padding={16}>
              <p className="mb-2 font-mono text-[11px] font-semibold uppercase tracking-wider text-muted">
                What links here
              </p>
              {backlinks === null ? (
                <Spinner label="Loading…" />
              ) : backlinks.length === 0 ? (
                <p className="text-sm text-muted">No pages link here yet.</p>
              ) : (
                <ul className="flex flex-col gap-1.5 text-sm">
                  {backlinks.map((b) => (
                    <li key={`${b.type}/${b.slug}`}>
                      <Link to={`/memory/${b.type}/${b.slug}`} className="text-signal hover:underline">
                        {b.title}
                      </Link>
                    </li>
                  ))}
                </ul>
              )}
            </Card>
          </div>
        </div>
      )}

      <Modal open={pendingDelete} onClose={() => setPendingDelete(false)} title="Delete this page?">
        <p className="mb-4 text-sm text-ink-dim">This will permanently remove "{page.title}" from long-term memory.</p>
        <div className="flex justify-end gap-2">
          <button
            onClick={() => setPendingDelete(false)}
            disabled={deleting}
            className="h-9 rounded-lg border border-line px-4 text-sm font-medium text-ink-dim"
          >
            Cancel
          </button>
          <button
            onClick={confirmDelete}
            disabled={deleting}
            className="h-9 rounded-lg bg-alert-red px-4 text-sm font-semibold text-white disabled:opacity-60"
          >
            {deleting ? 'Deleting…' : 'Delete'}
          </button>
        </div>
      </Modal>

      <Modal open={merging} onClose={closeMerge} title={mergeTarget ? 'Confirm merge' : 'Merge into another page'}>
        {mergeTarget ? (
          <>
            <button
              type="button"
              onClick={() => setMergeTarget(null)}
              className="mb-3 text-xs font-semibold text-signal hover:underline"
            >
              ← Choose a different page
            </button>
            <MergeConfirmPanel
              pageA={{ type: page.type, slug: page.slug, title: page.title }}
              pageB={{ type: mergeTarget.type, slug: mergeTarget.slug, title: mergeTarget.title }}
              defaultKeep="b"
              onCancel={closeMerge}
              onMerged={handleMerged}
            />
          </>
        ) : (
          <div className="flex flex-col gap-3">
            <input
              type="text"
              value={mergeFilter}
              onChange={(e) => setMergeFilter(e.target.value)}
              placeholder="Search pages by title…"
              autoFocus
              className="w-full rounded-lg border border-line bg-surface px-3.5 py-2.5 text-sm text-ink outline-none transition-colors focus:border-signal"
            />
            <div className="flex max-h-72 flex-col gap-1 overflow-y-auto">
              {mergeCandidates.length === 0 ? (
                <p className="text-sm text-muted">No matching pages.</p>
              ) : (
                mergeCandidates.map((p) => (
                  <button
                    key={`${p.type}/${p.slug}`}
                    type="button"
                    onClick={() => setMergeTarget(p)}
                    className="flex flex-col gap-0.5 rounded-lg border border-line px-3 py-2 text-left hover:bg-surface-dim"
                  >
                    <span className="flex items-center gap-2 text-sm font-semibold text-ink">
                      {p.title}
                      <Badge tone="neutral">{p.type}</Badge>
                    </span>
                    {p.summary && <span className="truncate text-xs text-muted">{p.summary}</span>}
                  </button>
                ))
              )}
            </div>
            <div className="flex justify-end">
              <button
                type="button"
                onClick={closeMerge}
                className="h-9 rounded-lg border border-line px-4 text-sm font-medium text-ink-dim"
              >
                Cancel
              </button>
            </div>
          </div>
        )}
      </Modal>
    </>
  );
};

export default WikiArticle;
