import React, { useCallback, useEffect, useState } from 'react';
import { BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer, CartesianGrid, LineChart, Line, Legend } from 'recharts';
import { fetchTokenUsageSummary, fetchTokenUsageRecent } from '../chattyApi';
import type { TokenUsageSummary, TokenUsageEntry } from '../chattyApi';
import PageHeader from '../components/ui/PageHeader';
import Card from '../components/ui/Card';
import StatCard from '../components/ui/StatCard';
import Badge from '../components/ui/Badge';
import Spinner from '../components/ui/Spinner';
import EmptyState from '../components/ui/EmptyState';
import ResponsiveTable from '../components/ui/ResponsiveTable';
import type { TableColumn } from '../components/ui/ResponsiveTable';

// Light-mode hex equivalents of the design tokens, for recharts (SVG props don't read CSS vars reliably).
const CHART_GRID = '#dfe3e1';
const CHART_AXIS = { fontSize: 12, fill: '#6b7478' };
const CHART_TOOLTIP_STYLE = { background: '#ffffff', border: '1px solid #dfe3e1', borderRadius: 8, color: '#12181b' };
const CHART_AMBER = '#a8631f';
const CHART_SIGNAL = '#1e6e64';

const sectionTitle = 'mb-4 font-mono text-[13px] uppercase tracking-wider text-muted';
const RANGE_OPTIONS = [7, 30, 90] as const;

const fmtTokens = (n: number): string => n.toLocaleString();
const fmtCost = (n: number | null): string => (n === null ? '—' : `$${n < 0.01 && n > 0 ? n.toFixed(4) : n.toFixed(2)}`);
const firstLine = (text: string): string => text.split('\n', 1)[0];
const fmtDay = (day: string): string => new Date(`${day}T00:00:00Z`).toLocaleDateString(undefined, { month: 'short', day: 'numeric' });

