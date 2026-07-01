import React, { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import axios from 'axios';
import { BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer, CartesianGrid, LineChart, Line } from 'recharts';
import PageHeader from '../components/ui/PageHeader';
import Card from '../components/ui/Card';

interface DashboardStats {
  total_spending: {
    month: number;
    year: number;
    all_time: number;
  };
  order_counts: {
    month: number;
    year: number;
    all_time: number;
  };
  most_expensive_month: {
    id: string;
    original_id: string;
    date: string;
    total: number;
    source: string;
    items_summary: string;
  } | null;
  avg_order_value: number;
  most_purchased: Array<{
    name: string;
    quantity: number;
    category: string;
    avg_price: number;
  }>;
  top_categories: Array<{
    category: string;
    total: number;
  }>;
  spending_trend: Array<{
    month: string;
    total: number;
  }>;
  recent_orders: Array<{
    id: string;
    original_id: string;
    date: string;
    total: number;
    source: string;
    items_summary: string;
  }>;
}

const statLabel: React.CSSProperties = { margin: 0, fontSize: '11px', color: 'var(--muted)', fontFamily: 'var(--font-mono)', textTransform: 'uppercase', letterSpacing: '0.04em' };
const AXIS = { fontSize: 12, fill: '#8b8f92' };

const Dashboard: React.FC = () => {
  const [stats, setStats] = useState<DashboardStats | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    axios.get<DashboardStats>('http://localhost:8015/dashboard')
      .then(response => {
        setStats(response.data);
        setLoading(false);
      })
      .catch(err => {
        console.error('Failed to load dashboard', err);
        setLoading(false);
      });
  }, []);

  if (loading) return <div style={{ padding: 24, color: 'var(--muted)' }}>Loading dashboard…</div>;
  if (!stats) return <div style={{ padding: 24, color: 'var(--muted)' }}>Failed to load dashboard</div>;

  return (
    <div style={{ padding: '24px 24px 48px' }}>
      <PageHeader eyebrow="Ledger / Dashboard" title="Order dashboard" />

      {/* Summary Cards */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(220px, 1fr))', gap: '16px', marginBottom: '28px' }}>
        <Card>
          <h3 style={statLabel}>This month</h3>
          <p style={{ margin: '10px 0 0', fontSize: '30px', fontWeight: 700, fontFamily: 'var(--font-mono)', color: 'var(--stamp-gold)' }}>${stats.total_spending.month.toFixed(2)}</p>
          <p style={{ margin: '4px 0 0', fontSize: '13px', color: 'var(--muted)' }}>{stats.order_counts.month} orders</p>
        </Card>
        <Card>
          <h3 style={statLabel}>This year</h3>
          <p style={{ margin: '10px 0 0', fontSize: '30px', fontWeight: 700, fontFamily: 'var(--font-mono)', color: 'var(--paper)' }}>${stats.total_spending.year.toFixed(2)}</p>
          <p style={{ margin: '4px 0 0', fontSize: '13px', color: 'var(--muted)' }}>{stats.order_counts.year} orders</p>
        </Card>
        <Card>
          <h3 style={statLabel}>All time</h3>
          <p style={{ margin: '10px 0 0', fontSize: '30px', fontWeight: 700, fontFamily: 'var(--font-mono)', color: 'var(--paper-dim)' }}>${stats.total_spending.all_time.toFixed(2)}</p>
          <p style={{ margin: '4px 0 0', fontSize: '13px', color: 'var(--muted)' }}>{stats.order_counts.all_time} orders</p>
        </Card>
        <Card>
          <h3 style={statLabel}>Avg order value</h3>
          <p style={{ margin: '10px 0 0', fontSize: '30px', fontWeight: 700, fontFamily: 'var(--font-mono)', color: 'var(--stamp-ember)' }}>${stats.avg_order_value.toFixed(2)}</p>
        </Card>
      </div>

      {/* Most Expensive Purchase This Month */}
      {stats.most_expensive_month && (
        <Card style={{ marginBottom: '28px', borderLeft: '3px solid var(--stamp-gold)' }}>
          <h2 style={{ fontSize: 13, fontFamily: 'var(--font-mono)', letterSpacing: '0.06em', textTransform: 'uppercase', marginBottom: 12, color: 'var(--muted)' }}>Most expensive purchase this month</h2>
          <p style={{ margin: 0, fontSize: '20px', fontWeight: 700, fontFamily: 'var(--font-mono)', color: 'var(--stamp-gold)' }}>
            ${stats.most_expensive_month.total.toFixed(2)}
          </p>
          <p style={{ margin: '6px 0 0 0', fontSize: '13px', color: 'var(--muted)' }}>
            {stats.most_expensive_month.source} · {stats.most_expensive_month.date} · {stats.most_expensive_month.items_summary}
          </p>
        </Card>
      )}

      {/* Spending Trend */}
      <Card style={{ marginBottom: '28px' }}>
        <h2 style={{ fontSize: 13, fontFamily: 'var(--font-mono)', letterSpacing: '0.06em', textTransform: 'uppercase', marginBottom: 16, color: 'var(--muted)' }}>Spending trend (last 6 months)</h2>
        <div style={{ height: '300px' }}>
          <ResponsiveContainer width="100%" height="100%">
            <LineChart data={stats.spending_trend}>
              <CartesianGrid strokeDasharray="3 3" stroke="#262c33" />
              <XAxis dataKey="month" tick={AXIS} />
              <YAxis tick={AXIS} />
              <Tooltip
                formatter={(value: any) => `$${value.toFixed(2)}`}
                contentStyle={{ background: '#1b2026', border: '1px solid #262c33', borderRadius: 8, color: '#e9e6dd' }}
              />
              <Line type="monotone" dataKey="total" stroke="#c89b3c" strokeWidth={2.5} dot={{ fill: '#c89b3c', r: 3 }} />
            </LineChart>
          </ResponsiveContainer>
        </div>
      </Card>

      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(380px, 1fr))', gap: '20px', marginBottom: '28px' }}>
        {/* Most Purchased Products */}
        <Card>
          <h2 style={{ fontSize: 13, fontFamily: 'var(--font-mono)', letterSpacing: '0.06em', textTransform: 'uppercase', marginBottom: 16, color: 'var(--muted)' }}>Most purchased products</h2>
          <div style={{ maxHeight: '380px', overflowY: 'auto', display: 'flex', flexDirection: 'column', gap: 8 }}>
            {stats.most_purchased.map((item, idx) => (
              <Link
                key={idx}
                to={`/items/${encodeURIComponent(item.name)}`}
                style={{
                  display: 'block',
                  padding: '11px 14px',
                  background: 'var(--ink-900)',
                  borderRadius: '8px',
                  border: '1px solid var(--ink-700)',
                }}
              >
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                  <div>
                    <p style={{ margin: 0, fontWeight: 600, color: 'var(--paper)', fontSize: 14 }}>{item.name}</p>
                    <p style={{ margin: '4px 0 0 0', fontSize: '12px', color: 'var(--muted)' }}>
                      {item.category} · Avg ${item.avg_price.toFixed(2)}
                    </p>
                  </div>
                  <div style={{
                    background: 'rgba(200, 155, 60, 0.15)',
                    color: 'var(--stamp-gold)',
                    padding: '5px 12px',
                    borderRadius: '20px',
                    fontWeight: 700,
                    fontSize: '13px',
                    fontFamily: 'var(--font-mono)',
                  }}>
                    {item.quantity}
                  </div>
                </div>
              </Link>
            ))}
          </div>
        </Card>

        {/* Top Categories */}
        <Card>
          <h2 style={{ fontSize: 13, fontFamily: 'var(--font-mono)', letterSpacing: '0.06em', textTransform: 'uppercase', marginBottom: 16, color: 'var(--muted)' }}>Top categories by spending</h2>
          <div style={{ height: '350px' }}>
            <ResponsiveContainer width="100%" height="100%">
              <BarChart data={stats.top_categories} layout="vertical">
                <CartesianGrid strokeDasharray="3 3" stroke="#262c33" />
                <XAxis type="number" tick={AXIS} />
                <YAxis dataKey="category" type="category" width={120} tick={AXIS} />
                <Tooltip
                  formatter={(value: any) => `$${value.toFixed(2)}`}
                  contentStyle={{ background: '#1b2026', border: '1px solid #262c33', borderRadius: 8, color: '#e9e6dd' }}
                />
                <Bar dataKey="total" fill="#4fa8a0" radius={[0, 4, 4, 0]} />
              </BarChart>
            </ResponsiveContainer>
          </div>
        </Card>
      </div>

      {/* Recent Orders */}
      <Card>
        <h2 style={{ fontSize: 13, fontFamily: 'var(--font-mono)', letterSpacing: '0.06em', textTransform: 'uppercase', marginBottom: 16, color: 'var(--muted)' }}>Recent orders</h2>
        <table style={{ width: '100%', borderCollapse: 'collapse' }}>
          <thead>
            <tr style={{ borderBottom: '1px solid var(--ink-700)' }}>
              <th style={{ padding: '10px 12px', textAlign: 'left', color: 'var(--muted)', fontWeight: 600, fontSize: 11, fontFamily: 'var(--font-mono)', textTransform: 'uppercase' }}>Date</th>
              <th style={{ padding: '10px 12px', textAlign: 'left', color: 'var(--muted)', fontWeight: 600, fontSize: 11, fontFamily: 'var(--font-mono)', textTransform: 'uppercase' }}>Source</th>
              <th style={{ padding: '10px 12px', textAlign: 'left', color: 'var(--muted)', fontWeight: 600, fontSize: 11, fontFamily: 'var(--font-mono)', textTransform: 'uppercase' }}>Order ID</th>
              <th style={{ padding: '10px 12px', textAlign: 'left', color: 'var(--muted)', fontWeight: 600, fontSize: 11, fontFamily: 'var(--font-mono)', textTransform: 'uppercase' }}>Details</th>
              <th style={{ padding: '10px 12px', textAlign: 'right', color: 'var(--muted)', fontWeight: 600, fontSize: 11, fontFamily: 'var(--font-mono)', textTransform: 'uppercase' }}>Total</th>
            </tr>
          </thead>
          <tbody>
            {stats.recent_orders.map((order) => (
              <tr key={order.id} style={{ borderBottom: '1px solid var(--ink-700)' }}>
                <td style={{ padding: '12px', fontFamily: 'var(--font-mono)', fontSize: 13, color: 'var(--paper)' }}>{order.date}</td>
                <td style={{ padding: '12px' }}>
                  <span style={{ background: 'rgba(200, 155, 60, 0.15)', color: 'var(--stamp-gold)', padding: '3px 9px', borderRadius: '12px', fontSize: '12px', fontWeight: 600 }}>
                    {order.source}
                  </span>
                </td>
                <td style={{ padding: '12px', fontSize: '12px', fontFamily: 'var(--font-mono)', color: 'var(--muted)' }}>{order.original_id}</td>
                <td style={{ padding: '12px', fontSize: '13.5px', color: 'var(--paper-dim)' }}>{order.items_summary}</td>
                <td style={{ padding: '12px', textAlign: 'right', fontWeight: 700, fontFamily: 'var(--font-mono)', color: 'var(--paper)' }}>
                  ${order.total.toFixed(2)}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
        <div style={{ marginTop: '16px', textAlign: 'center' }}>
          <Link to="/orders" style={{ color: 'var(--stamp-teal)', fontWeight: 600, fontSize: '13px' }}>
            View all orders →
          </Link>
        </div>
      </Card>
    </div>
  );
};

export default Dashboard;
