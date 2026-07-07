import React, { useEffect, useState, useCallback } from 'react';
import { fetchServerHealth, fetchStorageBreakdown } from '../chattyApi';
import type { ServerHealth, HealthGPU, StorageBreakdown } from '../chattyApi';
import PageHeader from '../components/ui/PageHeader';
import Card from '../components/ui/Card';
import Badge from '../components/ui/Badge';
import Spinner from '../components/ui/Spinner';
import PulseDot from '../components/ui/PulseDot';

// ── Helpers ─────────────────────────────────────────────────────────────────
const fmtBytes = (b: number): string => {
  if (b >= 1024 ** 3) return `${(b / 1024 ** 3).toFixed(1)} GB`;
  if (b >= 1024 ** 2) return `${(b / 1024 ** 2).toFixed(1)} MB`;
  return `${b} B`;
};

const fmtMiB = (m: number): string => `${m} MiB`;

const fmtUptime = (seconds: number): string => {
  const d = Math.floor(seconds / 86400);
  const h = Math.floor((seconds % 86400) / 3600);
  const m = Math.floor((seconds % 3600) / 60);
  const parts: string[] = [];
  if (d > 0) parts.push(`${d}d`);
  if (h > 0) parts.push(`${h}h`);
  parts.push(`${m}m`);
  return parts.join(' ');
};

// Tone for a percentage — green→amber→red
type PctTone = 'green' | 'amber' | 'red';
const pctTone = (pct: number): PctTone => (pct < 60 ? 'green' : pct < 85 ? 'amber' : 'red');
const barColorClass: Record<PctTone, string> = {
  green: 'bg-alert-green',
  amber: 'bg-alert-amber',
  red: 'bg-alert-red',
};
const pctTextClass: Record<PctTone, string> = {
  green: 'text-alert-green',
  amber: 'text-alert-amber',
  red: 'text-alert-red',
};
// Historically low-usage reads as a calm "teal" badge, mid as gold, high as danger.
const badgeToneForPct = (pct: number): 'teal' | 'gold' | 'danger' => {
  const t = pctTone(pct);
  return t === 'green' ? 'teal' : t === 'amber' ? 'gold' : 'danger';
};

// ── Sub-components ──────────────────────────────────────────────────────────

/* Small horizontal progress bar */
const Bar: React.FC<{ value: number; max?: number; label?: string; colorClass?: string }> = ({
  value, max = 100, label, colorClass,
}) => {
  const pct = Math.min(100, Math.max(0, (value / max) * 100));
  const cls = colorClass ?? barColorClass[pctTone(value)];
  return (
    <div className="mt-1.5">
      {label && (
        <div className="mb-1 font-mono text-[11px] text-muted">{label}</div>
      )}
      <div className="h-1.5 overflow-hidden rounded-full bg-surface-dim">
        <div
          className={`h-full rounded-full transition-[width] duration-400 ease-out ${cls}`}
          style={{ width: `${pct}%` }}
        />
      </div>
    </div>
  );
};

/* CPU card */
const CpuCard: React.FC<{ data: ServerHealth['cpu'] }> = ({ data }) => (
  <Card padding="18px 22px">
    <div className="mb-1.5 flex items-baseline justify-between">
      <span className="text-[15px] font-bold text-ink">CPU</span>
      <Badge tone={badgeToneForPct(data.overall_percent)}>{data.overall_percent.toFixed(0)}%</Badge>
    </div>
    <div className="font-mono text-xs text-muted">
      {data.logical_cores} logical / {data.physical_cores} physical cores
    </div>
    {Object.keys(data.load_average).length > 0 && (
      <div className="mt-0.5 font-mono text-xs text-muted">
        load: {data.load_average['1m'].toFixed(2)} / {data.load_average['5m'].toFixed(2)} / {data.load_average['15m'].toFixed(2)}
      </div>
    )}
    <div className="mt-2.5 flex flex-wrap gap-1">
      {data.per_core_percent.map((v, i) => (
        <div key={i} className="min-w-7 flex-1 rounded-md bg-surface-dim px-0.5 py-1 text-center">
          <div className="text-[9px] text-muted">#{i}</div>
          <div className={`font-mono text-xs font-bold ${pctTextClass[pctTone(v)]}`}>
            {v.toFixed(0)}%
          </div>
        </div>
      ))}
    </div>
  </Card>
);

