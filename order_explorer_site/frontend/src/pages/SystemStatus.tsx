import React, { useEffect, useState } from 'react';
import { fetchChattySystem } from '../chattyApi';
import type { SystemStatus as SystemStatusData, Pm2Process } from '../chattyApi';
import PageHeader from '../components/ui/PageHeader';
import Card from '../components/ui/Card';
import Badge from '../components/ui/Badge';

const statusColor: Record<string, string> = {
  online: 'var(--success)',
  stopping: 'var(--stamp-gold)',
  stopped: 'var(--danger)',
  errored: 'var(--danger)',
  'one-launch': 'var(--stamp-teal)',
};

const Pm2Badge: React.FC<{ proc: Pm2Process }> = ({ proc }) => {
  if (proc.error) {
    return <span style={{ fontSize: 12, color: 'var(--muted)' }}>pm2 unavailable</span>;
  }
  const color = statusColor[proc.status ?? ''] ?? 'var(--muted)';
  return (
    <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
      <span style={{ width: 7, height: 7, borderRadius: '50%', background: color, display: 'inline-block' }} />
      <span style={{ fontSize: 13, fontWeight: 600, color: 'var(--paper)' }}>{proc.name}</span>
      <span style={{ fontSize: 11, color, fontWeight: 600, fontFamily: 'var(--font-mono)' }}>{proc.status}</span>
      {proc.restarts !== undefined && proc.restarts > 0 && (
        <span style={{ fontSize: 11, color: 'var(--muted)', fontFamily: 'var(--font-mono)' }}>↺{proc.restarts}</span>
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
    <div style={{ maxWidth: 900, margin: '0 auto', padding: '24px 24px 48px' }}>
      <PageHeader
        eyebrow="Assistant / System"
        eyebrowColor="var(--stamp-teal)"
        title="System status"
        actions={
          <>
            <button onClick={load} style={{ fontSize: 12, padding: '4px 12px' }}>Refresh</button>
            {data && (
              <span style={{ fontSize: 11, fontFamily: 'var(--font-mono)', color: 'var(--muted)' }}>
                {new Date(data.timestamp).toLocaleTimeString()}
              </span>
            )}
          </>
        }
      />

      {error && <p style={{ color: 'var(--danger)' }}>{error}</p>}
      {loading && <p style={{ color: 'var(--muted)' }}>Loading…</p>}

      {data && (
        <>
          {/* pm2 section */}
          <section style={{ marginBottom: 32 }}>
            <h3 style={{ fontSize: 13, fontFamily: 'var(--font-mono)', letterSpacing: '0.08em', textTransform: 'uppercase', marginBottom: 14, color: 'var(--muted)' }}>
              Processes (pm2)
            </h3>
            {data.pm2.length === 0 ? (
              <p style={{ color: 'var(--muted)' }}>No pm2 processes found.</p>
            ) : (
              <div style={{ display: 'flex', flexWrap: 'wrap', gap: 12 }}>
                {data.pm2.map((proc, i) => (
                  <Card key={i} padding="12px 18px" style={{ minWidth: 180 }}>
                    <Pm2Badge proc={proc} />
                    {proc.pid && <div style={{ fontSize: 11, color: 'var(--muted)', marginTop: 4, fontFamily: 'var(--font-mono)' }}>PID {proc.pid}</div>}
                  </Card>
                ))}
              </div>
            )}
          </section>

          {/* Skills section */}
          <section>
            <h3 style={{ fontSize: 13, fontFamily: 'var(--font-mono)', letterSpacing: '0.08em', textTransform: 'uppercase', marginBottom: 14, color: 'var(--muted)' }}>
              Loaded skills ({data.skills.length})
            </h3>
            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(280px, 1fr))', gap: 12 }}>
              {data.skills.map((skill) => (
                <div
                  key={skill.name}
                  style={{
                    background: 'var(--ink-800)', borderRadius: 10, border: '1px solid var(--ink-700)',
                    overflow: 'hidden',
                  }}
                >
                  <button
                    onClick={() => setExpandedSkill(expandedSkill === skill.name ? null : skill.name)}
                    style={{
                      width: '100%', textAlign: 'left', padding: '14px 16px', borderRadius: 0,
                      background: expandedSkill === skill.name ? 'var(--ink-750)' : 'var(--ink-800)',
                      display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start',
                    }}
                  >
                    <div>
                      <div style={{ fontWeight: 700, fontSize: 14, color: 'var(--paper)', marginBottom: 4 }}>
                        {skill.name}
                      </div>
                      <div style={{ fontSize: 12, color: 'var(--muted)', lineHeight: 1.45 }}>
                        {skill.description.slice(0, 80)}{skill.description.length > 80 ? '…' : ''}
                      </div>
                    </div>
                    <Badge tone="teal">{skill.tool_count} tool{skill.tool_count !== 1 ? 's' : ''}</Badge>
                  </button>
                  {expandedSkill === skill.name && skill.tools.length > 0 && (
                    <div style={{ padding: '0 16px 14px', borderTop: '1px solid var(--ink-700)' }}>
                      <div style={{ fontSize: 11, fontFamily: 'var(--font-mono)', letterSpacing: '0.06em', textTransform: 'uppercase', color: 'var(--muted)', marginTop: 10, marginBottom: 6 }}>Tools</div>
                      <div style={{ display: 'flex', flexWrap: 'wrap', gap: 6 }}>
                        {skill.tools.map((t) => (
                          <span key={t} style={{
                            fontSize: 11, padding: '2px 8px', borderRadius: 6,
                            background: 'var(--ink-900)', color: 'var(--paper-dim)', fontFamily: 'var(--font-mono)',
                          }}>
                            {t}
                          </span>
                        ))}
                      </div>
                      {skill.description.length > 80 && (
                        <div style={{ fontSize: 12, color: 'var(--muted)', marginTop: 10, lineHeight: 1.5 }}>
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
