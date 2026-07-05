import React, { useEffect, useState } from 'react';
import { api } from '../api';
import { BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer, CartesianGrid, PieChart, Pie, Cell, Legend } from 'recharts';
import type { PieLabelRenderProps } from 'recharts';
import PageHeader from '../components/ui/PageHeader';
import Card from '../components/ui/Card';
import Spinner from '../components/ui/Spinner';
import ResponsiveTable from '../components/ui/ResponsiveTable';
import type { TableColumn } from '../components/ui/ResponsiveTable';

interface VendorData {
  vendor: string;
  total_spending: number;
  order_count: number;
  item_count: number;
  avg_order_value: number;
  top_categories: Array<{
    category: string;
    total: number;
  }>;
}

interface VendorAnalysis {
  vendors: VendorData[];
  total_vendors: number;
}

const COLORS = ['#c89b3c', '#4fa8a0', '#d8603f', '#e8c478', '#6ea87a'];
const AXIS = { fontSize: 12, fill: '#8b8f92' };
const TOOLTIP_STYLE = { background: '#1b2026', border: '1px solid #262c33', borderRadius: 8, color: '#e9e6dd' };

const pieShareLabel = (props: PieLabelRenderProps) => {
  const { name, percent } = props as unknown as { name: string; percent: number };
  return `${name}: ${(percent * 100).toFixed(0)}%`;
};

