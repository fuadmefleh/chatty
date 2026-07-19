import React, { useCallback, useEffect, useRef, useState } from 'react';
import {
  runTasteAudit,
  applyTasteFixes,
  getTasteFixStatus,
  type TasteAuditReport,
  type AuditFinding,
  type AuditSeverity,
  type TasteFixState,
} from '../chattyApi';
import PageHeader from '../components/ui/PageHeader';
import Card from '../components/ui/Card';
import Badge from '../components/ui/Badge';
import Spinner from '../components/ui/Spinner';

const FIX_POLL_MS = 1500;

// ── Helpers ─────────────────────────────────────────────────────────────────

const severityTone: Record<AuditSeverity, 'danger' | 'gold' | 'teal'> = {
  critical: 'danger',
  warning: 'gold',
  info: 'teal',
};

const severityDot: Record<AuditSeverity, string> = {
  critical: 'bg-alert-red',
  warning: 'bg-alert-amber',
  info: 'bg-signal',
};

const scoreTone = (score: number): 'danger' | 'gold' | 'teal' => {
  if (score >= 80) return 'teal';
  if (score >= 60) return 'gold';
  return 'danger';
};

const scoreBarColor = (score: number): string => {
  if (score >= 80) return 'bg-alert-green';
  if (score >= 60) return 'bg-alert-amber';
  return 'bg-alert-red';
};

// ── Sub-components ──────────────────────────────────────────────────────────

const ScoreRing: React.FC<{ score: number }> = ({ score }) => {
  const circumference = 2 * Math.PI * 36; // r=36
  const pct = Math.max(0, Math.min(100, score));
  const offset = circumference * (1 - pct / 100);
  const barColor = scoreBarColor(score);

  return (
    <div className="relative inline-flex h-24 w-24 items-center justify-center">
      <svg className="absolute h-24 w-24 -rotate-90" viewBox="0 0 80 80">
        <circle
          cx="40"
          cy="40"
          r="36"
          fill="none"
          stroke="var(--surface-dim)"
          strokeWidth="6"
        />
        <circle
          cx="40"
          cy="40"
          r="36"
          fill="none"
          className={barColor.replace('bg-', 'stroke-').replace('bg-', 'stroke-current')}
          stroke="currentColor"
          strokeWidth="6"
          strokeLinecap="round"
          strokeDasharray={circumference}
          strokeDashoffset={offset}
          style={{ color: undefined }}
        />
      </svg>
      <div className="text-center">
        <div className="text-[22px] font-bold text-ink">{score.toFixed(0)}</div>
        <div className="font-mono text-[9px] text-muted">/ 100</div>
      </div>
    </div>
  );
};

const SummaryBar: React.FC<{
  count: number;
  severity: AuditSeverity;
  label: string;
}> = ({ count, severity, label }) => (
  <div className="flex items-center gap-2">
    <span className={`inline-block h-2 w-2 rounded-full ${severityDot[severity]}`} />
    <span className="font-mono text-[13px] font-semibold text-ink">{count}</span>
    <span className="text-xs text-muted">{label}</span>
  </div>
);

const FindingRow: React.FC<{
  finding: AuditFinding;
  selected: boolean;
  onToggle: () => void;
}> = ({ finding, selected, onToggle }) => (
  <div
    className={`group flex items-start gap-3 rounded-lg border px-3 py-2.5 transition-colors ${
      selected
        ? 'border-signal/30 bg-signal/5'
        : 'border-transparent bg-surface-dim/50 hover:bg-surface-dim'
    }`}
  >
    <button
      onClick={onToggle}
      className={`mt-0.5 flex h-4 w-4 shrink-0 items-center justify-center rounded border ${
        selected
          ? 'border-signal bg-signal text-bg'
          : 'border-line bg-transparent'
      }`}
      aria-label={selected ? 'Deselect finding' : 'Select finding'}
    >
      {selected && (
        <svg className="h-2.5 w-2.5" viewBox="0 0 12 12" fill="none" stroke="currentColor" strokeWidth="2">
          <path d="M2 6l3 3 5-6" />
        </svg>
      )}
    </button>
    <div className="flex-1 min-w-0">
      <div className="flex flex-wrap items-center gap-2">
        <span className={`inline-block h-1.5 w-1.5 rounded-full ${severityDot[finding.severity]}`} />
        <span className="text-[13px] font-semibold text-ink">{finding.title}</span>
        <Badge tone={severityTone[finding.severity]}>{finding.severity}</Badge>
        {finding.fixable && (
          <span className="font-mono text-[10px] text-signal">fixable</span>
        )}
      </div>
      <div className="mt-0.5 flex items-center gap-2 text-xs text-muted">
        <span className="font-mono">{finding.file}:{finding.line}</span>
      </div>
      {finding.line_content && (
        <pre className="mt-1 overflow-x-auto rounded-md bg-surface-dim/60 px-2 py-1 font-mono text-[11px] leading-relaxed text-muted">
          {finding.line_content}
        </pre>
      )}
    </div>
  </div>
);

