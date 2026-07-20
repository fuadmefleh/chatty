import React, { useEffect, useState } from 'react';
import {
  fetchWatchlist,
  createWatchTopic,
  deleteWatchTopic,
  fetchInsights,
  deleteInsight,
  startScan,
  fetchScanJob,
} from '../chattyApi';
import type {
  ChattyWatchTopic,
  ChattyInsight,
  WatchTopicKind,
  InsightRelation,
  ScanJob,
  ScanJobStatus,
  StartScanRequest,
} from '../chattyApi';
import PageHeader from '../components/ui/PageHeader';
import Card from '../components/ui/Card';
import Spinner from '../components/ui/Spinner';
import EmptyState from '../components/ui/EmptyState';

const formatLastRun = (lastRunAt: string | null): string => {
  if (!lastRunAt) return 'not yet checked';
  return `checked ${new Date(lastRunAt).toLocaleString()}`;
};

const RELATION_LABELS: Record<InsightRelation, string> = {
  follows_up: 'Follows up on',
  contradicts: 'Contradicts',
  escalates: 'Escalates',
};

const SIGNIFICANCE_LABELS: Record<number, string> = {
  2: 'minor',
  3: 'notable',
  4: 'significant',
  5: 'major',
};

// Tier 4+ is what earns a chat notification, so it's also what opens expanded.
const isHighSignificance = (insight: ChattyInsight): boolean => (insight.significance ?? 3) >= 4;

// Records written before structured insights only carry a flat `summary`.
const isStructured = (insight: ChattyInsight): boolean => Boolean(insight.headline);

const SignificanceMeter: React.FC<{ value: number }> = ({ value }) => (
  <span
    className="flex items-center gap-1"
    title={`Significance ${value}/5 — ${SIGNIFICANCE_LABELS[value] ?? 'unrated'}`}
  >
    {[1, 2, 3, 4, 5].map((n) => (
      <span
        key={n}
        className={`h-1.5 w-1.5 rounded-full ${
          n <= value ? (value >= 4 ? 'bg-signal' : 'bg-muted') : 'bg-line'
        }`}
      />
    ))}
  </span>
);

const Section: React.FC<{ label: string; children: React.ReactNode }> = ({ label, children }) => (
  <div className="mb-3">
    <div className="mb-1 font-mono text-[10.5px] uppercase tracking-wider text-muted">{label}</div>
    <div className="text-[14px] leading-relaxed text-ink">{children}</div>
  </div>
);

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

const SEARCH_PLACEHOLDERS: Record<WatchTopicKind, string> = {
  news: 'Search now, without watching…',
  stock: 'Ticker symbol, e.g. TSLA',
  github: 'owner/repo, e.g. anthropics/claude-code',
};

const POLL_INTERVAL_MS = 2000;

const isTerminal = (status: ScanJobStatus): boolean => status === 'done' || status === 'failed';

// What each per-target outcome should read as in the progress panel. These
// mirror world_watch.SCAN_STATES, plus "error" for an unexpected exception.
const TARGET_STATE_LABELS: Record<string, string> = {
  pending: 'queued',
  stored: 'new insight',
  nothing_new: 'nothing new',
  below_threshold: 'nothing significant',
  fetch_failed: 'source unavailable',
  analysis_failed: 'analysis failed',
  error: 'failed',
};

const TARGET_STATE_COLORS: Record<string, string> = {
  stored: 'text-signal',
  fetch_failed: 'text-alert-red',
  analysis_failed: 'text-alert-red',
  error: 'text-alert-red',
};

