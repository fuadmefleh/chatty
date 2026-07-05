import React, { useEffect, useState } from 'react';
import { fetchChattySystem } from '../chattyApi';
import type { SystemStatus as SystemStatusData, Pm2Process } from '../chattyApi';
import PageHeader from '../components/ui/PageHeader';
import Card from '../components/ui/Card';
import Badge from '../components/ui/Badge';
import Spinner from '../components/ui/Spinner';

const statusToneClass: Record<string, string> = {
  online: 'bg-alert-green',
  stopping: 'bg-alert-amber',
  stopped: 'bg-alert-red',
  errored: 'bg-alert-red',
  'one-launch': 'bg-signal',
};

const statusTextClass: Record<string, string> = {
  online: 'text-alert-green',
  stopping: 'text-alert-amber',
  stopped: 'text-alert-red',
  errored: 'text-alert-red',
  'one-launch': 'text-signal',
};

const Pm2Badge: React.FC<{ proc: Pm2Process }> = ({ proc }) => {
  if (proc.error) {
    return <span className="text-xs text-muted">pm2 unavailable</span>;
  }
  const dotClass = statusToneClass[proc.status ?? ''] ?? 'bg-muted';
  const textClass = statusTextClass[proc.status ?? ''] ?? 'text-muted';
  return (
    <div className="flex items-center gap-1.5">
      <span className={`inline-block h-1.5 w-1.5 rounded-full ${dotClass}`} />
      <span className="text-[13px] font-semibold text-ink">{proc.name}</span>
      <span className={`font-mono text-[11px] font-semibold ${textClass}`}>{proc.status}</span>
      {proc.restarts !== undefined && proc.restarts > 0 && (
        <span className="font-mono text-[11px] text-muted">↺{proc.restarts}</span>
      )}
    </div>
  );
};

const SystemStatus: React.FC = () => {
  const [data, setData] = useState<SystemStatusData | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [expandedSkill, setExpandedSkill] = useState<string | null>(null);

  const load = async () => {
    setLoading(true);
    setError('');
    try {
      setData(await fetchChattySystem());
    } catch {
      setError('Failed to load system status');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => { load(); }, []);

  return (
    <div className="mx-auto max-w-[900px] px-4 pb-12 pt-6 md:px-6">
      <PageHeader
        eyebrow="Assistant / System"
        eyebrowColor="var(--signal)"
        title="System status"
        actions={
          <>
            <button onClick={load} className="rounded-md px-3 py-1 text-xs font-semibold">Refresh</button>
            {data && (
              <span className="font-mono text-[11px] text-muted">
                {new Date(data.timestamp).toLocaleTimeString()}
              </span>
            )}
          </>
        }
      />

      {error && <p className="mb-4 text-sm text-alert-red">{error}</p>}
      {loading && !data && <Spinner label="Loading system status…" />}

      {data && (
        <>
          {/* pm2 section */}
          <section className="mb-8">
            <h3 className="mb-3.5 font-mono text-[13px] uppercase tracking-wider text-muted">
              Processes (pm2)
            </h3>
            {data.pm2.length === 0 ? (
              <p className="text-muted">No pm2 processes found.</p>
            ) : (
              <div className="flex flex-wrap gap-3">
                {data.pm2.map((proc, i) => (
                  <Card key={i} padding="12px 18px" className="min-w-[180px]">
                    <Pm2Badge proc={proc} />
                    {proc.pid && <div className="mt-1 font-mono text-[11px] text-muted">PID {proc.pid}</div>}
                  </Card>
                ))}
              </div>
            )}
          </section>

          {/* Skills section */}
          <section>
            <h3 className="mb-3.5 font-mono text-[13px] uppercase tracking-wider text-muted">
              Loaded skills ({data.skills.length})
            </h3>
            <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
              {data.skills.map((skill) => (
                <div
                  key={skill.name}
                  className="overflow-hidden rounded-[10px] border border-line bg-surface"
                >
                  <button
                    onClick={() => setExpandedSkill(expandedSkill === skill.name ? null : skill.name)}
                    className={`flex w-full items-start justify-between rounded-none px-4 py-3.5 text-left ${
                      expandedSkill === skill.name ? 'bg-surface-dim' : 'bg-surface'
                    }`}
                  >
                    <div>
                      <div className="mb-1 text-sm font-bold text-ink">
                        {skill.name}
                      </div>
                      <div className="text-xs leading-snug text-muted">
                        {skill.description.slice(0, 80)}{skill.description.length > 80 ? '…' : ''}
                      </div>
                    </div>
                    <Badge tone="teal">{skill.tool_count} tool{skill.tool_count !== 1 ? 's' : ''}</Badge>
                  </button>
                  {expandedSkill === skill.name && skill.tools.length > 0 && (
                    <div className="border-t border-line px-4 pb-3.5">
                      <div className="mb-1.5 mt-2.5 font-mono text-[11px] uppercase tracking-wider text-muted">Tools</div>
                      <div className="flex flex-wrap gap-1.5">
                        {skill.tools.map((t) => (
                          <span key={t} className="rounded-md bg-surface-dim px-2 py-0.5 font-mono text-[11px] text-ink-dim">
                            {t}
                          </span>
                        ))}
                      </div>
                      {skill.description.length > 80 && (
                        <div className="mt-2.5 text-xs leading-snug text-muted">
                          {skill.description}
                        </div>
                      )}
                    </div>
                  )}
                </div>
              ))}
            </div>
          </section>
        </>
      )}
    </div>
  );
};

export default SystemStatus;
