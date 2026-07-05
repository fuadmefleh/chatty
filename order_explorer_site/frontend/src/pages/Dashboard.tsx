import React, { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import { api } from '../api';
import { BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer, CartesianGrid, LineChart, Line } from 'recharts';
import PageHeader from '../components/ui/PageHeader';
import Card from '../components/ui/Card';
import StatCard from '../components/ui/StatCard';
import Badge from '../components/ui/Badge';
import Spinner from '../components/ui/Spinner';
import EmptyState from '../components/ui/EmptyState';
import ResponsiveTable from '../components/ui/ResponsiveTable';
import type { TableColumn } from '../components/ui/ResponsiveTable';

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

// Light-mode hex equivalents of the design tokens, for recharts (SVG props don't read CSS vars reliably).
const CHART_GRID = '#dfe3e1';
const CHART_AXIS = { fontSize: 12, fill: '#6b7478' };
const CHART_TOOLTIP_STYLE = { background: '#ffffff', border: '1px solid #dfe3e1', borderRadius: 8, color: '#12181b' };
const CHART_AMBER = '#a8631f';
const CHART_SIGNAL = '#1e6e64';

const sectionTitle = 'mb-4 font-mono text-[13px] uppercase tracking-wider text-muted';

const Dashboard: React.FC = () => {
  const [stats, setStats] = useState<DashboardStats | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(false);

  useEffect(() => {
    api.get<DashboardStats>('/dashboard')
      .then(response => {
        setStats(response.data);
        setLoading(false);
      })
      .catch(err => {
        console.error('Failed to load dashboard', err);
        setError(true);
        setLoading(false);
      });
  }, []);

  const orderColumns: TableColumn<DashboardStats['recent_orders'][number]>[] = [
    { key: 'date', header: 'Date', primary: true, render: (o) => <span className="font-mono text-[13px]">{o.date}</span> },
    { key: 'source', header: 'Source', render: (o) => <Badge tone="gold">{o.source}</Badge> },
    { key: 'original_id', header: 'Order ID', render: (o) => <span className="font-mono text-xs text-muted">{o.original_id}</span> },
    { key: 'details', header: 'Details', render: (o) => <span className="text-[13.5px] text-ink-dim">{o.items_summary}</span> },
    { key: 'total', header: 'Total', className: 'text-right', render: (o) => <span className="font-mono font-bold">${o.total.toFixed(2)}</span> },
  ];

  if (loading) {
    return (
      <div className="mx-auto max-w-[1100px] px-4 pb-12 pt-6 md:px-6">
        <Spinner label="Loading dashboard…" />
      </div>
    );
  }
  if (error || !stats) {
    return (
      <div className="mx-auto max-w-[1100px] px-4 pb-12 pt-6 md:px-6">
        <EmptyState title="Failed to load dashboard" description="Something went wrong fetching order stats. Try refreshing the page." />
      </div>
    );
  }

  return (
    <div className="mx-auto max-w-[1100px] px-4 pb-12 pt-6 md:px-6">
      <PageHeader eyebrow="Ledger / Dashboard" title="Order dashboard" />

      {/* Summary Cards */}
      <div className="mb-7 grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
        <StatCard label="This month" value={`$${stats.total_spending.month.toFixed(2)}`} detail={`${stats.order_counts.month} orders`} tone="amber" />
        <StatCard label="This year" value={`$${stats.total_spending.year.toFixed(2)}`} detail={`${stats.order_counts.year} orders`} tone="neutral" />
        <StatCard label="All time" value={`$${stats.total_spending.all_time.toFixed(2)}`} detail={`${stats.order_counts.all_time} orders`} tone="neutral" />
        <StatCard label="Avg order value" value={`$${stats.avg_order_value.toFixed(2)}`} tone="red" />
      </div>

      {/* Most Expensive Purchase This Month */}
      {stats.most_expensive_month && (
        <Card className="mb-7 border-l-[3px] border-l-alert-amber">
          <h2 className={sectionTitle}>Most expensive purchase this month</h2>
          <p className="m-0 font-mono text-xl font-bold text-alert-amber">
            ${stats.most_expensive_month.total.toFixed(2)}
          </p>
          <p className="mt-1.5 text-[13px] text-muted">
            {stats.most_expensive_month.source} · {stats.most_expensive_month.date} · {stats.most_expensive_month.items_summary}
          </p>
        </Card>
      )}

      {/* Spending Trend */}
      <Card className="mb-7">
        <h2 className={sectionTitle}>Spending trend (last 6 months)</h2>
        <div className="h-[300px]">
          <ResponsiveContainer width="100%" height="100%">
            <LineChart data={stats.spending_trend}>
              <CartesianGrid strokeDasharray="3 3" stroke={CHART_GRID} />
              <XAxis dataKey="month" tick={CHART_AXIS} />
              <YAxis tick={CHART_AXIS} />
              <Tooltip
                formatter={(value: unknown) => `$${Number(value).toFixed(2)}`}
                contentStyle={CHART_TOOLTIP_STYLE}
              />
              <Line type="monotone" dataKey="total" stroke={CHART_AMBER} strokeWidth={2.5} dot={{ fill: CHART_AMBER, r: 3 }} />
            </LineChart>
          </ResponsiveContainer>
        </div>
      </Card>

      <div className="mb-7 grid grid-cols-1 gap-5 lg:grid-cols-2">
        {/* Most Purchased Products */}
        <Card>
          <h2 className={sectionTitle}>Most purchased products</h2>
          <div className="flex max-h-[380px] flex-col gap-2 overflow-y-auto">
            {stats.most_purchased.map((item, idx) => (
              <Link
                key={idx}
                to={`/items/${encodeURIComponent(item.name)}`}
                className="block rounded-lg border border-line bg-bg px-3.5 py-2.5"
              >
                <div className="flex items-center justify-between">
                  <div>
                    <p className="m-0 text-sm font-semibold text-ink">{item.name}</p>
                    <p className="mt-1 text-xs text-muted">
                      {item.category} · Avg ${item.avg_price.toFixed(2)}
                    </p>
                  </div>
                  <Badge tone="gold">{item.quantity}</Badge>
                </div>
              </Link>
            ))}
          </div>
        </Card>

        {/* Top Categories */}
        <Card>
          <h2 className={sectionTitle}>Top categories by spending</h2>
          <div className="h-[350px]">
            <ResponsiveContainer width="100%" height="100%">
              <BarChart data={stats.top_categories} layout="vertical">
                <CartesianGrid strokeDasharray="3 3" stroke={CHART_GRID} />
                <XAxis type="number" tick={CHART_AXIS} />
                <YAxis dataKey="category" type="category" width={120} tick={CHART_AXIS} />
                <Tooltip
                  formatter={(value: unknown) => `$${Number(value).toFixed(2)}`}
                  contentStyle={CHART_TOOLTIP_STYLE}
                />
                <Bar dataKey="total" fill={CHART_SIGNAL} radius={[0, 4, 4, 0]} />
              </BarChart>
            </ResponsiveContainer>
          </div>
        </Card>
      </div>

      {/* Recent Orders */}
      <Card>
        <h2 className={sectionTitle}>Recent orders</h2>
        <ResponsiveTable
          columns={orderColumns}
          rows={stats.recent_orders}
          rowKey={(o) => o.id}
          emptyTitle="No recent orders"
        />
        <div className="mt-4 text-center">
          <Link to="/orders" className="text-[13px] font-semibold text-signal">
            View all orders →
          </Link>
        </div>
      </Card>
    </div>
  );
};

export default Dashboard;
