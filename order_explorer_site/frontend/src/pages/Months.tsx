import React, { useEffect, useState, useCallback } from 'react';
import { api } from '../api';
import { BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer, CartesianGrid, PieChart, Pie, Cell } from 'recharts';
import type { PieLabelRenderProps } from 'recharts';
import { Link } from 'react-router-dom';
import PageHeader from '../components/ui/PageHeader';
import Card from '../components/ui/Card';
import Badge from '../components/ui/Badge';
import Spinner from '../components/ui/Spinner';
import ResponsiveTable from '../components/ui/ResponsiveTable';
import type { TableColumn } from '../components/ui/ResponsiveTable';

interface MonthlyData {
  month: string;
  total_spending: number;
  order_count: number;
  item_count: number;
  avg_order_value: number;
  top_category: string;
  top_category_spending: number;
  sources: Record<string, number>;
  top_categories: Array<{
    category: string;
    total: number;
  }>;
}

interface Order {
  id: string;
  original_id: string;
  date: string;
  total: number;
  source: string;
  items_summary: string;
}

interface Item {
  name: string;
  price: number;
  quantity: number;
  total_price: number;
  category: string;
  date: string;
  source: string;
  order_id: string;
}

interface MonthDetails {
  orders: Order[];
  items: Item[];
}

const COLORS = ['#c89b3c', '#4fa8a0', '#d8603f', '#e8c478', '#6ea87a', '#8f7fd6'];
const AXIS = { fontSize: 12, fill: '#8b8f92' };
const TOOLTIP_STYLE = { background: '#1b2026', border: '1px solid #262c33', borderRadius: 8, color: '#e9e6dd' };

const pieCategoryLabel = (props: PieLabelRenderProps) => {
  const { category, total } = props as unknown as { category: string; total: number };
  return `${category}: $${total.toFixed(0)}`;
};

// One order row inside a month's detail panel, with its own line-items expansion
// (no extra fetch needed — the parent already loaded every item for the month).
const OrdersSubTable: React.FC<{ orders: Order[]; items: Item[] }> = ({ orders, items }) => {
  const columns: TableColumn<Order>[] = [
    { key: 'date', header: 'Date', primary: true, render: (o) => <span className="font-mono">{o.date}</span> },
    { key: 'source', header: 'Source', render: (o) => <Badge tone="gold">{o.source}</Badge> },
    {
      key: 'total',
      header: 'Total',
      className: 'text-right',
      render: (o) => <span className="font-mono font-semibold text-ink">${o.total?.toFixed(2)}</span>,
    },
  ];

  return (
    <ResponsiveTable
      columns={columns}
      rows={orders}
      rowKey={(o) => o.id}
      emptyTitle="No orders"
      expandedContent={(o) => {
        const orderItems = items.filter((item) => item.order_id === o.id);
        return (
          <div className="flex flex-col gap-2">
            <div className="font-mono text-[11px] uppercase tracking-wider text-muted">Items in this order</div>
            {orderItems.length > 0 ? (
              orderItems.map((item, itemIdx) => (
                <div key={itemIdx} className="flex items-center justify-between gap-2 rounded-md bg-surface-dim px-2.5 py-2">
                  <div className="flex-1">
                    <Link to={`/items/${encodeURIComponent(item.name)}`} className="font-semibold text-signal hover:underline">
                      {item.name}
                    </Link>
                    <div className="mt-0.5 text-xs text-muted">{item.category}</div>
                  </div>
                  <div className="text-right">
                    <div className="font-mono font-semibold text-ink">${item.price?.toFixed(2)} × {item.quantity}</div>
                    <div className="text-xs text-muted">Total ${item.total_price?.toFixed(2)}</div>
                  </div>
                </div>
              ))
            ) : (
              <p className="text-center text-sm text-muted">No items found.</p>
            )}
          </div>
        );
      }}
    />
  );
};

