import React, { useEffect, useState } from 'react';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import { fetchChattyMemory } from '../chattyApi';
import type { MemoryData, MemoryEntry } from '../chattyApi';
import PageHeader from '../components/ui/PageHeader';
import './MemoryViewer.css';

const MemoryViewer: React.FC = () => {
  const [data, setData] = useState<MemoryData | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [days, setDays] = useState(7);
  const [activeTab, setActiveTab] = useState<'short_term' | 'long_term'>('short_term');
  const [openDates, setOpenDates] = useState<Set<string>>(new Set());

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
    <div style={{ maxWidth: 900, margin: '0 auto', padding: '24px 24px 48px' }}>
      <PageHeader
        eyebrow="Assistant / Memory"
        eyebrowColor="var(--stamp-teal)"
        title="Memory"
        actions={
          <div style={{ display: 'flex', alignItems: 'center', gap: 8, fontSize: 13, color: 'var(--muted)' }}>
            <label htmlFor="days-select">Last</label>
            <select
              id="days-select"
              value={days}
              onChange={(e) => setDays(Number(e.target.value))}
              style={{ padding: '4px 8px', borderRadius: 6, fontSize: 13 }}
            >
              {[3, 7, 14, 30, 60, 90].map((d) => (
                <option key={d} value={d}>{d} days</option>
              ))}
            </select>
          </div>
        }
      />

      {/* Tabs */}
      <div style={{ display: 'flex', gap: 4, marginBottom: 20 }}>
        {(['short_term', 'long_term'] as const).map((tab) => (
          <button
            key={tab}
            onClick={() => setActiveTab(tab)}
            style={{
              padding: '7px 16px', borderRadius: 8, fontWeight: 600, fontSize: 13,
              background: activeTab === tab ? 'var(--stamp-teal)' : 'var(--ink-800)',
              color: activeTab === tab ? 'var(--ink-900)' : 'var(--muted)',
              border: activeTab === tab ? 'none' : '1px solid var(--ink-700)',
            }}
          >
            {tab === 'short_term' ? 'Short-term' : 'Long-term'}
            {data && (
              <span style={{ marginLeft: 6, fontSize: 11, fontFamily: 'var(--font-mono)', opacity: 0.8 }}>
                {data[tab].length}
              </span>
            )}
          </button>
        ))}
      </div>

      {error && <p style={{ color: 'var(--danger)' }}>{error}</p>}
      {loading ? (
        <p style={{ color: 'var(--muted)' }}>Loading memory…</p>
      ) : entries.length === 0 ? (
        <p style={{ color: 'var(--muted)', textAlign: 'center', marginTop: 40 }}>No {activeTab.replace('_', '-')} memory entries found.</p>
      ) : (
        <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
          {entries.map((entry) => (
            <div key={entry.filename} style={{ border: '1px solid var(--ink-700)', borderRadius: 8, overflow: 'hidden' }}>
              {/* Accordion header */}
              <button
                onClick={() => toggleDate(entry.date)}
                style={{
                  width: '100%', textAlign: 'left', padding: '11px 16px', borderRadius: 0,
                  background: openDates.has(entry.date) ? 'var(--ink-750)' : 'var(--ink-800)',
                  display: 'flex', justifyContent: 'space-between', alignItems: 'center',
                  fontWeight: 600, fontSize: 13, color: 'var(--paper)', fontFamily: 'var(--font-mono)',
                }}
              >
                <span>{entry.date}</span>
                <span style={{ fontSize: 11, color: 'var(--stamp-teal)' }}>
                  {openDates.has(entry.date) ? 'collapse' : 'expand'}
                </span>
              </button>
              {/* Content */}
              {openDates.has(entry.date) && (
                <div className="memory-markdown" style={{
                  margin: 0, padding: '16px 20px', fontSize: 13.5, lineHeight: 1.7,
                  background: 'var(--ink-900)', color: 'var(--paper-dim)',
                  borderTop: '1px solid var(--ink-700)',
                  overflowX: 'auto',
                }}>
                  <ReactMarkdown remarkPlugins={[remarkGfm]}>
                    {entry.content}
                  </ReactMarkdown>
                </div>
              )}
            </div>
          ))}
        </div>
      )}
    </div>
  );
};

export default MemoryViewer;
