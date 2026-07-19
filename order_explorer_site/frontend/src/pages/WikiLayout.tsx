import React, { useCallback, useEffect, useMemo, useState } from 'react';
import { Link, Outlet, useLocation, useParams, useSearchParams } from 'react-router-dom';
import { fetchChattyMemory } from '../chattyApi';
import type { WikiPage } from '../chattyApi';
import Badge from '../components/ui/Badge';
import Spinner from '../components/ui/Spinner';
import { WikiSidebarContext } from '../hooks/useWikiSidebar';

const WIKI_TYPE_LABELS: Record<WikiPage['type'], string> = {
  entity: 'Entities',
  concept: 'Concepts',
};

/** Persistent shell for the whole /memory section: a left-hand page-list
 * sidebar that stays mounted across the front page, articles, and the
 * health page, so navigating between wiki pages never requires clicking
 * back to "see the list again" - the list is always there. */
const WikiLayout: React.FC = () => {
  const location = useLocation();
  const { type: activeType, slug: activeSlug } = useParams<{ type: string; slug: string }>();
  const [searchParams] = useSearchParams();

  const [pages, setPages] = useState<WikiPage[] | null>(null);
  const [error, setError] = useState('');

  // days=1: the sidebar only needs .long_term from this response, so keep
  // the short_term slice this endpoint also returns as small as possible.
  const load = useCallback(async () => {
    try {
      const data = await fetchChattyMemory(1);
      setPages(data.long_term);
    } catch {
      setError('Failed to load page list.');
    }
  }, []);

  // Re-fetch on navigation (covers create/delete, which always navigate)
  // plus a shared refreshPages() in context for in-place edits (e.g. a
  // title/tag change on the current article) that don't change the route.
  useEffect(() => { load(); }, [load, location.pathname]);

  const selectedTag = searchParams.get('tag');

  const filteredPages = useMemo(
    () => (selectedTag ? (pages ?? []).filter((p) => p.tags.includes(selectedTag)) : pages ?? []),
    [pages, selectedTag],
  );

  const allTags = useMemo(
    () => Array.from(new Set((pages ?? []).flatMap((p) => p.tags))).sort(),
    [pages],
  );

  const pagesByType = (['entity', 'concept'] as const).map((type) => ({
    type,
    items: filteredPages.filter((p) => p.type === type),
  })).filter((group) => group.items.length > 0);

  const tagHref = (tag: string): string => {
    const params = new URLSearchParams();
    if (selectedTag !== tag) params.set('tag', tag);
    const qs = params.toString();
    return `/memory${qs ? `?${qs}` : ''}`;
  };

  return (
    <WikiSidebarContext.Provider value={{ refreshPages: load, pages: pages ?? [] }}>
      <div className="mx-auto flex max-w-[1400px] items-start gap-6 px-4 py-6 md:px-6">
        <aside data-testid="wiki-sidebar" className="sticky top-6 hidden w-56 shrink-0 flex-col gap-4 self-start md:flex">
          <nav className="flex flex-col gap-0.5">
            <p className="mb-1 font-mono text-[11px] font-semibold uppercase tracking-wider text-muted">Wiki</p>
            <Link
              to="/memory"
              className={`rounded-md px-2 py-1 text-sm font-semibold ${
                location.pathname === '/memory' ? 'bg-signal/15 text-signal' : 'text-ink hover:bg-surface-dim'
              }`}
            >
              Front page
            </Link>
            <Link
              to="/memory/health"
              className={`rounded-md px-2 py-1 text-sm font-semibold ${
                location.pathname === '/memory/health' ? 'bg-signal/15 text-signal' : 'text-ink hover:bg-surface-dim'
              }`}
            >
              Wiki Health
            </Link>
            <Link
              to="/memory/reorganize"
              className={`rounded-md px-2 py-1 text-sm font-semibold ${
                location.pathname === '/memory/reorganize' ? 'bg-signal/15 text-signal' : 'text-ink hover:bg-surface-dim'
              }`}
            >
              Reorganize
            </Link>
            <Link
              to="/memory"
              state={{ createPage: {} }}
              className="rounded-md px-2 py-1 text-sm font-semibold text-signal hover:bg-surface-dim"
            >
              + New page
            </Link>
          </nav>

          {allTags.length > 0 && (
            <div>
              <p className="mb-1.5 font-mono text-[11px] font-semibold uppercase tracking-wider text-muted">Tags</p>
              <div className="flex flex-wrap gap-1">
                {allTags.map((tag) => (
                  <Link key={tag} to={tagHref(tag)} className="transition-opacity hover:opacity-80">
                    <Badge tone={selectedTag === tag ? 'teal' : 'neutral'}>{tag}</Badge>
                  </Link>
                ))}
              </div>
            </div>
          )}

          <div className="min-h-0 flex-1 overflow-y-auto">
            {pages === null ? (
              <Spinner size="sm" label="Loading pages…" />
            ) : error ? (
              <p className="text-sm text-alert-red">{error}</p>
            ) : pagesByType.length === 0 ? (
              <p className="text-sm text-muted">No pages yet.</p>
            ) : (
              pagesByType.map(({ type, items }) => (
                <div key={type} className="mb-3">
                  <p className="mb-1 font-mono text-[11px] font-semibold uppercase tracking-wider text-muted">
                    {WIKI_TYPE_LABELS[type]} <span className="normal-case opacity-70">{items.length}</span>
                  </p>
                  <div className="flex flex-col gap-0.5">
                    {items.map((p) => {
                      const isActive = activeType === p.type && activeSlug === p.slug;
                      return (
                        <Link
                          key={`${p.type}/${p.slug}`}
                          to={`/memory/${p.type}/${p.slug}`}
                          title={p.title}
                          className={`truncate rounded-md px-2 py-1 text-sm ${
                            isActive ? 'bg-signal/15 font-semibold text-signal' : 'text-ink-dim hover:bg-surface-dim hover:text-ink'
                          }`}
                        >
                          {p.title}
                        </Link>
                      );
                    })}
                  </div>
                </div>
              ))
            )}
          </div>
        </aside>

        <div className="min-w-0 flex-1">
          <Outlet />
        </div>
      </div>
    </WikiSidebarContext.Provider>
  );
};

export default WikiLayout;
