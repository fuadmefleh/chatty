import React, { useEffect, useState } from 'react';
import { api } from '../api';
import { PieChart, Pie, Cell, ResponsiveContainer, Tooltip, Legend, BarChart, Bar, XAxis, YAxis, CartesianGrid } from 'recharts';
import type { PieLabelRenderProps } from 'recharts';
import PageHeader from '../components/ui/PageHeader';
import Card from '../components/ui/Card';
import Spinner from '../components/ui/Spinner';
import ResponsiveTable from '../components/ui/ResponsiveTable';
import type { TableColumn } from '../components/ui/ResponsiveTable';

interface CategoryData {
  category: string;
  total_spending: number;
  item_count: number;
  order_count: number;
  avg_price: number;
  sources: Record<string, number>;
  monthly_trend: Array<{
    month: string;
    total: number;
  }>;
}

interface CategoryAnalysis {
  categories: CategoryData[];
  total_categories: number;
  top_category: CategoryData | null;
}

const COLORS = ['#c89b3c', '#4fa8a0', '#d8603f', '#e8c478', '#6ea87a', '#8f7fd6', '#4a90c4', '#b6588c', '#a67c9c', '#7fa66b'];
const AXIS = { fontSize: 12, fill: '#8b8f92' };
const TOOLTIP_STYLE = { background: '#1b2026', border: '1px solid #262c33', borderRadius: 8, color: '#e9e6dd' };

const pieShareLabel = (props: PieLabelRenderProps) => {
  const { name, percent } = props as unknown as { name: string; percent: number };
  return `${name}: ${(percent * 100).toFixed(0)}%`;
};