const Vendors: React.FC = () => {
  const [data, setData] = useState<VendorAnalysis | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    api.get<VendorAnalysis>('/vendors')
      .then(response => {
        setData(response.data);
        setLoading(false);
      })
      .catch(err => {
        console.error('Failed to load vendor analysis', err);
        setLoading(false);
      });
  }, []);

  if (loading) {
    return (
      <div className="mx-auto max-w-[1200px] px-4 py-6 md:px-6">
        <Spinner label="Loading vendors…" />
      </div>
    );
  }
  if (!data) {
    return (
      <div className="mx-auto max-w-[1200px] px-4 py-6 md:px-6">
        <p className="text-muted">Failed to load vendors</p>
      </div>
    );
  }

  const columns: TableColumn<VendorData>[] = [
    { key: 'vendor', header: 'Vendor', primary: true, render: (v) => <span className="font-bold text-ink">{v.vendor}</span> },
    {
      key: 'total_spending',
      header: 'Total spending',
      className: 'text-right',
      render: (v) => <span className="font-mono text-base font-bold text-alert-amber">${v.total_spending.toFixed(2)}</span>,
    },
    { key: 'order_count', header: 'Orders', className: 'text-center', render: (v) => <span className="text-ink-dim">{v.order_count}</span> },
    { key: 'item_count', header: 'Items', className: 'text-center', render: (v) => <span className="text-ink-dim">{v.item_count}</span> },
    {
      key: 'avg_order_value',
      header: 'Avg order value',
      className: 'text-right',
      render: (v) => <span className="font-mono text-sm text-muted">${v.avg_order_value.toFixed(2)}</span>,
    },
  ];

  return (
    <div className="mx-auto max-w-[1200px] px-4 py-6 md:px-6">
      <PageHeader eyebrow="Ledger / Vendors" title="Vendor analysis" />

      {/* Summary Cards */}
      <div className="mb-7 grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3">
        {data.vendors.map((vendor, idx) => (
          <Card key={vendor.vendor}>
            <h3 className="mb-2.5 text-base font-bold text-ink">{vendor.vendor}</h3>
            <p className="m-0 font-mono text-2xl font-bold" style={{ color: COLORS[idx % COLORS.length] }}>
              ${vendor.total_spending.toFixed(2)}
            </p>
            <p className="mt-1.5 text-sm text-muted">{vendor.order_count} orders · {vendor.item_count} items</p>
            <p className="mt-0.5 text-sm text-muted">Avg ${vendor.avg_order_value.toFixed(2)}/order</p>
          </Card>
        ))}
      </div>

      {/* Charts */}
      <div className="mb-7 grid grid-cols-1 gap-5 md:grid-cols-2">
        <Card>
          <h2 className="mb-4 font-mono text-xs uppercase tracking-wider text-muted">Total spending by vendor</h2>
          <div className="h-72">
            <ResponsiveContainer width="100%" height="100%">
              <BarChart data={data.vendors}>
                <CartesianGrid strokeDasharray="3 3" stroke="#262c33" />
                <XAxis dataKey="vendor" tick={AXIS} />
                <YAxis tick={AXIS} />
                <Tooltip formatter={(value: unknown) => `$${Number(value).toFixed(2)}`} contentStyle={TOOLTIP_STYLE} />
                <Bar dataKey="total_spending" fill="#c89b3c" radius={[4, 4, 0, 0]} />
              </BarChart>
            </ResponsiveContainer>
          </div>
        </Card>

        <Card>
          <h2 className="mb-4 font-mono text-xs uppercase tracking-wider text-muted">Order distribution</h2>
          <div className="h-72">
            <ResponsiveContainer width="100%" height="100%">
              <PieChart>
                <Pie
                  data={data.vendors.map(v => ({ name: v.vendor, value: v.order_count }))}
                  cx="50%"
                  cy="50%"
                  labelLine={false}
                  label={pieShareLabel}
                  outerRadius={100}
                  dataKey="value"
                >
                  {data.vendors.map((_entry, index) => (
                    <Cell key={`cell-${index}`} fill={COLORS[index % COLORS.length]} />
                  ))}
                </Pie>
                <Tooltip contentStyle={TOOLTIP_STYLE} />
                <Legend wrapperStyle={{ fontSize: 12, color: '#8b8f92' }} />
              </PieChart>
            </ResponsiveContainer>
          </div>
        </Card>
      </div>

      {/* Vendor Comparison Table */}
      <h2 className="mb-4 font-mono text-xs uppercase tracking-wider text-muted">Vendor comparison</h2>
      <ResponsiveTable
        columns={columns}
        rows={data.vendors}
        rowKey={(v) => v.vendor}
        emptyTitle="No vendors yet"
        expandedContent={(vendor) => (
          <div>
            <h4 className="mb-3 font-mono text-xs uppercase tracking-wider text-muted">Top categories at {vendor.vendor}</h4>
            <div className="grid grid-cols-1 gap-2.5 sm:grid-cols-2 lg:grid-cols-3">
              {vendor.top_categories.map((cat, catIdx) => (
                <div key={catIdx} className="flex items-center justify-between rounded-lg border border-line bg-surface-dim px-3 py-2.5">
                  <span className="text-sm font-semibold text-ink">{cat.category}</span>
                  <span className="font-mono font-bold text-alert-amber">${cat.total.toFixed(2)}</span>
                </div>
              ))}
            </div>
          </div>
        )}
      />

      {/* Insights Section */}
      <Card className="mt-7">
        <h2 className="mb-4 font-mono text-xs uppercase tracking-wider text-muted">Insights</h2>
        <div className="flex flex-col gap-2.5">
          {data.vendors.length > 0 && (
            <>
              <div className="rounded-lg border-l-[3px] border-alert-amber bg-surface-dim px-4 py-3">
                <p className="m-0 text-sm text-ink-dim">
                  <strong className="text-ink">{data.vendors[0].vendor}</strong> is your most used vendor with ${data.vendors[0].total_spending.toFixed(2)} in total spending.
                </p>
              </div>
              {data.vendors.length > 1 && (
                <div className="rounded-lg border-l-[3px] border-signal bg-surface-dim px-4 py-3">
                  <p className="m-0 text-sm text-ink-dim">
                    Your average order value is highest at <strong className="text-ink">{data.vendors.reduce((max, v) => v.avg_order_value > max.avg_order_value ? v : max).vendor}</strong>
                    {' '}(${data.vendors.reduce((max, v) => v.avg_order_value > max.avg_order_value ? v : max).avg_order_value.toFixed(2)}/order).
                  </p>
                </div>
              )}
              <div className="rounded-lg border-l-[3px] border-alert-red bg-surface-dim px-4 py-3">
                <p className="m-0 text-sm text-ink-dim">
                  You've placed a total of <strong className="text-ink">{data.vendors.reduce((sum, v) => sum + v.order_count, 0)} orders</strong> across all vendors.
                </p>
              </div>
            </>
          )}
        </div>
      </Card>
    </div>
  );
};

export default Vendors;