// ── Main Page ───────────────────────────────────────────────────────────────

const TasteAuditPage: React.FC = () => {
  const [report, setReport] = useState<TasteAuditReport | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [fixState, setFixState] = useState<TasteFixState | null>(null);
  const [selectedFindings, setSelectedFindings] = useState<Set<number>>(new Set());
  const [filterSeverity, setFilterSeverity] = useState<AuditSeverity | 'all'>('all');
  const [filterFile, setFilterFile] = useState<string>('');
  const pollRef = useRef<ReturnType<typeof setInterval> | null>(null);
  const prevFixStatusRef = useRef<TasteFixState['status'] | undefined>(undefined);

  const load = useCallback(async () => {
    setLoading(true);
    setError('');
    setSelectedFindings(new Set());
    try {
      const data = await runTasteAudit();
      setReport(data);
    } catch {
      setError('Failed to run taste audit');
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { load(); }, [load]);

  // Pick up an in-progress fix job on mount (e.g. the user navigated away
  // mid-fix and came back), so it isn't invisible on reload.
  useEffect(() => {
    getTasteFixStatus().then(setFixState).catch(() => {});
  }, []);

  // Poll while a fix job is running - this survives navigating away and
  // back, since the job itself runs server-side regardless of who's watching.
  const isFixing = fixState?.status === 'running';
  useEffect(() => {
    if (isFixing && !pollRef.current) {
      pollRef.current = setInterval(() => {
        getTasteFixStatus().then(setFixState).catch(() => {});
      }, FIX_POLL_MS);
    } else if (!isFixing && pollRef.current) {
      clearInterval(pollRef.current);
      pollRef.current = null;
    }
    return () => {
      if (pollRef.current) {
        clearInterval(pollRef.current);
        pollRef.current = null;
      }
    };
  }, [isFixing]);

  // Once a fix job finishes, refresh the audit report so applied fixes drop
  // off the findings list.
  useEffect(() => {
    if (prevFixStatusRef.current === 'running' && fixState?.status === 'done') {
      load();
    }
    prevFixStatusRef.current = fixState?.status;
  }, [fixState?.status, load]);

  const toggleFinding = (index: number) => {
    setSelectedFindings(prev => {
      const next = new Set(prev);
      if (next.has(index)) next.delete(index);
      else next.add(index);
      return next;
    });
  };

  const selectAllFiltered = () => {
    const filteredIndices = filteredFindings.map(f => f.index);
    setSelectedFindings(new Set(filteredIndices));
  };

  const clearSelection = () => setSelectedFindings(new Set());

  const applyFixes = async () => {
    if (!report) return;
    const selected = report.findings.filter((_, i) => selectedFindings.has(i));
    if (selected.length === 0) return;

    try {
      const started = await applyTasteFixes({
        findings: selected.map(f => ({
          file: f.file,
          line: f.line,
          rule_id: f.rule_id,
          fix: f.fix_suggestion ?? '',
        })),
      });
      setFixState(started);
    } catch (err) {
      setFixState({
        status: 'error',
        total: 0,
        completed: 0,
        current_file: null,
        applied: [],
        errors: [],
        summary: `Fix failed: ${err instanceof Error ? err.message : 'Unknown error'}`,
        updated_at: null,
      });
    }
  };

  // Derived data
  const filteredFindings = (report?.findings ?? []).map((f, i) => ({ ...f, index: i })).filter(f => {
    if (filterSeverity !== 'all' && f.severity !== filterSeverity) return false;
    if (filterFile && !f.file.includes(filterFile)) return false;
    return true;
  });

  const uniqueFiles = [...new Set((report?.findings ?? []).map(f => f.file))];
  const selectedFixableCount = report
    ? report.findings.filter((_, i) => selectedFindings.has(i) && report.findings[i].fixable).length
    : 0;

  return (
    <div className="mx-auto max-w-[1000px] px-4 pb-12 pt-6 md:px-6">
      <PageHeader
        eyebrow="Assistant / UI Quality"
        eyebrowColor="var(--signal)"
        title="UI Taste Auditor"
        actions={
          <>
            <button
              onClick={load}
              disabled={loading}
              className="rounded-md px-3 py-1 text-xs font-semibold disabled:opacity-50"
            >
              Re-scan
            </button>
            {report && (
              <span className="font-mono text-[11px] text-muted">
                {new Date(report.timestamp).toLocaleTimeString()}
              </span>
            )}
          </>
        }
      />

      {error && <p className="mb-4 text-sm text-alert-red">{error}</p>}
      {loading && !report && <Spinner label="Scanning frontend components…" />}

      {report && (
        <>
          {/* Score + Summary Row */}
          <div className="mb-6 flex flex-wrap items-center gap-6">
            <ScoreRing score={report.score} />
            <div className="flex flex-col gap-1.5">
              <SummaryBar
                count={report.summary.critical}
                severity="critical"
                label="critical"
              />
              <SummaryBar
                count={report.summary.warning}
                severity="warning"
                label="warnings"
              />
              <SummaryBar
                count={report.summary.info}
                severity="info"
                label="info"
              />
            </div>
            <div className="ml-auto font-mono text-[11px] text-muted">
              {report.files_scanned} files · {report.scan_duration_ms}ms
            </div>
          </div>

          {/* Score bar */}
          <Card padding="12px 18px" className="mb-6">
            <div className="mb-1 flex items-baseline justify-between">
              <span className="font-mono text-[11px] text-muted">Quality Score</span>
              <Badge tone={scoreTone(report.score)}>
                {report.score.toFixed(1)} / 100
              </Badge>
            </div>
            <div className="h-2 overflow-hidden rounded-full bg-surface-dim">
              <div
                className={`h-full rounded-full transition-[width] duration-500 ease-out ${scoreBarColor(report.score)}`}
                style={{ width: `${Math.max(0, Math.min(100, report.score))}%` }}
              />
            </div>
          </Card>

          {/* Filters + Actions Bar */}
          <div className="mb-3 flex flex-wrap items-center gap-2">
            {/* Severity filter */}
            <div className="flex rounded-md border border-line overflow-hidden">
              {(['all', 'critical', 'warning', 'info'] as const).map(s => (
                <button
                  key={s}
                  onClick={() => setFilterSeverity(s)}
                  className={`px-2.5 py-1 text-[11px] font-mono font-semibold transition-colors ${
                    filterSeverity === s
                      ? s === 'critical'
                        ? 'bg-alert-red/15 text-alert-red'
                        : s === 'warning'
                        ? 'bg-alert-amber/15 text-alert-amber'
                        : s === 'info'
                        ? 'bg-signal/15 text-signal'
                        : 'bg-surface-dim text-ink'
                      : 'text-muted hover:text-ink'
                  }`}
                >
                  {s === 'all' ? 'All' : s.charAt(0).toUpperCase() + s.slice(1)}
                </button>
              ))}
            </div>

            {/* File filter */}
            <select
              value={filterFile}
              onChange={e => setFilterFile(e.target.value)}
              className="rounded-md border border-line bg-surface px-2 py-1 text-[11px] font-mono text-ink"
            >
              <option value="">All files</option>
              {uniqueFiles.map(f => (
                <option key={f} value={f}>{f}</option>
              ))}
            </select>

            {/* Selection actions */}
            {filteredFindings.length > 0 && (
              <div className="ml-auto flex items-center gap-2">
                <button
                  onClick={selectAllFiltered}
                  className="font-mono text-[11px] text-muted hover:text-ink"
                >
                  Select all
                </button>
                <button
                  onClick={clearSelection}
                  className="font-mono text-[11px] text-muted hover:text-ink"
                >
                  Clear
                </button>
                <button
                  onClick={applyFixes}
                  disabled={selectedFixableCount === 0 || isFixing}
                  className="rounded-md bg-signal px-3 py-1 font-mono text-[11px] font-semibold text-bg disabled:opacity-40"
                >
                  {isFixing ? 'Fixing…' : `Fix selected (${selectedFixableCount})`}
                </button>
              </div>
            )}
          </div>

          {/* Fix progress / result */}
          {isFixing && (
            <Card padding="12px 18px" className="mb-4">
              <div className="mb-1.5 flex items-baseline justify-between">
                <span className="font-mono text-[11px] text-muted">
                  Fixing {fixState.completed} of {fixState.total} file{fixState.total === 1 ? '' : 's'}
                  {fixState.current_file ? ` — ${fixState.current_file}` : ''}
                </span>
                <span className="font-mono text-[11px] text-muted">
                  {fixState.total > 0 ? Math.round((fixState.completed / fixState.total) * 100) : 0}%
                </span>
              </div>
              <div className="h-2 overflow-hidden rounded-full bg-surface-dim">
                <div
                  className="h-full rounded-full bg-signal transition-[width] duration-300 ease-out"
                  style={{ width: `${fixState.total > 0 ? (fixState.completed / fixState.total) * 100 : 0}%` }}
                />
              </div>
              <p className="mt-2 text-xs text-muted">
                Running in the background — feel free to navigate away and check back later.
              </p>
            </Card>
          )}

          {!isFixing && fixState && (fixState.status === 'done' || fixState.status === 'error') && (
            <Card padding="12px 18px" className="mb-4" style={{ background: 'var(--surface-dim)' }}>
              <div className="font-mono text-[12px] text-ink">{fixState.summary}</div>
              {fixState.applied.length > 0 && (
                <ul className="mt-2 space-y-1">
                  {fixState.applied.map((c, i) => (
                    <li key={i} className="flex items-start gap-1.5 font-mono text-[11px] text-muted">
                      <span className="text-alert-green">✓</span>
                      <span>{c.file}:{c.line} ({c.rule_id})</span>
                    </li>
                  ))}
                </ul>
              )}
              {fixState.errors.length > 0 && (
                <ul className="mt-2 space-y-1">
                  {fixState.errors.map((e, i) => (
                    <li key={i} className="flex items-start gap-1.5 font-mono text-[11px] text-alert-red">
                      <span>✗</span>
                      <span>{e.file}{e.line ? `:${e.line}` : ''} — {e.error}</span>
                    </li>
                  ))}
                </ul>
              )}
            </Card>
          )}

          {/* Findings list */}
          <div className="space-y-1.5">
            {filteredFindings.length === 0 ? (
              <Card padding="24px">
                <p className="text-center text-muted">
                  {report.total_findings === 0
                    ? 'No findings — the codebase looks great!'
                    : 'No findings match the current filters.'}
                </p>
              </Card>
            ) : (
              filteredFindings.map(f => (
                <FindingRow
                  key={`${f.file}-${f.line}-${f.rule_id}`}
                  finding={f}
                  selected={selectedFindings.has(f.index)}
                  onToggle={() => toggleFinding(f.index)}
                />
              ))
            )}
          </div>

          {filteredFindings.length > 0 && (
            <div className="mt-3 text-center font-mono text-[11px] text-muted">
              Showing {filteredFindings.length} of {report.total_findings} findings
            </div>
          )}
        </>
      )}
    </div>
  );
};

export default TasteAuditPage;
