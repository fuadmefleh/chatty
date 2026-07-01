import React, { useEffect, useState } from 'react';
import axios from 'axios';
import { Link } from 'react-router-dom';
import PageHeader from '../components/ui/PageHeader';
import Card from '../components/ui/Card';

interface RecurringItem {
  name: string;
  purchase_count: number;
  total_spent: number;
  avg_price: number;
  category: string;
  sources: string[];
  avg_days_between: number | null;
  last_purchase: string | null;
  first_purchase: string | null;
}

const statLabel: React.CSSProperties = { margin: 0, fontSize: '11px', color: 'var(--muted)', fontFamily: 'var(--font-mono)', textTransform: 'uppercase', letterSpacing: '0.04em' };

const sortBtn = (active: boolean): React.CSSProperties => ({
  background: active ? 'var(--stamp-gold)' : 'transparent',
  color: active ? 'var(--ink-900)' : 'var(--muted)',
  border: active ? 'none' : '1px solid var(--ink-700)',
  padding: '7px 16px',
  fontSize: '13px',
  fontWeight: 600,
});

const Recurring: React.FC = () => {
  const [items, setItems] = useState<RecurringItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [sortBy, setSortBy] = useState<'count' | 'frequency' | 'total'>('count');

  useEffect(() => {
    axios.get<RecurringItem[]>('http://localhost:8015/recurring')
      .then(response => {
        setItems(response.data);
        setLoading(false);
      })
      .catch(err => {
        console.error('Failed to load recurring items', err);
        setLoading(false);
      });
  }, []);

  if (loading) return <div style={{ padding: 24, color: 'var(--muted)' }}>Loading recurring items…</div>;

  const sortedItems = [...items].sort((a, b) => {
    if (sortBy === 'count') {
      return b.purchase_count - a.purchase_count;
    } else if (sortBy === 'frequency') {
      const aFreq = a.avg_days_between ?? Infinity;
      const bFreq = b.avg_days_between ?? Infinity;
      return aFreq - bFreq;
    } else {
      return b.total_spent - a.total_spent;
    }
  });

  const getDaysSinceLastPurchase = (lastPurchase: string | null): number | null => {
    if (!lastPurchase) return null;
    try {
      const lastDate = new Date(lastPurchase);
      const now = new Date();
      const diffTime = Math.abs(now.getTime() - lastDate.getTime());
      const diffDays = Math.ceil(diffTime / (1000 * 60 * 60 * 24));
      return diffDays;
    } catch {
      return null;
    }
  };

  const getFrequencyLabel = (avgDays: number | null): string => {
    if (!avgDays) return 'Unknown';
    if (avgDays < 7) return 'Weekly';
    if (avgDays < 30) return 'Bi-weekly';
    if (avgDays < 60) return 'Monthly';
    if (avgDays < 120) return 'Bi-monthly';
    if (avgDays < 365) return 'Quarterly';
    return 'Yearly';
  };

  const getReorderAlert = (item: RecurringItem): boolean => {
    if (!item.avg_days_between || !item.last_purchase) return false;
    const daysSince = getDaysSinceLastPurchase(item.last_purchase);
    if (daysSince === null) return false;
    return daysSince >= item.avg_days_between * 0.9;
  };

  const reorderAlerts = sortedItems.filter(getReorderAlert);

  return (
    <div style={{ padding: '24px 24px 48px' }}>
      <PageHeader eyebrow="Ledger / Recurring" title="Recurring items & subscriptions" />

      {/* Summary Cards */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(220px, 1fr))', gap: '16px', marginBottom: '28px' }}>
        <Card>
          <h3 style={statLabel}>Recurring items</h3>
          <p style={{ margin: '10px 0 0', fontSize: '28px', fontWeight: 700, fontFamily: 'var(--font-mono)', color: 'var(--stamp-gold)' }}>{items.length}</p>
          <p style={{ margin: '4px 0 0', fontSize: '13px', color: 'var(--muted)' }}>purchased multiple times</p>
        </Card>

        <Card>
          <h3 style={statLabel}>Reorder alerts</h3>
          <p style={{ margin: '10px 0 0', fontSize: '28px', fontWeight: 700, fontFamily: 'var(--font-mono)', color: reorderAlerts.length > 0 ? 'var(--stamp-ember)' : 'var(--success)' }}>
            {reorderAlerts.length}
          </p>
          <p style={{ margin: '4px 0 0', fontSize: '13px', color: 'var(--muted)' }}>
            {reorderAlerts.length > 0 ? 'items may need reordering' : 'all items up to date'}
          </p>
        </Card>

        {items.length > 0 && (
          <>
            <Card>
              <h3 style={statLabel}>Most purchased</h3>
              <p style={{ margin: '10px 0 0', fontSize: '17px', fontWeight: 700, color: 'var(--paper)' }}>{items[0].name}</p>
              <p style={{ margin: '4px 0 0', fontSize: '13px', color: 'var(--muted)' }}>{items[0].purchase_count} times</p>
            </Card>

            <Card>
              <h3 style={statLabel}>Total on recurring</h3>
              <p style={{ margin: '10px 0 0', fontSize: '28px', fontWeight: 700, fontFamily: 'var(--font-mono)', color: 'var(--stamp-gold)' }}>
                ${items.reduce((sum, item) => sum + item.total_spent, 0).toFixed(2)}
              </p>
            </Card>
          </>
        )}
      </div>

      {/* Reorder Alerts */}
      {reorderAlerts.length > 0 && (
        <Card style={{ marginBottom: '28px', borderLeft: '3px solid var(--stamp-ember)' }}>
          <h2 style={{ fontSize: 15, marginBottom: 8, color: 'var(--paper)' }}>Reorder alerts</h2>
          <p style={{ margin: '0 0 16px 0', fontSize: '13px', color: 'var(--muted)' }}>
            These items may need reordering based on your typical purchase frequency:
          </p>
          <div style={{ display: 'flex', flexDirection: 'column', gap: '10px' }}>
            {reorderAlerts.map(item => (
              <div
                key={item.name}
                style={{
                  background: 'var(--ink-900)',
                  padding: '12px 16px',
                  borderRadius: '8px',
                  display: 'flex',
                  justifyContent: 'space-between',
                  alignItems: 'center',
                  border: '1px solid var(--ink-700)',
                }}
              >
                <div>
                  <Link to={`/items/${encodeURIComponent(item.name)}`} style={{ fontWeight: 600, color: 'var(--stamp-teal)', fontSize: '14px' }}>
                    {item.name}
                  </Link>
                  <p style={{ margin: '5px 0 0 0', fontSize: '12px', color: 'var(--muted)' }}>
                    Last purchased {getDaysSinceLastPurchase(item.last_purchase)} days ago · Typically every {item.avg_days_between?.toFixed(0)} days
                  </p>
                </div>
                <span style={{ background: 'var(--stamp-ember)', color: 'var(--ink-900)', padding: '4px 12px', borderRadius: '12px', fontSize: '12px', fontWeight: 700 }}>
                  Reorder
                </span>
              </div>
            ))}
          </div>
        </Card>
      )}

      {/* Sort Controls */}
      <Card style={{ marginBottom: '20px', padding: '14px 20px' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '10px', flexWrap: 'wrap' }}>
          <span style={{ fontSize: '12px', fontWeight: 600, color: 'var(--muted)', fontFamily: 'var(--font-mono)', textTransform: 'uppercase' }}>Sort by</span>
          <button onClick={() => setSortBy('count')} style={sortBtn(sortBy === 'count')}>Purchase count</button>
          <button onClick={() => setSortBy('frequency')} style={sortBtn(sortBy === 'frequency')}>Frequency</button>
          <button onClick={() => setSortBy('total')} style={sortBtn(sortBy === 'total')}>Total spent</button>
        </div>
      </Card>

      {/* Recurring Items List */}
      <div style={{ border: '1px solid var(--ink-700)', borderRadius: '10px', overflow: 'hidden' }}>
        <h2 style={{ margin: 0, padding: '16px 20px', borderBottom: '1px solid var(--ink-700)', background: 'var(--ink-800)', fontSize: 13, fontFamily: 'var(--font-mono)', letterSpacing: '0.06em', textTransform: 'uppercase', color: 'var(--muted)' }}>
          All recurring items
        </h2>
        <div style={{ display: 'flex', flexDirection: 'column' }}>
          {sortedItems.map((item, idx) => {
            const daysSince = getDaysSinceLastPurchase(item.last_purchase);
            const isAlert = getReorderAlert(item);

            return (
              <div
                key={item.name}
                style={{
                  padding: '18px 20px',
                  borderBottom: idx < sortedItems.length - 1 ? '1px solid var(--ink-700)' : 'none',
                  backgroundColor: isAlert ? 'rgba(216, 96, 63, 0.08)' : (idx % 2 === 0 ? 'var(--ink-800)' : 'var(--ink-900)'),
                }}
              >
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'start', marginBottom: '12px' }}>
                  <div style={{ flex: 1 }}>
                    <Link to={`/items/${encodeURIComponent(item.name)}`} style={{ fontSize: '16px', fontWeight: 700, color: 'var(--stamp-teal)' }}>
                      {item.name}
                    </Link>
                    {isAlert && (
                      <span style={{ marginLeft: '10px', background: 'var(--stamp-ember)', color: 'var(--ink-900)', padding: '2px 8px', borderRadius: '10px', fontSize: '11px', fontWeight: 700 }}>
                        Reorder
                      </span>
                    )}
                    <p style={{ margin: '5px 0', fontSize: '13px', color: 'var(--muted)' }}>
                      {item.category} · {item.sources.join(', ')}
                    </p>
                  </div>
                </div>

                <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(140px, 1fr))', gap: '14px' }}>
                  <div>
                    <p style={statLabel}>Purchases</p>
                    <p style={{ margin: '4px 0 0', fontSize: '18px', fontWeight: 700, fontFamily: 'var(--font-mono)', color: 'var(--stamp-gold)' }}>{item.purchase_count}x</p>
                  </div>

                  <div>
                    <p style={statLabel}>Frequency</p>
                    <p style={{ margin: '4px 0 0', fontSize: '15px', fontWeight: 700, color: 'var(--paper)' }}>{getFrequencyLabel(item.avg_days_between)}</p>
                    {item.avg_days_between && (
                      <p style={{ margin: '2px 0 0', fontSize: '11px', color: 'var(--muted)' }}>Every ~{item.avg_days_between.toFixed(0)} days</p>
                    )}
                  </div>

                  <div>
                    <p style={statLabel}>Avg price</p>
                    <p style={{ margin: '4px 0 0', fontSize: '16px', fontWeight: 700, fontFamily: 'var(--font-mono)', color: 'var(--paper)' }}>${item.avg_price.toFixed(2)}</p>
                  </div>

                  <div>
                    <p style={statLabel}>Total spent</p>
                    <p style={{ margin: '4px 0 0', fontSize: '16px', fontWeight: 700, fontFamily: 'var(--font-mono)', color: 'var(--stamp-gold)' }}>${item.total_spent.toFixed(2)}</p>
                  </div>

                  <div>
                    <p style={statLabel}>Last purchase</p>
                    <p style={{ margin: '4px 0 0', fontSize: '13px', fontWeight: 500, color: 'var(--paper)' }}>
                      {daysSince !== null ? `${daysSince} days ago` : 'Unknown'}
                    </p>
                    {item.last_purchase && (
                      <p style={{ margin: '2px 0 0', fontSize: '11px', color: 'var(--muted)' }}>{new Date(item.last_purchase).toLocaleDateString()}</p>
                    )}
                  </div>
                </div>
              </div>
            );
          })}
        </div>
      </div>

      {items.length === 0 && (
        <Card style={{ textAlign: 'center', padding: 40 }}>
          <p style={{ margin: 0, fontSize: '14px', color: 'var(--muted)' }}>
            No recurring items found. Items appear here after being purchased multiple times.
          </p>
        </Card>
      )}
    </div>
  );
};

export default Recurring;
