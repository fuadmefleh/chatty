import React, { useEffect, useMemo, useState } from 'react';
import { useParams, Link } from 'react-router-dom';
import { fetchWikiPage } from '../chattyApi';
import type { WikiPage } from '../chattyApi';
import PageHeader from '../components/ui/PageHeader';
import Spinner from '../components/ui/Spinner';
import EmptyState from '../components/ui/EmptyState';
import Badge from '../components/ui/Badge';
import MarkdownContent from '../components/ui/MarkdownContent';
import { slugifyHeading } from '../lib/slugifyHeading';

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
  const [page, setPage] = useState<WikiPage | null | undefined>(undefined);
  const [error, setError] = useState('');

  useEffect(() => {
    if (!type || !slug) return;
    setPage(undefined);
    setError('');
    fetchWikiPage(type, slug)
      .then(setPage)
      .catch(() => setError('Failed to load this page.'));
  }, [type, slug]);

  const toc = useMemo(() => (page ? parseToc(page.body) : []), [page]);

  if (page === undefined) {
    if (error) {
      return (
        <div className="mx-auto max-w-[1100px] px-4 py-6 md:px-6">
          <Link to="/memory" className="mb-4 inline-block text-sm font-medium text-signal">
            ← Back to memory
          </Link>
          <EmptyState title="Something went wrong" description={error} />
        </div>
      );
    }
    return (
      <div className="mx-auto max-w-[1100px] px-4 py-6 md:px-6">
        <Spinner label="Loading article…" />
      </div>
    );
  }

  if (page === null) {
    return (
      <div className="mx-auto max-w-[1100px] px-4 py-6 md:px-6">
        <Link to="/memory" className="mb-4 inline-block text-sm font-medium text-signal">
          ← Back to memory
        </Link>
        <EmptyState
          title="Page not found"
          description={`No wiki page found for ${type}/${slug}.`}
        />
      </div>
    );
  }

  return (
    <div className="mx-auto max-w-[1100px] px-4 py-6 md:px-6">
      <Link to="/memory" className="mb-4 inline-block text-sm font-medium text-signal">
        ← Back to memory
      </Link>

      <div className="mb-6 border-b border-line pb-5">
        <PageHeader eyebrow="Assistant / Memory" eyebrowColor="var(--signal)" title={page.title} titleClassName="font-serif text-4xl" />
        {page.summary && <p className="-mt-5 mb-4 italic text-muted">{page.summary}</p>}
        <div className="flex flex-wrap items-center gap-2">
          <Badge tone="teal">{page.type}</Badge>
          {page.tags.map((tag) => (
            <Badge key={tag} tone="neutral">{tag}</Badge>
          ))}
          <span className="ml-auto font-mono text-[11px] text-muted">
            Last updated: {page.updated}
          </span>
        </div>
      </div>

      <div className="flex flex-col gap-8 md:flex-row md:items-start">
        <div className="min-w-0 flex-1">
          <MarkdownContent content={page.body} anchorHeadings />
        </div>

        {toc.length >= 2 && (
          <aside className="w-full shrink-0 rounded-lg border border-line bg-surface-dim p-4 md:w-64">
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
          </aside>
        )}
      </div>
    </div>
  );
};

export default WikiArticle;