/* Memory card */
const MemoryCard: React.FC<{ mem: ServerHealth['memory']; swap: ServerHealth['swap'] }> = ({ mem, swap }) => (
  <Card padding="18px 22px">
    <div className="mb-1.5 flex items-baseline justify-between">
      <span className="text-[15px] font-bold text-ink">Memory</span>
      <Badge tone={badgeToneForPct(mem.percent)}>{mem.percent.toFixed(0)}%</Badge>
    </div>
    <div className="mb-1 font-mono text-xs text-ink">
      {fmtBytes(mem.used_bytes)} / {fmtBytes(mem.total_bytes)} used &nbsp;·&nbsp; {fmtBytes(mem.available_bytes)} avail
    </div>
    <Bar value={mem.percent} label="RAM" />
    {swap.total_bytes > 0 && (
      <>
        <div className="mb-0.5 mt-2.5 font-mono text-xs text-muted">
          Swap: {fmtBytes(swap.used_bytes)} / {fmtBytes(swap.total_bytes)} ({swap.percent.toFixed(0)}%)
        </div>
        <Bar value={swap.percent} label="Swap" />
      </>
    )}
  </Card>
);

/* Storage breakdown row (shown inside expanded disk card) */
const StorageBreakdownRow: React.FC<{
  entry: { path: string; size_bytes: number; depth: number };
  maxSize: number;
  mountpoint: string;
}> = ({ entry, maxSize, mountpoint }) => {
  const pct = maxSize > 0 ? Math.min(100, (entry.size_bytes / maxSize) * 100) : 0;
  const rel = entry.path === mountpoint ? entry.path : entry.path.replace(mountpoint, '').replace(/^\//, '') || mountpoint;
  return (
    <div className="group flex items-center gap-2 py-0.5">
      <div className="flex-1 truncate font-mono text-[11px] text-muted group-hover:text-ink">
        {rel}
      </div>
      <div className="w-16 text-right font-mono text-[11px] text-ink">
        {fmtBytes(entry.size_bytes)}
      </div>
      <div className="w-20">
        <div className="h-1.5 overflow-hidden rounded-full bg-surface-dim">
          <div
            className={`h-full rounded-full transition-[width] duration-300 ease-out ${barColorClass[pctTone(pct)]}`}
            style={{ width: `${pct}%` }}
          />
        </div>
      </div>
    </div>
  );
};

/* Storage breakdown section */
const StorageBreakdownCard: React.FC<{
  mountpoint: string;
  data: StorageBreakdown | null;
  loading: boolean;
}> = ({ mountpoint, data, loading }) => {
  const entries = data?.entries.filter(e => e.mountpoint === mountpoint) ?? [];
  const maxBytes = entries.length > 0 ? Math.max(...entries.map(e => e.size_bytes)) : 0;

  return (
    <Card padding="14px 18px" className="mt-2">
      <div className="mb-2 flex items-center justify-between">
        <span className="font-mono text-[11px] uppercase tracking-wider text-muted">Storage Breakdown</span>
        {loading && <Spinner size="sm" label="" />}
      </div>
      {entries.length === 0 && !loading && (
        <div className="font-mono text-[11px] text-muted">No data available</div>
      )}
      {entries.map((entry, i) => (
        <StorageBreakdownRow
          key={i}
          entry={{ path: entry.path, size_bytes: entry.size_bytes, depth: entry.depth }}
          maxSize={maxBytes}
          mountpoint={mountpoint}
        />
      ))}
    </Card>
  );
};

/* Disk card */
const DiskCard: React.FC<{
  disk: ServerHealth['disks'][0];
  expanded: boolean;
  breakdownData: Record<string, StorageBreakdown | null>;
  breakdownLoading: Record<string, boolean>;
  onLoadBreakdown: (mp: string) => void;
}> = ({ disk, expanded, breakdownData, breakdownLoading, onLoadBreakdown }) => (
  <Card padding="14px 18px">
    <div className="flex items-baseline justify-between">
      <span className="font-mono text-[13px] font-semibold text-ink">{disk.mountpoint}</span>
      <div className="flex items-center gap-2">
        <Badge tone={disk.percent > 85 ? 'danger' : disk.percent > 60 ? 'gold' : 'neutral'}>
          {disk.percent.toFixed(0)}%
        </Badge>
        <button
          onClick={() => onLoadBreakdown(disk.mountpoint)}
          className="text-[10px] text-muted hover:text-ink"
          title="Show storage breakdown"
        >
          {expanded ? '▴' : '▾'}
        </button>
      </div>
    </div>
    <div className="font-mono text-[11px] text-muted">
      {fmtBytes(disk.used_bytes)} / {fmtBytes(disk.total_bytes)} &nbsp;·&nbsp; {fmtBytes(disk.free_bytes)} free
    </div>
    <Bar value={disk.percent} />
    {expanded && (
      <StorageBreakdownCard
        mountpoint={disk.mountpoint}
        data={breakdownData[disk.mountpoint] ?? null}
        loading={breakdownLoading[disk.mountpoint] ?? false}
      />
    )}
  </Card>
);

/* GPU card */
const GpuCard: React.FC<{ gpu: HealthGPU }> = ({ gpu }) => {
  const memPct = gpu.memory_total_miB > 0 ? (gpu.memory_used_miB / gpu.memory_total_miB) * 100 : 0;
  return (
    <Card padding="18px 22px">
      <div className="mb-1.5 flex items-baseline justify-between">
        <span className="text-[15px] font-bold text-ink">{gpu.name}</span>
        <Badge tone="teal">{gpu.gpu_util_percent.toFixed(0)}% util</Badge>
      </div>

      {/* VRAM */}
      <div className="mb-0.5 font-mono text-xs text-ink">
        VRAM: {fmtMiB(gpu.memory_used_miB)} / {fmtMiB(gpu.memory_total_miB)}
      </div>
      <Bar value={memPct} label="VRAM" />

      <div className="mt-3 grid grid-cols-2 gap-x-4 gap-y-2">
        <Metric label="Temp" value={`${gpu.temperature_c.toFixed(0)}°C`} />
        <Metric label="Power" value={`${gpu.power_draw_w.toFixed(0)}W / ${gpu.power_limit_w.toFixed(0)}W`} />
        <Metric label="GPU Clock" value={`${gpu.clock_gr_mhz} MHz`} />
        <Metric label="Mem Clock" value={`${gpu.clock_mem_mhz} MHz`} />
        <Metric label="Mem Util" value={`${gpu.mem_util_percent.toFixed(0)}%`} />
        <Metric label="Driver" value={gpu.driver_version} />
      </div>
    </Card>
  );
};

const Metric: React.FC<{ label: string; value: string }> = ({ label, value }) => (
  <div>
    <div className="font-mono text-[10px] uppercase tracking-wider text-muted">{label}</div>
    <div className="font-mono text-xs font-semibold text-ink">{value}</div>
  </div>
);

/* Network card */
const NetworkCard: React.FC<{ data: ServerHealth['network'] }> = ({ data }) => (
  <Card padding="18px 22px">
    <span className="text-[15px] font-bold text-ink">Network</span>
    <div className="mt-2.5 grid grid-cols-2 gap-x-4 gap-y-2">
      <Metric label="Sent" value={fmtBytes(data.bytes_sent)} />
      <Metric label="Received" value={fmtBytes(data.bytes_recv)} />
      <Metric label="Pkts Sent" value={data.packets_sent.toLocaleString()} />
      <Metric label="Pkts Recv" value={data.packets_recv.toLocaleString()} />
    </div>
  </Card>
);

// ── Main Page ───────────────────────────────────────────────────────────────
const ServerHealthPage: React.FC = () => {
  const [data, setData] = useState<ServerHealth | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [autoRefresh, setAutoRefresh] = useState(true);
  const [expandedDisks, setExpandedDisks] = useState<Set<string>>(new Set());
  const [breakdownData, setBreakdownData] = useState<Record<string, StorageBreakdown | null>>({});
  const [breakdownLoading, setBreakdownLoading] = useState<Record<string, boolean>>({});

  const load = useCallback(async () => {
    setLoading(true);
    setError('');
    try {
      setData(await fetchServerHealth());
    } catch {
      setError('Failed to load server health data');
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { load(); }, [load]);

  const loadBreakdown = useCallback(async (mp: string) => {
    const current = expandedDisks.has(mp);
    setExpandedDisks(prev => {
      const next = new Set(prev);
      if (current) next.delete(mp);
      else next.add(mp);
      return next;
    });
    if (!current) {
      if (!breakdownData[mp]) {
        setBreakdownLoading(prev => ({ ...prev, [mp]: true }));
        try {
          const bd = await fetchStorageBreakdown(mp, 1);
          setBreakdownData(prev => ({ ...prev, [mp]: bd }));
        } catch {
          setBreakdownData(prev => ({ ...prev, [mp]: null }));
        } finally {
          setBreakdownLoading(prev => ({ ...prev, [mp]: false }));
        }
      }
    }
  }, [expandedDisks, breakdownData]);

  // Auto-refresh every 5 seconds
  useEffect(() => {
    if (!autoRefresh) return;
    const id = setInterval(load, 5000);
    return () => clearInterval(id);
  }, [autoRefresh, load]);

  return (
    <div className="mx-auto max-w-[1100px] px-4 pb-12 pt-6 md:px-6">
      <PageHeader
        eyebrow="Assistant / Server Health"
        eyebrowColor="var(--signal)"
        title="Server Health"
        actions={
          <>
            <button
              onClick={() => setAutoRefresh((v) => !v)}
              className={`rounded-md px-3 py-1 text-xs font-semibold ${
                autoRefresh ? 'bg-signal text-bg' : 'bg-surface-dim text-ink-dim'
              }`}
            >
              Auto-refresh {autoRefresh ? 'ON' : 'OFF'}
            </button>
            <button onClick={load} className="rounded-md px-3 py-1 text-xs font-semibold">Refresh</button>
            {data && (
              <span className="flex items-center gap-2 font-mono text-[11px] text-muted">
                {autoRefresh && <PulseDot tone="signal" />}
                {new Date(data.timestamp).toLocaleTimeString()}
              </span>
            )}
          </>
        }
      />

      {/* Uptime banner */}
      {data && (
        <Card padding="12px 22px" className="mb-6" style={{ background: 'var(--surface-dim)' }}>
          <div className="flex flex-wrap gap-6">
            <div className="font-mono text-[13px] text-ink">
              <span className="text-muted">Uptime: </span>
              <span className="font-bold text-signal">{fmtUptime(data.uptime_seconds)}</span>
            </div>
            <div className="font-mono text-[13px] text-ink">
              <span className="text-muted">Boot: </span>
              {new Date(data.boot_time).toLocaleString()}
            </div>
          </div>
        </Card>
      )}

      {error && <p className="mb-4 text-sm text-alert-red">{error}</p>}
      {loading && !data && <Spinner label="Loading server health…" />}

      {data && (
        <>
          {/* Top row: CPU + Memory side by side */}
          <div className="mb-4 grid grid-cols-1 gap-4 md:grid-cols-2">
            <CpuCard data={data.cpu} />
            <MemoryCard mem={data.memory} swap={data.swap} />
          </div>

          {/* GPUs */}
          {data.gpus.length > 0 && (
            <section className="mb-4">
              <h3 className="mb-3 font-mono text-[13px] uppercase tracking-wider text-muted">
                GPUs ({data.gpus.length})
              </h3>
              <div className="grid grid-cols-1 gap-3 lg:grid-cols-2">
                {data.gpus.map((gpu, i) => (
                  <GpuCard key={i} gpu={gpu} />
                ))}
              </div>
            </section>
          )}

          {/* Disks */}
          <section className="mb-4">
            <h3 className="mb-3 font-mono text-[13px] uppercase tracking-wider text-muted">
              Disks
            </h3>
            <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-3">
              {data.disks.map((d, i) => (
                <DiskCard
                  key={i}
                  disk={d}
                  expanded={expandedDisks.has(d.mountpoint)}
                  breakdownData={breakdownData}
                  breakdownLoading={breakdownLoading}
                  onLoadBreakdown={loadBreakdown}
                />
              ))}
            </div>
          </section>

          {/* Network */}
          <NetworkCard data={data.network} />
        </>
      )}
    </div>
  );
};

export default ServerHealthPage;