const MonthDetailPanel: React.FC<{ data: MonthlyData; details?: MonthDetails; loading: boolean }> = ({
  data,
  details,
  loading,
}) => {
  if (loading || !details) {
    return (
      <div className="py-10 text-center">
        <Spinner label="Loading details…" />
      </div>
    );
  }

  const { orders: monthOrders, items: monthItems } = details;

  return (
    <div className="flex flex-col gap-5">
      {/* Summary Cards */}
      <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
        <Card padding={14}>
          <div className="mb-2 font-mono text-[11px] uppercase tracking-wider text-muted">Total spending</div>
          <div className="font-mono text-xl font-bold text-alert-amber">${data.total_spending.toFixed(2)}</div>
        </Card>
        <Card padding={14}>
          <div className="mb-2 font-mono text-[11px] uppercase tracking-wider text-muted">Orders</div>
          <div className="font-mono text-xl font-bold text-signal">{data.order_count}</div>
        </Card>
        <Card padding={14}>
          <div className="mb-2 font-mono text-[11px] uppercase tracking-wider text-muted">Items</div>
          <div className="font-mono text-xl font-bold text-alert-red">{data.item_count}</div>
        </Card>
        <Card padding={14}>
          <div className="mb-2 font-mono text-[11px] uppercase tracking-wider text-muted">Avg order</div>
          <div className="font-mono text-xl font-bold text-ink-dim">${data.avg_order_value.toFixed(2)}</div>
        </Card>
      </div>

      {/* Charts */}
      <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
        <Card padding={14}>
          <h4 className="mb-3 font-mono text-xs uppercase tracking-wider text-muted">Spending by category</h4>
          <div className="h-56">
            <ResponsiveContainer width="100%" height="100%">
              <PieChart>
                <Pie
                  data={data.top_categories}
                  cx="50%"
                  cy="50%"
                  labelLine={false}
                  label={pieCategoryLabel}
                  outerRadius={80}
                  dataKey="total"
                >
                  {data.top_categories.map((_entry, index) => (
                    <Cell key={`cell-${index}`} fill={COLORS[index % COLORS.length]} />
                  ))}
                </Pie>
                <Tooltip formatter={(value: unknown) => `$${Number(value).toFixed(2)}`} contentStyle={TOOLTIP_STYLE} />
              </PieChart>
            </ResponsiveContainer>
          </div>
        </Card>

        <Card padding={14}>
          <h4 className="mb-3 font-mono text-xs uppercase tracking-wider text-muted">Orders by source</h4>
          <div className="h-56">
            <ResponsiveContainer width="100%" height="100%">
              <BarChart data={Object.entries(data.sources).map(([source, count]) => ({ source, count }))}>
                <CartesianGrid strokeDasharray="3 3" stroke="#262c33" />
                <XAxis dataKey="source" tick={AXIS} />
                <YAxis tick={AXIS} />
                <Tooltip contentStyle={TOOLTIP_STYLE} />
                <Bar dataKey="count" fill="#4fa8a0" radius={[4, 4, 0, 0]} />
              </BarChart>
            </ResponsiveContainer>
          </div>
        </Card>
      </div>

      {/* Top Items */}
      <Card padding={14}>
        <h4 className="mb-3 font-mono text-xs uppercase tracking-wider text-muted">Top items this month</h4>
        <div className="flex max-h-[300px] flex-col overflow-y-auto">
          {monthItems
            .sort((a, b) => (b.total_price || 0) - (a.total_price || 0))
            .slice(0, 10)
            .map((item, idx2) => (
              <div key={idx2} className="flex items-center justify-between gap-2 border-b border-line py-2.5 last:border-b-0">
                <div className="flex-1">
                  <Link to={`/items/${encodeURIComponent(item.name)}`} className="text-sm font-semibold text-signal hover:underline">
                    {item.name}
                  </Link>
                  <div className="mt-0.5 text-xs text-muted">{item.category} · {item.source}</div>
                </div>
                <div className="text-right">
                  <div className="font-mono font-semibold text-ink">${item.total_price?.toFixed(2)}</div>
                  <div className="text-xs text-muted">Qty {item.quantity}</div>
                </div>
              </div>
            ))}
        </div>
      </Card>

      {/* Orders List */}
      <Card padding={14}>
        <h4 className="mb-3 font-mono text-xs uppercase tracking-wider text-muted">Orders this month</h4>
        <OrdersSubTable orders={monthOrders} items={monthItems} />
      </Card>
    </div>
  );
};