const Categories: React.FC = () => {
  const [data, setData] = useState<CategoryAnalysis | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    api.get<CategoryAnalysis>('/categories')
      .then(response => {
        setData(response.data);
        setLoading(false);
      })
      .catch(err => {
        console.error('Failed to load category analysis', err);
        setLoading(false);
      });
  }, []);

  if (loading) {
    return (
      <div className="mx-auto max-w-[1200px] px-4 py-6 md:px-6">
        <Spinner label="Loading categories…" />
      </div>
    );
  }
  if (!data) {
    return (
      <div className="mx-auto max-w-[1200px] px-4 py-6 md:px-6">
        <p className="text-muted">Failed to load categories</p>
      </div>
    );
  }

  const pieData = data.categories.map(cat => ({
    name: cat.category,
    value: cat.total_spending
  }));

  const columns: TableColumn<CategoryData>[] = [
    { key: 'category', header: 'Category', primary: true, render: (c) => <span className="font-bold text-ink">{c.category}</span> },
    {
      key: 'total_spending',
      header: 'Total spending',
      className: 'text-right',
      render: (c) => <span className="font-mono text-base font-bold text-alert-amber">${c.total_spending.toFixed(2)}</span>,
    },
    { key: 'item_count', header: 'Items', className: 'text-center', render: (c) => <span className="text-ink-dim">{c.item_count}</span> },
    { key: 'order_count', header: 'Orders', className: 'text-center', render: (c) => <span className="text-ink-dim">{c.order_count}</span> },
    {
      key: 'avg_price',
      header: 'Avg price',
      className: 'text-right',
      render: (c) => <span className="font-mono text-sm text-muted">${c.avg_price.toFixed(2)}</span>,
    },
  ];

  return (
    <div className="mx-auto max-w-[1200px] px-4 py-6 md:px-6">
      <PageHeader eyebrow="Ledger / Categories" title="Category analysis" />

      {/* Summary Cards */}
      <div className="mb-7 grid grid-cols-1 gap-4 sm:grid-cols-3">
        <Card>
          <h3 className="m-0 font-mono text-[11px] uppercase tracking-wider text-muted">Total categories</h3>
          <p className="mt-2.5 font-mono text-3xl font-bold text-alert-amber">{data.total_categories}</p>
        </Card>

        {data.top_category && (
          <>
            <Card>
              <h3 className="m-0 font-mono text-[11px] uppercase tracking-wider text-muted">Top category</h3>
              <p className="mt-2.5 text-xl font-bold text-ink">{data.top_category.category}</p>
              <p className="mt-1 text-sm text-muted">${data.top_category.total_spending.toFixed(2)}</p>
            </Card>

            <Card>
              <h3 className="m-0 font-mono text-[11px] uppercase tracking-wider text-muted">Top category items</h3>
              <p className="mt-2.5 font-mono text-3xl font-bold text-alert-red">{data.top_category.item_count}</p>
            </Card>
          </>
        )}
      </div>

      {/* Charts */}
      <div className="mb-7 grid grid-cols-1 gap-5 md:grid-cols-2">
        <Card>
          <h2 className="mb-4 font-mono text-xs uppercase tracking-wider text-muted">Spending distribution</h2>
          <div className="h-80">
            <ResponsiveContainer width="100%" height="100%">
              <PieChart>
                <Pie
                  data={pieData}
                  cx="50%"
                  cy="50%"
                  labelLine={false}
                  label={pieShareLabel}
                  outerRadius={100}
                  dataKey="value"
                >
                  {pieData.map((_entry, index) => (
                    <Cell key={`cell-${index}`} fill={COLORS[index % COLORS.length]} />
                  ))}
                </Pie>
                <Tooltip formatter={(value: unknown) => `$${Number(value).toFixed(2)}`} contentStyle={TOOLTIP_STYLE} />
                <Legend wrapperStyle={{ fontSize: 12, color: '#8b8f92' }} />
              </PieChart>
            </ResponsiveContainer>
          </div>
        </Card>

        <Card>
          <h2 className="mb-4 font-mono text-xs uppercase tracking-wider text-muted">Top categories by spending</h2>
          <div className="h-80">
            <ResponsiveContainer width="100%" height="100%">
              <BarChart data={data.categories.slice(0, 10)}>
                <CartesianGrid strokeDasharray="3 3" stroke="#262c33" />
                <XAxis dataKey="category" angle={-45} textAnchor="end" height={100} tick={AXIS} />
                <YAxis tick={AXIS} />
                <Tooltip formatter={(value: unknown) => `$${Number(value).toFixed(2)}`} contentStyle={TOOLTIP_STYLE} />
                <Bar dataKey="total_spending" fill="#c89b3c" radius={[4, 4, 0, 0]} />
              </BarChart>
            </ResponsiveContainer>
          </div>
        </Card>
      </div>

      {/* Category Details Table */}
      <h2 className="mb-4 font-mono text-xs uppercase tracking-wider text-muted">Category details</h2>
      <ResponsiveTable
        columns={columns}
        rows={data.categories}
        rowKey={(c) => c.category}
        emptyTitle="No categories yet"
        expandedContent={(cat) => (
          <div className="grid grid-cols-1 gap-5 md:grid-cols-2">
            <div>
              <h4 className="mb-2.5 font-mono text-xs uppercase tracking-wider text-muted">Purchase sources</h4>
              <div className="flex flex-col gap-2">
                {Object.entries(cat.sources).map(([source, count]) => (
                  <div key={source} className="flex items-center justify-between rounded-md bg-surface-dim px-3 py-2.5">
                    <span className="text-sm font-semibold text-ink">{source}</span>
                    <span className="text-sm text-muted">{count} orders</span>
                  </div>
                ))}
              </div>
            </div>

            <div>
              <h4 className="mb-2.5 font-mono text-xs uppercase tracking-wider text-muted">Monthly trend</h4>
              <div className="h-48">
                <ResponsiveContainer width="100%" height="100%">
                  <BarChart data={cat.monthly_trend.slice(-6)}>
                    <CartesianGrid strokeDasharray="3 3" stroke="#262c33" />
                    <XAxis dataKey="month" tick={AXIS} />
                    <YAxis tick={AXIS} />
                    <Tooltip formatter={(value: unknown) => `$${Number(value).toFixed(2)}`} contentStyle={TOOLTIP_STYLE} />
                    <Bar dataKey="total" fill="#4fa8a0" radius={[4, 4, 0, 0]} />
                  </BarChart>
                </ResponsiveContainer>
              </div>
            </div>
          </div>
        )}
      />
    </div>
  );
};

export default Categories;