const TokenUsagePage: React.FC = () => {
  const [days, setDays] = useState<number>(30);
  const [summary, setSummary] = useState<TokenUsageSummary | null>(null);
  const [recent, setRecent] = useState<TokenUsageEntry[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(false);

  const load = useCallback(async (range: number) => {
    setLoading(true);
    setError(false);
    try {
      const [summaryData, recentData] = await Promise.all([
        fetchTokenUsageSummary(range),
        fetchTokenUsageRecent(50),
      ]);
      setSummary(summaryData);
      setRecent(recentData);
    } catch {
      setError(true);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { load(days); }, [days, load]);

  const recentColumns: TableColumn<TokenUsageEntry>[] = [
    {
      key: 'timestamp', header: 'Time', primary: true,
      render: (e) => <span className="font-mono text-[13px]">{new Date(e.timestamp).toLocaleString()}</span>,
    },
    { key: 'provider', header: 'Provider', render: (e) => <Badge tone="gold">{e.provider}</Badge> },
    { key: 'model', header: 'Model', render: (e) => <span className="font-mono text-xs text-ink-dim">{e.model}</span> },
    {
      key: 'prompt_preview', header: 'Prompt', className: 'max-w-[280px]',
      render: (e) => (
        e.prompt_preview
          ? (
            <span className="flex items-baseline gap-1.5">
              <span className="font-mono text-[11px] uppercase tracking-wide text-muted">{e.prompt_role}</span>
              <span className="block truncate text-xs text-ink-dim">{firstLine(e.prompt_preview)}</span>
            </span>
          )
          : <span className="text-xs text-muted">—</span>
      ),
    },
    { key: 'prompt', header: 'Prompt', className: 'text-right', render: (e) => <span className="font-mono text-xs text-muted">{fmtTokens(e.prompt_tokens)}</span> },
    { key: 'completion', header: 'Completion', className: 'text-right', render: (e) => <span className="font-mono text-xs text-muted">{fmtTokens(e.completion_tokens)}</span> },
    { key: 'total', header: 'Total', className: 'text-right', render: (e) => <span className="font-mono font-bold">{fmtTokens(e.total_tokens)}</span> },
  ];

  return (
    <div className="mx-auto max-w-[1100px] px-4 pb-12 pt-6 md:px-6">
      <PageHeader
        eyebrow="Assistant / Token Usage"
        eyebrowColor="var(--signal)"
        title="Token Usage"
        actions={
          <div className="flex gap-1.5">
            {RANGE_OPTIONS.map((r) => (
              <button
                key={r}
                onClick={() => setDays(r)}
                className={`rounded-md px-3 py-1 text-xs font-semibold ${
                  days === r ? 'bg-signal text-bg' : 'bg-surface-dim text-ink-dim'
                }`}
              >
                {r}d
              </button>
            ))}
          </div>
        }
      />

      {loading && !summary && <Spinner label="Loading token usage…" />}
      {error && !summary && (
        <EmptyState title="Failed to load token usage" description="Something went wrong fetching usage data. Try refreshing the page." />
      )}

      {summary && (
        <>
          {/* Summary Cards */}
          <div className="mb-7 grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
            <StatCard label="Today" value={fmtTokens(summary.today_total_tokens)} detail={`${summary.today_request_count} requests`} tone="signal" />
            <StatCard
              label={`Last ${summary.range_days}d`}
              value={fmtTokens(summary.total_tokens)}
              detail={`${summary.request_count} requests`}
              tone="neutral"
            />
            <StatCard
              label="Prompt / Completion"
              value={`${fmtTokens(summary.total_prompt_tokens)} / ${fmtTokens(summary.total_completion_tokens)}`}
              tone="neutral"
            />
            <StatCard
              label="Estimated cost"
              value={fmtCost(summary.total_estimated_cost_usd)}
              detail={summary.unpriced_model_count > 0 ? `excludes ${summary.unpriced_model_count} unpriced model(s)` : `last ${summary.range_days}d`}
              tone="amber"
            />
          </div>

          {/* Usage over time */}
          <Card className="mb-7">
            <h2 className={sectionTitle}>Tokens per day</h2>
            {summary.by_day.length === 0 ? (
              <EmptyState title="No usage recorded yet" description="Token usage will appear here once the assistant makes LLM calls." />
            ) : (
              <div className="h-[300px]">
                <ResponsiveContainer width="100%" height="100%">
                  <LineChart data={summary.by_day.map((d) => ({ ...d, day: fmtDay(d.day) }))}>
                    <CartesianGrid strokeDasharray="3 3" stroke={CHART_GRID} />
                    <XAxis dataKey="day" tick={CHART_AXIS} />
                    <YAxis tick={CHART_AXIS} />
                    <Tooltip formatter={(value: unknown) => fmtTokens(Number(value))} contentStyle={CHART_TOOLTIP_STYLE} />
                    <Legend wrapperStyle={{ fontSize: 12 }} />
                    <Line type="monotone" dataKey="prompt_tokens" name="Prompt" stroke={CHART_SIGNAL} strokeWidth={2} dot={{ r: 2 }} />
                    <Line type="monotone" dataKey="completion_tokens" name="Completion" stroke={CHART_AMBER} strokeWidth={2} dot={{ r: 2 }} />
                  </LineChart>
                </ResponsiveContainer>
              </div>
            )}
          </Card>

          <div className="mb-7 grid grid-cols-1 gap-5 lg:grid-cols-2">
            {/* By model */}
            <Card>
              <h2 className={sectionTitle}>By model</h2>
              {summary.by_model.length === 0 ? (
                <EmptyState title="No usage recorded yet" />
              ) : (
                <div className="flex max-h-[380px] flex-col gap-2 overflow-y-auto">
                  {summary.by_model.map((m, idx) => (
                    <div key={idx} className="rounded-lg border border-line bg-bg px-3.5 py-2.5">
                      <div className="flex items-center justify-between">
                        <div>
                          <p className="m-0 font-mono text-sm font-semibold text-ink">{m.model}</p>
                          <p className="mt-1 text-xs text-muted">
                            {m.provider} · {m.request_count} requests · {fmtCost(m.estimated_cost_usd)}
                          </p>
                        </div>
                        <Badge tone="teal">{fmtTokens(m.total_tokens)}</Badge>
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </Card>

            {/* By model bar chart */}
            <Card>
              <h2 className={sectionTitle}>Total tokens by model</h2>
              {summary.by_model.length === 0 ? (
                <EmptyState title="No usage recorded yet" />
              ) : (
                <div className="h-[350px]">
                  <ResponsiveContainer width="100%" height="100%">
                    <BarChart data={summary.by_model} layout="vertical">
                      <CartesianGrid strokeDasharray="3 3" stroke={CHART_GRID} />
                      <XAxis type="number" tick={CHART_AXIS} />
                      <YAxis dataKey="model" type="category" width={140} tick={CHART_AXIS} />
                      <Tooltip formatter={(value: unknown) => fmtTokens(Number(value))} contentStyle={CHART_TOOLTIP_STYLE} />
                      <Bar dataKey="total_tokens" fill={CHART_SIGNAL} radius={[0, 4, 4, 0]} />
                    </BarChart>
                  </ResponsiveContainer>
                </div>
              )}
            </Card>
          </div>

          {/* Recent requests */}
          <Card>
            <h2 className={sectionTitle}>Recent requests</h2>
            <ResponsiveTable
              columns={recentColumns}
              rows={recent}
              rowKey={(e) => `${e.timestamp}-${e.model}`}
              expandedContent={(e) => (
                e.prompt_preview
                  ? (
                    <div>
                      <p className="mb-2 font-mono text-[11px] uppercase tracking-wider text-muted">
                        {e.prompt_role} · final message sent to the model
                      </p>
                      <pre className="m-0 max-h-[320px] overflow-auto whitespace-pre-wrap break-words rounded-lg border border-line bg-bg px-3 py-2.5 font-mono text-xs text-ink-dim">
                        {e.prompt_preview}
                      </pre>
                    </div>
                  )
                  : <p className="m-0 text-xs text-muted">No prompt recorded for this request.</p>
              )}
              emptyTitle="No requests logged yet"
            />
          </Card>
        </>
      )}
    </div>
  );
};

export default TokenUsagePage;