const Months: React.FC = () => {
  const [monthlyData, setMonthlyData] = useState<MonthlyData[]>([]);
  const [loading, setLoading] = useState(true);
  const [monthDetails, setMonthDetails] = useState<Record<string, MonthDetails>>({});
  const [loadingMonths, setLoadingMonths] = useState<Set<string>>(new Set());

  useEffect(() => {
    api.get<MonthlyData[]>('/months')
      .then(response => {
        setMonthlyData(response.data);
        setLoading(false);
      })
      .catch(err => {
        console.error('Failed to load monthly data', err);
        setLoading(false);
      });
  }, []);

  const ensureMonthDetails = useCallback((month: string) => {
    setMonthDetails(prev => {
      if (prev[month]) return prev;
      setLoadingMonths(cur => new Set(cur).add(month));
      Promise.all([
        api.get<Order[]>('/orders'),
        api.get<Item[]>('/items'),
      ])
        .then(([ordersRes, itemsRes]) => {
          const filteredOrders = ordersRes.data.filter(o => o.date?.startsWith(month));
          const filteredItems = itemsRes.data.filter(i => i.date?.startsWith(month));
          setMonthDetails(cur => ({ ...cur, [month]: { orders: filteredOrders, items: filteredItems } }));
        })
        .catch(err => console.error('Failed to load month details', err))
        .finally(() => {
          setLoadingMonths(cur => {
            const next = new Set(cur);
            next.delete(month);
            return next;
          });
        });
      return prev;
    });
  }, []);

  if (loading) {
    return (
      <div className="mx-auto max-w-[1200px] px-4 py-6 md:px-6">
        <Spinner label="Loading monthly data…" />
      </div>
    );
  }

  const chartData = monthlyData.slice(0, 12).reverse();

  const columns: TableColumn<MonthlyData>[] = [
    { key: 'month', header: 'Month', primary: true, render: (d) => <span className="font-mono font-bold">{d.month}</span> },
    {
      key: 'total_spending',
      header: 'Total spending',
      className: 'text-right',
      render: (d) => <span className="font-mono text-base font-bold text-alert-amber">${d.total_spending.toFixed(2)}</span>,
    },
    {
      key: 'order_count',
      header: 'Orders',
      className: 'text-center',
      render: (d) => <Badge tone="teal">{d.order_count}</Badge>,
    },
    {
      key: 'item_count',
      header: 'Items',
      className: 'text-center',
      render: (d) => <Badge tone="ember">{d.item_count}</Badge>,
    },
    {
      key: 'avg_order_value',
      header: 'Avg order',
      className: 'text-right',
      render: (d) => <span className="font-mono text-sm text-muted">${d.avg_order_value.toFixed(2)}</span>,
    },
    {
      key: 'top_category',
      header: 'Top category',
      render: (d) => (
        <div>
          <div className="text-sm font-semibold text-ink">{d.top_category}</div>
          <div className="text-xs text-muted">${d.top_category_spending.toFixed(2)}</div>
        </div>
      ),
    },
  ];

  return (
    <div className="mx-auto max-w-[1200px] px-4 py-6 md:px-6">
      <PageHeader eyebrow="Ledger / Months" title="Monthly spending analysis" />

      {/* Overview Chart */}
      <Card className="mb-7">
        <h2 className="mb-4 font-mono text-xs uppercase tracking-wider text-muted">Monthly spending trend</h2>
        <div className="h-72">
          <ResponsiveContainer width="100%" height="100%">
            <BarChart data={chartData}>
              <CartesianGrid strokeDasharray="3 3" stroke="#262c33" />
              <XAxis dataKey="month" tick={AXIS} />
              <YAxis tick={AXIS} />
              <Tooltip
                formatter={(value: unknown) => `$${Number(value).toFixed(2)}`}
                labelFormatter={(label) => `Month: ${label}`}
                contentStyle={TOOLTIP_STYLE}
              />
              <Bar dataKey="total_spending" fill="#c89b3c" radius={[4, 4, 0, 0]} />
            </BarChart>
          </ResponsiveContainer>
        </div>
      </Card>

      {/* Monthly Details Table */}
      <ResponsiveTable
        columns={columns}
        rows={monthlyData}
        rowKey={(d) => d.month}
        emptyTitle="No monthly data yet"
        expandedContent={(d) => {
          ensureMonthDetails(d.month);
          return (
            <MonthDetailPanel data={d} details={monthDetails[d.month]} loading={loadingMonths.has(d.month)} />
          );
        }}
      />

      {/* Summary Stats */}
      <div className="mt-7 grid grid-cols-2 gap-4 sm:grid-cols-4">
        <Card className="text-center">
          <div className="mb-2 font-mono text-[11px] uppercase tracking-wider text-muted">Total months</div>
          <div className="font-mono text-2xl font-bold text-alert-amber">{monthlyData.length}</div>
        </Card>
        <Card className="text-center">
          <div className="mb-2 font-mono text-[11px] uppercase tracking-wider text-muted">Highest month</div>
          <div className="font-mono text-xl font-bold text-signal">
            ${monthlyData.length > 0 ? Math.max(...monthlyData.map(m => m.total_spending)).toFixed(2) : '0.00'}
          </div>
          <div className="mt-1 text-xs text-muted">
            {monthlyData.length > 0 ? monthlyData.reduce((max, m) => m.total_spending > max.total_spending ? m : max).month : 'N/A'}
          </div>
        </Card>
        <Card className="text-center">
          <div className="mb-2 font-mono text-[11px] uppercase tracking-wider text-muted">Lowest month</div>
          <div className="font-mono text-xl font-bold text-alert-red">
            ${monthlyData.length > 0 ? Math.min(...monthlyData.map(m => m.total_spending)).toFixed(2) : '0.00'}
          </div>
          <div className="mt-1 text-xs text-muted">
            {monthlyData.length > 0 ? monthlyData.reduce((min, m) => m.total_spending < min.total_spending ? m : min).month : 'N/A'}
          </div>
        </Card>
        <Card className="text-center">
          <div className="mb-2 font-mono text-[11px] uppercase tracking-wider text-muted">Avg per month</div>
          <div className="font-mono text-xl font-bold text-ink-dim">
            ${monthlyData.length > 0 ? (monthlyData.reduce((sum, m) => sum + m.total_spending, 0) / monthlyData.length).toFixed(2) : '0.00'}
          </div>
        </Card>
      </div>
    </div>
  );
};

export default Months;
