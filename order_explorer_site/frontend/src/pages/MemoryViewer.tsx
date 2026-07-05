import React, { useEffect, useState } from 'react';
import { fetchChattyMemory, searchChattyMemory, triggerMemoryConsolidation } from '../chattyApi';
import type { MemoryData, MemoryEntry } from '../chattyApi';
import PageHeader from '../components/ui/PageHeader';
import Spinner from '../components/ui/Spinner';
import EmptyState from '../components/ui/EmptyState';
import MarkdownContent from '../components/ui/MarkdownContent';

const ChevronIcon: React.FC<{ open: boolean }> = ({ open }) => (
  <svg
    viewBox="0 0 24 24"
    fill="none"
    stroke="currentColor"
    strokeWidth={2}
    strokeLinecap="round"
    strokeLinejoin="round"
    className={`h-3.5 w-3.5 shrink-0 transition-transform ${open ? 'rotate-90' : ''}`}
  >
    <path d="m9 6 6 6-6 6" />
  </svg>
);

const MemoryViewer: React.FC = () => {
  const [data, setData] = useState<MemoryData | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [days, setDays] = useState(7);
  const [activeTab, setActiveTab] = useState<'short_term' | 'long_term'>('short_term');
  const [openDates, setOpenDates] = useState<Set<string>>(new Set());

  const [query, setQuery] = useState('');
  const [searching, setSearching] = useState(false);
  const [searchResults, setSearchResults] = useState<string | null>(null);

  const [consolidating, setConsolidating] = useState(false);
  const [consolidateStatus, setConsolidateStatus] = useState('');

  const load = async (d: number) => {
    setLoading(true);
    setError('');
    try {
      setData(await fetchChattyMemory(d));
    } catch {
      setError('Failed to load memory');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => { load(days); }, [days]);

  const runSearch = async () => {
    if (!query.trim()) return;
    setSearching(true);
    try {
      setSearchResults(await searchChattyMemory(query.trim()));
    } catch {
      setSearchResults('Search failed.');
    } finally {
      setSearching(false);
    }
  };

  const runConsolidate = async () => {
    setConsolidating(true);
    setConsolidateStatus('');
    try {
      setConsolidateStatus(await triggerMemoryConsolidation());
      await load(days);
    } catch {
      setConsolidateStatus('Consolidation failed.');
    } finally {
      setConsolidating(false);
    }
  };

  const toggleDate = (date: string) => {
    setOpenDates((prev) => {
      const next = new Set(prev);
      if (next.has(date)) next.delete(date);
      else next.add(date);
      return next;
    });
  };

  const entries: MemoryEntry[] = data ? data[activeTab] : [];

  return (
    <div className="mx-auto max-w-[900px] px-4 py-6 md:px-6">
      <PageHeader
        eyebrow="Assistant / Memory"
        eyebrowColor="var(--signal)"
        title="Memory"
        actions={
          <div className="flex flex-wrap items-center gap-2 text-sm text-muted">
            <input
              type="text"
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              onKeyDown={(e) => { if (e.key === 'Enter') runSearch(); }}
              placeholder="Search memory…"
              className="rounded-md border border-line bg-surface px-2 py-1 text-sm text-ink"
            />
            <button
              type="button"
              onClick={runSearch}
              disabled={searching || !query.trim()}
              className="rounded-md border border-line bg-surface-dim px-3 py-1 text-sm font-semibold text-ink disabled:opacity-50"
            >
              {searching ? 'Searching…' : 'Search'}
            </button>
            <button
              type="button"
              onClick={runConsolidate}
              disabled={consolidating}
              className="rounded-md border border-line bg-surface-dim px-3 py-1 text-sm font-semibold text-ink disabled:opacity-50"
            >
              {consolidating ? 'Consolidating…' : 'Consolidate now'}
            </button>
            <label htmlFor="days-select">Last</label>
            <select
              id="days-select"
              value={days}
              onChange={(e) => setDays(Number(e.target.value))}
              className="rounded-md border border-line bg-surface px-2 py-1 text-sm text-ink"
            >
              {[3, 7, 14, 30, 60, 90].map((d) => (
                <option key={d} value={d}>{d} days</option>
              ))}
            </select>
          </div>
        }
      />

      {consolidateStatus && (
        <p className="mb-4 text-sm text-muted">{consolidateStatus}</p>
      )}

      {searchResults !== null && (
        <div className="mb-5 overflow-hidden rounded-lg border border-line">
          <div className="flex items-center justify-between gap-2 bg-surface-dim px-4 py-2.5">
            <span className="text-sm font-semibold text-ink">Search results</span>
            <button
              type="button"
              onClick={() => setSearchResults(null)}
              className="text-xs text-signal"
            >
              dismiss
            </button>
          </div>
          <div className="overflow-x-auto border-t border-line bg-bg px-5 py-4">
            <MarkdownContent content={searchResults || 'No matches found.'} />
          </div>
        </div>
      )}

      {/* Tabs */}
      <div className="mb-5 flex gap-1">
        {(['short_term', 'long_term'] as const).map((tab) => (
          <button
            key={tab}
            type="button"
            onClick={() => setActiveTab(tab)}
            className={`rounded-lg px-4 py-1.5 text-sm font-semibold ${
              activeTab === tab
                ? 'bg-signal text-white'
                : 'border border-line bg-surface-dim text-muted'
            }`}
          >
            {tab === 'short_term' ? 'Short-term' : 'Long-term'}
            {data && (
              <span className="ml-1.5 font-mono text-[11px] opacity-80">
                {data[tab].length}
              </span>
            )}
          </button>
        ))}
      </div>

      {error && <p className="mb-4 text-sm text-alert-red">{error}</p>}
      {loading ? (
        <Spinner label="Loading memory…" />
      ) : entries.length === 0 ? (
        <EmptyState
          title="No memory entries"
          description={`No ${activeTab.replace('_', '-')} memory entries found for this period.`}
        />
      ) : (
        <div className="flex flex-col gap-2">
          {entries.map((entry) => {
            const isOpen = openDates.has(entry.date);
            return (
              <div key={entry.filename} className="overflow-hidden rounded-lg border border-line">
                {/* Accordion header */}
                <button
                  type="button"
                  onClick={() => toggleDate(entry.date)}
                  aria-expanded={isOpen}
                  className={`flex w-full items-center justify-between gap-2 rounded-none px-4 py-2.5 text-left font-mono text-sm font-semibold text-ink ${
                    isOpen ? 'bg-surface-dim' : 'bg-surface'
                  }`}
                >
                  <span>{entry.date}</span>
                  <span className="flex items-center gap-1 text-xs text-signal">
                    {isOpen ? 'collapse' : 'expand'}
                    <ChevronIcon open={isOpen} />
                  </span>
                </button>
                {/* Content */}
                {isOpen && (
                  <div className="overflow-x-auto border-t border-line bg-bg px-5 py-4">
                    <MarkdownContent content={entry.content} />
                  </div>
                )}
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
};

export default MemoryViewer;