const Insights: React.FC = () => {
  const [topics, setTopics] = useState<ChattyWatchTopic[]>([]);
  const [insights, setInsights] = useState<ChattyInsight[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [newTopic, setNewTopic] = useState('');
  const [newKind, setNewKind] = useState<WatchTopicKind>('news');
  const [saving, setSaving] = useState(false);
  const [topicFilter, setTopicFilter] = useState<string | null>(null);
  // Only holds explicit user toggles; the default open/closed state comes from
  // significance, so an untouched card follows its tier.
  const [toggled, setToggled] = useState<Record<string, boolean>>({});
  const [searchTopic, setSearchTopic] = useState('');
  const [searchKind, setSearchKind] = useState<WatchTopicKind>('news');
  const [scanJob, setScanJob] = useState<ScanJob | null>(null);
  // One-off search results are kept out of the curated feed until asked for.
  const [showAdHoc, setShowAdHoc] = useState(false);

  const scanning = scanJob !== null && !isTerminal(scanJob.status);

  const isExpanded = (insight: ChattyInsight): boolean =>
    toggled[insight.id] ?? (isHighSignificance(insight) || !isStructured(insight));

  const toggleExpanded = (insight: ChattyInsight) =>
    setToggled((prev) => ({ ...prev, [insight.id]: !isExpanded(insight) }));

  const insightTopics = Array.from(new Set(insights.map((i) => i.topic)));
  const visibleInsights = topicFilter ? insights.filter((i) => i.topic === topicFilter) : insights;
  const insightsById = new Map(insights.map((i) => [i.id, i]));

  const load = async (includeAdHoc: boolean) => {
    setLoading(true);
    try {
      const [t, i] = await Promise.all([fetchWatchlist(), fetchInsights(50, 1, includeAdHoc)]);
      setTopics(t);
      setInsights(i);
    } catch {
      setError('Failed to load insights');
    } finally {
      setLoading(false);
    }
  };

  // Covers the initial mount as well as every flip of the ad-hoc toggle.
  useEffect(() => { load(showAdHoc); }, [showAdHoc]);

  const handleScanComplete = (job: ScanJob) => {
    // A finished ad-hoc search must reveal its own result, or the spinner
    // resolves into an unchanged feed and reads as a failure.
    if (job.mode === 'adhoc' && !showAdHoc) {
      setShowAdHoc(true);  // the effect above refetches
    } else {
      load(showAdHoc);
    }
  };

  useEffect(() => {
    if (scanJob === null || isTerminal(scanJob.status)) return;

    let cancelled = false;
    const timer = setTimeout(async () => {
      try {
        const updated = await fetchScanJob(scanJob.id);
        if (cancelled) return;
        setScanJob(updated);
        if (isTerminal(updated.status)) handleScanComplete(updated);
      } catch {
        // A 404 means chatty-web-server restarted and lost the in-memory job.
        // The insight may well have been written first, so refetch rather
        // than reporting an error.
        if (cancelled) return;
        setScanJob(null);
        load(showAdHoc);
      }
    }, POLL_INTERVAL_MS);

    return () => { cancelled = true; clearTimeout(timer); };
  }, [scanJob, showAdHoc]);

  const beginScan = async (req: StartScanRequest) => {
    if (scanning) return;
    setError('');
    try {
      const { job_id } = await startScan(req);
      setScanJob(await fetchScanJob(job_id));
    } catch (e: unknown) {
      const status = (e as { response?: { status?: number } })?.response?.status;
      setError(status === 409 ? 'A scan is already running' : 'Failed to start scan');
    }
  };

  const handleSearch = () => {
    const topic = searchTopic.trim();
    if (!topic) return;
    beginScan({ mode: 'adhoc', topic, kind: searchKind });
  };

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
    <div className="mx-auto max-w-[760px] px-4 pb-12 pt-6 md:px-6">
      <PageHeader eyebrow="Assistant / Insights" eyebrowColor="var(--signal)" title="Insights" />

      {error && <p className="mb-4 text-sm text-alert-red">{error}</p>}

      {/* Ad-hoc search - runs the pipeline without adding to the watchlist */}
      <Card className="mb-4">
        <div className="mb-3 text-[13px] font-bold text-ink">Search now</div>
        <div className="flex flex-col gap-2 sm:flex-row">
          <select
            value={searchKind}
            onChange={(e) => setSearchKind(e.target.value as WatchTopicKind)}
            disabled={scanning}
            className="rounded-lg border border-line bg-bg px-2.5 py-2 text-[13.5px] text-ink outline-none disabled:opacity-50"
          >
            <option value="news">News</option>
            <option value="stock">Stock</option>
            <option value="github">GitHub repo</option>
          </select>
          <input
            type="text"
            placeholder={SEARCH_PLACEHOLDERS[searchKind]}
            value={searchTopic}
            onChange={(e) => setSearchTopic(e.target.value)}
            onKeyDown={(e) => { if (e.key === 'Enter') handleSearch(); }}
            disabled={scanning}
            className="flex-1 rounded-lg border border-line bg-bg px-3 py-2 text-sm text-ink outline-none disabled:opacity-50"
          />
          <button
            onClick={handleSearch}
            disabled={scanning || !searchTopic.trim()}
            className={`rounded-lg px-4.5 py-2 text-[13px] font-bold ${
              scanning || !searchTopic.trim() ? 'bg-surface-dim text-muted' : 'bg-signal text-bg'
            }`}
          >
            {scanning ? 'Scanning…' : 'Search'}
          </button>
        </div>
        <div className="mt-2 font-mono text-[11.5px] text-muted">
          One-off — doesn’t add to your watchlist.
        </div>
      </Card>

      {/* Live scan progress */}
      {scanJob && (
        <Card className="mb-4">
          <div className="mb-2.5 flex items-center gap-2">
            {scanning && <Spinner size="sm" label="" />}
            <span className="text-[13px] font-bold text-ink">
              {scanning ? 'Scanning…' : scanJob.status === 'failed' ? 'Scan failed' : 'Scan complete'}
            </span>
            {!scanning && (
              <button
                onClick={() => setScanJob(null)}
                className="ml-auto rounded-md border border-line bg-transparent px-2.5 py-0.5 text-[11.5px] font-semibold text-muted"
              >
                Dismiss
              </button>
            )}
          </div>
          <div className="flex flex-col gap-1">
            {scanJob.targets.map((target) => (
              <div key={`${target.topic}-${target.kind}`} className="flex items-center justify-between gap-3">
                <span className="text-[13px] text-ink">
                  {target.topic}
                  <span className="ml-2 font-mono text-[10.5px] uppercase tracking-wider text-muted">
                    {KIND_LABELS[target.kind] ?? target.kind}
                  </span>
                </span>
                <span
                  className={`font-mono text-[11.5px] ${TARGET_STATE_COLORS[target.state] ?? 'text-muted'}`}
                  title={target.error ?? undefined}
                >
                  {TARGET_STATE_LABELS[target.state] ?? target.state}
                </span>
              </div>
            ))}
          </div>
          {scanJob.error && (
            <div className="mt-2 text-[12.5px] text-alert-red">{scanJob.error}</div>
          )}
        </Card>
      )}

      {/* Watchlist management */}
      <Card className="mb-7">
        <div className="mb-3 flex items-center justify-between gap-3">
          <span className="text-[13px] font-bold text-ink">Watched topics</span>
          {topics.length > 0 && (
            <button
              onClick={() => beginScan({ mode: 'all' })}
              disabled={scanning}
              className="rounded-md border border-line bg-transparent px-3 py-1 text-xs font-semibold text-muted disabled:opacity-50"
            >
              Scan all
            </button>
          )}
        </div>
        <div className={`flex flex-col gap-2 sm:flex-row ${topics.length ? 'mb-3.5' : ''}`}>
          <select
            value={newKind}
            onChange={(e) => setNewKind(e.target.value as WatchTopicKind)}
            className="rounded-lg border border-line bg-bg px-2.5 py-2 text-[13.5px] text-ink outline-none"
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
            className="flex-1 rounded-lg border border-line bg-bg px-3 py-2 text-sm text-ink outline-none"
          />
          <button
            onClick={handleAddTopic}
            disabled={saving || !newTopic.trim()}
            className={`rounded-lg px-4.5 py-2 text-[13px] font-bold ${
              saving || !newTopic.trim()
                ? 'bg-surface-dim text-muted'
                : 'bg-signal text-bg'
            }`}
          >
            {saving ? 'Saving…' : '+ Watch'}
          </button>
        </div>
        {topics.length > 0 && (
          <div className="flex flex-col gap-2">
            {topics.map((topic) => (
              <div
                key={topic.id}
                className="flex items-center justify-between rounded-lg bg-surface-dim px-3 py-2"
              >
                <div>
                  <div className="text-sm text-ink">
                    {topic.topic}
                    <span className="ml-2 font-mono text-[10.5px] uppercase tracking-wider text-muted">
                      {KIND_LABELS[topic.kind] ?? topic.kind}
                    </span>
                  </div>
                  <div className="font-mono text-[11.5px] text-muted">
                    {formatLastRun(topic.last_run_at)}
                  </div>
                </div>
                <div className="flex shrink-0 items-center gap-1.5">
                  <button
                    onClick={() => beginScan({ mode: 'topic', topic_id: topic.id })}
                    disabled={scanning}
                    title="Check this topic now, ignoring its schedule"
                    className="rounded-md border border-line bg-transparent px-3 py-1 text-xs font-semibold text-signal disabled:opacity-50"
                  >
                    Scan
                  </button>
                  <button
                    onClick={() => handleRemoveTopic(topic.id)}
                    className="rounded-md border border-line bg-transparent px-3 py-1 text-xs font-semibold text-alert-red"
                  >
                    Remove
                  </button>
                </div>
              </div>
            ))}
          </div>
        )}
      </Card>

      {/* Insight feed */}
      {!loading && (insightTopics.length > 1 || showAdHoc) && (
        <div className="mb-3.5 flex flex-wrap items-center gap-1.5">
          {insightTopics.length > 1 &&
            [null, ...insightTopics].map((topic) => (
              <button
                key={topic ?? '__all__'}
                onClick={() => setTopicFilter(topic)}
                className={`rounded-full px-3 py-1 text-[12px] font-semibold ${
                  topicFilter === topic
                    ? 'bg-signal text-bg'
                    : 'border border-line bg-transparent text-muted'
                }`}
              >
                {topic ?? 'All'}
              </button>
            ))}
          <button
            onClick={() => setShowAdHoc((prev) => !prev)}
            title="One-off search results are hidden from the curated feed by default"
            className={`ml-auto rounded-full px-3 py-1 text-[12px] font-semibold ${
              showAdHoc ? 'bg-signal text-bg' : 'border border-line bg-transparent text-muted'
            }`}
          >
            {showAdHoc ? '✓ Searches' : 'Show searches'}
          </button>
        </div>
      )}

      {loading ? (
        <Spinner label="Loading insights…" />
      ) : insights.length === 0 ? (
        <EmptyState
          title="No insights yet"
          description="Watched topics are checked periodically in the background — or search above to look something up now."
        />
      ) : (
        <div className="flex flex-col gap-3">
          {visibleInsights.map((insight) => {
            const expanded = isExpanded(insight);
            const priorHeadline = insight.connection
              ? insightsById.get(insight.connection.prior_insight_id)?.headline
              : undefined;

            return (
              <Card key={insight.id}>
                <div className="mb-2 flex items-start justify-between gap-3">
                  <div className="flex items-center gap-2">
                    <span className="font-mono text-[11px] uppercase tracking-wider text-signal">
                      {insight.topic}
                    </span>
                    {insight.ad_hoc && (
                      <span
                        title="From a one-off search, not your watchlist"
                        className="rounded-md bg-surface-dim px-1.5 py-0.5 font-mono text-[10px] uppercase tracking-wider text-muted"
                      >
                        search
                      </span>
                    )}
                    {insight.significance != null && <SignificanceMeter value={insight.significance} />}
                  </div>
                  <button
                    onClick={() => handleDeleteInsight(insight.id)}
                    className="shrink-0 rounded-md border border-line bg-transparent px-3 py-1 text-xs font-semibold text-alert-red"
                  >
                    Delete
                  </button>
                </div>

                {isStructured(insight) ? (
                  <>
                    <button
                      onClick={() => toggleExpanded(insight)}
                      className="mb-3 block w-full cursor-pointer border-0 bg-transparent p-0 text-left text-[15.5px] font-bold leading-snug text-ink"
                    >
                      {insight.headline}
                      {!expanded && <span className="ml-2 text-[12px] font-normal text-muted">show more</span>}
                    </button>

                    {expanded && (
                      <>
                        {insight.what_happened && (
                          <Section label="What happened">{insight.what_happened}</Section>
                        )}
                        {insight.why_it_matters && (
                          <Section label="Why it matters">{insight.why_it_matters}</Section>
                        )}
                        {insight.connection && (
                          <Section label={RELATION_LABELS[insight.connection.relation] ?? 'Related to'}>
                            {priorHeadline && (
                              <div className="mb-1 text-[13px] italic text-muted">“{priorHeadline}”</div>
                            )}
                            {insight.connection.note}
                          </Section>
                        )}
                        {(insight.what_to_watch?.length ?? 0) > 0 && (
                          <Section label="What to watch">
                            <ul className="m-0 list-disc pl-5">
                              {insight.what_to_watch!.map((item) => (
                                <li key={item}>{item}</li>
                              ))}
                            </ul>
                          </Section>
                        )}
                        {(insight.entities?.length ?? 0) > 0 && (
                          <div className="mb-3 flex flex-wrap gap-1.5">
                            {insight.entities!.map((entity) => (
                              <span
                                key={entity}
                                className="rounded-md bg-surface-dim px-2 py-0.5 text-[11.5px] text-muted"
                              >
                                {entity}
                              </span>
                            ))}
                          </div>
                        )}
                      </>
                    )}
                  </>
                ) : (
                  <p className="mb-3 whitespace-pre-wrap text-[14.5px] leading-relaxed text-ink">
                    {insight.summary}
                  </p>
                )}

                {expanded && insight.sources.length > 0 && (
                  <div className="mb-2.5 flex flex-col gap-1">
                    {insight.sources.map((source) => (
                      <a
                        key={source.url}
                        href={source.url}
                        target="_blank"
                        rel="noreferrer"
                        className="text-[12.5px] text-alert-amber no-underline"
                      >
                        {source.title}
                      </a>
                    ))}
                  </div>
                )}

                <span className="font-mono text-xs text-muted">
                  {new Date(insight.created_at).toLocaleString()}
                </span>
              </Card>
            );
          })}
        </div>
      )}
    </div>
  );
};

export default Insights;
