import React, { useEffect, useState, useCallback, useMemo } from 'react';
import { api } from '../api';
import { BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer, CartesianGrid, PieChart, Pie, Cell, Legend, LineChart, Line } from 'recharts';
import type { PieLabelRenderProps } from 'recharts';
import { Link } from 'react-router-dom';
import PageHeader from '../components/ui/PageHeader';
import Card from '../components/ui/Card';
import Badge from '../components/ui/Badge';
import Spinner from '../components/ui/Spinner';
import ResponsiveTable from '../components/ui/ResponsiveTable';
import type { TableColumn } from '../components/ui/ResponsiveTable';

interface YearlyData {
  year: string;
  total_spending: number;
  order_count: number;
  item_count: number;
  avg_order_value: number;
  top_category: string;
  top_category_spending: number;
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

interface Order {
  id: string;
  original_id: string;
  date: string;
  total: number;
  source: string;
  items_summary: string;
}

interface YearDetails {
  items: Item[];
  orders: Order[];
}

const COLORS = ['#c89b3c', '#4fa8a0', '#d8603f', '#e8c478', '#6ea87a', '#8f7fd6', '#4a90c4', '#b6588c'];
const AXIS = { fontSize: 12, fill: '#8b8f92' };
const TOOLTIP_STYLE = { background: '#1b2026', border: '1px solid #262c33', borderRadius: 8, color: '#e9e6dd' };

const pieCategoryLabel = (props: PieLabelRenderProps) => {
  const { category, total } = props as unknown as { category: string; total: number };
  return `${category}: $${total.toFixed(0)}`;
};

const getMonthlyBreakdown = (yearOrders: Order[], yearItems: Item[]) => {
  const monthly: Record<string, { month: string; spending: number; orders: number; items: number }> = {};

  yearOrders.forEach(order => {
    const month = order.date?.substring(0, 7) || '';
    if (!monthly[month]) {
      monthly[month] = { month, spending: 0, orders: 0, items: 0 };
    }
    monthly[month].spending += order.total || 0;
    monthly[month].orders += 1;
  });

  yearItems.forEach(item => {
    const month = item.date?.substring(0, 7) || '';
    if (monthly[month]) {
      monthly[month].items += item.quantity || 0;
    }
  });

  return Object.values(monthly).sort((a, b) => a.month.localeCompare(b.month));
};

const getCategoryBreakdown = (yearItems: Item[]) => {
  const categories: Record<string, { category: string; total: number; count: number }> = {};

  yearItems.forEach(item => {
    const cat = item.category || 'Uncategorized';
    if (!categories[cat]) {
      categories[cat] = { category: cat, total: 0, count: 0 };
    }
    categories[cat].total += item.total_price || 0;
    categories[cat].count += item.quantity || 0;
  });

  return Object.values(categories).sort((a, b) => b.total - a.total);
};

const getSourceBreakdown = (yearOrders: Order[]) => {
  const sources: Record<string, { source: string; total: number; orders: number }> = {};

  yearOrders.forEach(order => {
    const src = order.source || 'Unknown';
    if (!sources[src]) {
      sources[src] = { source: src, total: 0, orders: 0 };
    }
    sources[src].total += order.total || 0;
    sources[src].orders += 1;
  });

  return Object.values(sources).sort((a, b) => b.total - a.total);
};

const getTopItems = (yearItems: Item[]) => {
  const itemTotals: Record<string, { name: string; total: number; quantity: number; category: string; avgPrice: number }> = {};

  yearItems.forEach(item => {
    const name = item.name || 'Unknown';
    if (!itemTotals[name]) {
      itemTotals[name] = { name, total: 0, quantity: 0, category: item.category || 'Unknown', avgPrice: 0 };
    }
    itemTotals[name].total += item.total_price || 0;
    itemTotals[name].quantity += item.quantity || 0;
  });

  Object.values(itemTotals).forEach(item => {
    item.avgPrice = item.total / item.quantity;
  });

  return Object.values(itemTotals).sort((a, b) => b.total - a.total).slice(0, 10);
};

const getExpensiveOrders = (yearOrders: Order[]) => {
  return [...yearOrders].sort((a, b) => (b.total || 0) - (a.total || 0)).slice(0, 10);
};

const getWeekdayBreakdown = (yearOrders: Order[]) => {
  const weekdays = ['Sunday', 'Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday'];
  const breakdown: Record<string, { day: string; spending: number; orders: number }> = {};

  weekdays.forEach(day => {
    breakdown[day] = { day, spending: 0, orders: 0 };
  });

  yearOrders.forEach(order => {
    if (order.date) {
      try {
        const date = new Date(order.date);
        const dayName = weekdays[date.getDay()];
        breakdown[dayName].spending += order.total || 0;
        breakdown[dayName].orders += 1;
      } catch {
        // Skip invalid dates
      }
    }
  });

  return weekdays.map(day => breakdown[day]);
};

const sortToggleClass = (active: boolean): string =>
  `rounded-md border px-3 py-1.5 text-xs font-semibold ${
    active ? 'border-transparent bg-alert-amber text-white' : 'border-line text-muted'
  }`;

const YearDetailPanel: React.FC<{ data: YearlyData; details?: YearDetails; loading: boolean }> = ({
  data,
  details,
  loading,
}) => {
  const [sortBy, setSortBy] = useState<'date' | 'price' | 'name'>('price');
  const [sortOrder, setSortOrder] = useState<'asc' | 'desc'>('desc');

  const handleSort = (field: 'date' | 'price' | 'name') => {
    if (sortBy === field) {
      setSortOrder(sortOrder === 'asc' ? 'desc' : 'asc');
    } else {
      setSortBy(field);
      setSortOrder(field === 'price' ? 'desc' : 'asc');
    }
  };

  const yearItems = details?.items ?? [];
  const yearOrders = details?.orders ?? [];

  const sortedItems = useMemo(() => {
    const sorted = [...yearItems];
    sorted.sort((a, b) => {
      let compareA: string | number, compareB: string | number;
      if (sortBy === 'price') {
        compareA = a.total_price || 0;
        compareB = b.total_price || 0;
      } else if (sortBy === 'date') {
        compareA = a.date || '';
        compareB = b.date || '';
      } else {
        compareA = (a.name || '').toLowerCase();
        compareB = (b.name || '').toLowerCase();
      }
      if (compareA < compareB) return sortOrder === 'asc' ? -1 : 1;
      if (compareA > compareB) return sortOrder === 'asc' ? 1 : -1;
      return 0;
    });
    return sorted;
  }, [yearItems, sortBy, sortOrder]);

  const topItems = useMemo(() => getTopItems(yearItems), [yearItems]);
  const expensiveOrders = useMemo(() => getExpensiveOrders(yearOrders), [yearOrders]);
  const categoryBreakdown = useMemo(() => getCategoryBreakdown(yearItems), [yearItems]);
  const sourceBreakdown = useMemo(() => getSourceBreakdown(yearOrders), [yearOrders]);
  const monthlyBreakdown = useMemo(() => getMonthlyBreakdown(yearOrders, yearItems), [yearOrders, yearItems]);
  const weekdayBreakdown = useMemo(() => getWeekdayBreakdown(yearOrders), [yearOrders]);

  if (loading || !details) {
    return (
      <div className="py-10 text-center">
        <Spinner label="Loading details…" />
      </div>
    );
  }

  const categoryColumns: TableColumn<{ category: string; total: number; count: number }>[] = [
    { key: 'category', header: 'Category', primary: true, render: (c) => <span className="font-semibold text-ink">{c.category}</span> },
    { key: 'total', header: 'Total spent', className: 'text-right', render: (c) => <span className="font-mono font-bold text-alert-amber">${c.total.toFixed(2)}</span> },
    { key: 'count', header: 'Items', className: 'text-center', render: (c) => <span className="text-ink-dim">{c.count}</span> },
    {
      key: 'pct',
      header: '% of total',
      className: 'text-right',
      render: (c) => <span className="font-mono text-muted">{((c.total / data.total_spending) * 100).toFixed(1)}%</span>,
    },
  ];

  const allItemsColumns: TableColumn<Item>[] = [
    {
      key: 'name',
      header: 'Item',
      primary: true,
      render: (item) => (
        <Link to={`/items/${encodeURIComponent(item.name)}`} className="font-semibold text-signal hover:underline">
          {item.name}
        </Link>
      ),
    },
    { key: 'category', header: 'Category', render: (item) => <Badge tone="neutral">{item.category}</Badge> },
    { key: 'source', header: 'Source', render: (item) => <Badge tone="gold">{item.source}</Badge> },
    { key: 'date', header: 'Date', render: (item) => <span className="font-mono text-xs text-muted">{item.date}</span> },
    {
      key: 'total_price',
      header: 'Total',
      className: 'text-right',
      render: (item) => (
        <div>
          <div className="font-mono font-bold text-ink">${item.total_price?.toFixed(2)}</div>
          <div className="text-xs text-muted">${item.price?.toFixed(2)} × {item.quantity}</div>
        </div>
      ),
    },
  ];

  return (
    <div className="flex flex-col gap-5">
      <h3 className="text-base font-semibold text-ink">Detailed analysis for {data.year}</h3>

      {/* Summary Stats */}
      <div className="grid grid-cols-2 gap-3 sm:grid-cols-5">
        <Card padding={14}>
          <div className="mb-2 font-mono text-[11px] uppercase tracking-wider text-muted">Total spending</div>
          <div className="font-mono text-xl font-bold text-alert-amber">${data.total_spending.toFixed(2)}</div>
        </Card>
        <Card padding={14}>
          <div className="mb-2 font-mono text-[11px] uppercase tracking-wider text-muted">Orders</div>
          <div className="font-mono text-xl font-bold text-signal">{data.order_count}</div>
          <div className="mt-0.5 text-xs text-muted">Avg ${data.avg_order_value.toFixed(2)}</div>
        </Card>
        <Card padding={14}>
          <div className="mb-2 font-mono text-[11px] uppercase tracking-wider text-muted">Items purchased</div>
          <div className="font-mono text-xl font-bold text-alert-red">{data.item_count}</div>
          <div className="mt-0.5 text-xs text-muted">Unique: {topItems.length}</div>
        </Card>
        <Card padding={14}>
          <div className="mb-2 font-mono text-[11px] uppercase tracking-wider text-muted">Avg per month</div>
          <div className="font-mono text-xl font-bold text-ink-dim">${(data.total_spending / 12).toFixed(2)}</div>
        </Card>
        <Card padding={14}>
          <div className="mb-2 font-mono text-[11px] uppercase tracking-wider text-muted">Avg per day</div>
          <div className="font-mono text-xl font-bold text-alert-amber">${(data.total_spending / 365).toFixed(2)}</div>
        </Card>
      </div>

      {/* Monthly Trend */}
      <Card padding={14}>
        <h4 className="mb-3.5 font-mono text-xs uppercase tracking-wider text-muted">Monthly spending trend</h4>
        <div className="h-72">
          <ResponsiveContainer width="100%" height="100%">
            <LineChart data={monthlyBreakdown}>
              <CartesianGrid strokeDasharray="3 3" stroke="#262c33" />
              <XAxis dataKey="month" angle={-45} textAnchor="end" height={80} tick={AXIS} />
              <YAxis tick={AXIS} />
              <Tooltip
                formatter={(value: unknown, name: unknown) => {
                  if (name === 'spending') return `$${Number(value).toFixed(2)}`;
                  return value as React.ReactNode;
                }}
                contentStyle={TOOLTIP_STYLE}
              />
              <Legend wrapperStyle={{ fontSize: 12, color: '#8b8f92' }} />
              <Line type="monotone" dataKey="spending" stroke="#c89b3c" strokeWidth={2.5} name="Spending" dot={{ fill: '#c89b3c', r: 3 }} />
              <Line type="monotone" dataKey="orders" stroke="#4fa8a0" strokeWidth={2} name="Orders" dot={{ fill: '#4fa8a0', r: 3 }} />
            </LineChart>
          </ResponsiveContainer>
        </div>
      </Card>

      {/* Category & Source Analysis */}
      <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
        <Card padding={14}>
          <h4 className="mb-3.5 font-mono text-xs uppercase tracking-wider text-muted">Spending by category</h4>
          <div className="h-72">
            <ResponsiveContainer width="100%" height="100%">
              <PieChart>
                <Pie
                  data={categoryBreakdown.slice(0, 8)}
                  dataKey="total"
                  nameKey="category"
                  cx="50%"
                  cy="50%"
                  outerRadius={100}
                  label={pieCategoryLabel}
                >
                  {categoryBreakdown.slice(0, 8).map((_entry, index) => (
                    <Cell key={`cell-${index}`} fill={COLORS[index % COLORS.length]} />
                  ))}
                </Pie>
                <Tooltip formatter={(value: unknown) => `$${Number(value).toFixed(2)}`} contentStyle={TOOLTIP_STYLE} />
              </PieChart>
            </ResponsiveContainer>
          </div>
        </Card>

        <Card padding={14}>
          <h4 className="mb-3.5 font-mono text-xs uppercase tracking-wider text-muted">Spending by source</h4>
          <div className="h-72">
            <ResponsiveContainer width="100%" height="100%">
              <BarChart data={sourceBreakdown}>
                <CartesianGrid strokeDasharray="3 3" stroke="#262c33" />
                <XAxis dataKey="source" tick={AXIS} />
                <YAxis tick={AXIS} />
                <Tooltip formatter={(value: unknown) => `$${Number(value).toFixed(2)}`} contentStyle={TOOLTIP_STYLE} />
                <Bar dataKey="total" fill="#4fa8a0" radius={[4, 4, 0, 0]} />
              </BarChart>
            </ResponsiveContainer>
          </div>
        </Card>
      </div>

      {/* Weekday Analysis */}
      <Card padding={14}>
        <h4 className="mb-3.5 font-mono text-xs uppercase tracking-wider text-muted">Spending by day of week</h4>
        <div className="h-60">
          <ResponsiveContainer width="100%" height="100%">
            <BarChart data={weekdayBreakdown}>
              <CartesianGrid strokeDasharray="3 3" stroke="#262c33" />
              <XAxis dataKey="day" tick={AXIS} />
              <YAxis tick={AXIS} />
              <Tooltip
                formatter={(value: unknown, name: unknown) => {
                  if (name === 'spending') return `$${Number(value).toFixed(2)}`;
                  return value as React.ReactNode;
                }}
                contentStyle={TOOLTIP_STYLE}
              />
              <Bar dataKey="spending" fill="#4fa8a0" radius={[4, 4, 0, 0]} />
            </BarChart>
          </ResponsiveContainer>
        </div>
      </Card>

      {/* Top Items & Expensive Orders */}
      <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
        <Card padding={14}>
          <h4 className="mb-3.5 font-mono text-xs uppercase tracking-wider text-muted">Top 10 items (by total spent)</h4>
          <div className="flex max-h-[400px] flex-col overflow-y-auto">
            {topItems.map((item, idx) => (
              <div key={idx} className="flex items-center justify-between gap-2 border-b border-line py-2.5 last:border-b-0">
                <div className="flex-1">
                  <div className="mb-1 text-sm font-semibold text-ink">
                    {idx + 1}. <Link to={`/items/${encodeURIComponent(item.name)}`} className="text-signal hover:underline">{item.name}</Link>
                  </div>
                  <div className="text-xs text-muted">
                    <span className="mr-1.5 rounded bg-surface-dim px-1.5 py-0.5">{item.category}</span>
                    Qty {item.quantity} · Avg ${item.avgPrice.toFixed(2)}
                  </div>
                </div>
                <div className="font-mono text-base font-bold text-alert-amber">${item.total.toFixed(2)}</div>
              </div>
            ))}
          </div>
        </Card>

        <Card padding={14}>
          <h4 className="mb-3.5 font-mono text-xs uppercase tracking-wider text-muted">Most expensive orders</h4>
          <div className="flex max-h-[400px] flex-col overflow-y-auto">
            {expensiveOrders.map((order, idx) => (
              <div key={idx} className="flex items-center justify-between gap-2 border-b border-line py-2.5 last:border-b-0">
                <div className="flex-1">
                  <div className="mb-1 text-sm font-semibold text-ink">{idx + 1}. {order.date}</div>
                  <div className="text-xs text-muted">
                    <Badge tone="gold">{order.source}</Badge> <span className="ml-1.5">{order.items_summary}</span>
                  </div>
                </div>
                <div className="font-mono text-base font-bold text-alert-red">${order.total.toFixed(2)}</div>
              </div>
            ))}
          </div>
        </Card>
      </div>

      {/* Category Details Table */}
      <Card padding={14}>
        <h4 className="mb-3.5 font-mono text-xs uppercase tracking-wider text-muted">Category breakdown details</h4>
        <ResponsiveTable columns={categoryColumns} rows={categoryBreakdown} rowKey={(c) => c.category} emptyTitle="No categories" />
      </Card>

      {/* All Items List with Sorting */}
      <Card padding={14}>
        <div className="mb-3.5 flex flex-wrap items-center justify-between gap-2.5">
          <h4 className="font-mono text-xs uppercase tracking-wider text-muted">All items ({yearItems.length})</h4>
          <div className="flex gap-2">
            <button type="button" onClick={() => handleSort('price')} className={sortToggleClass(sortBy === 'price')}>
              Price {sortBy === 'price' && (sortOrder === 'desc' ? '↓' : '↑')}
            </button>
            <button type="button" onClick={() => handleSort('date')} className={sortToggleClass(sortBy === 'date')}>
              Date {sortBy === 'date' && (sortOrder === 'desc' ? '↓' : '↑')}
            </button>
            <button type="button" onClick={() => handleSort('name')} className={sortToggleClass(sortBy === 'name')}>
              Name {sortBy === 'name' && (sortOrder === 'desc' ? '↓' : '↑')}
            </button>
          </div>
        </div>
        <ResponsiveTable columns={allItemsColumns} rows={sortedItems} rowKey={(item) => `${item.name}-${item.date}-${item.order_id}`} emptyTitle="No items" />
      </Card>
    </div>
  );
};

const Years: React.FC = () => {
  const [yearlyData, setYearlyData] = useState<YearlyData[]>([]);
  const [loading, setLoading] = useState(true);
  const [yearDetails, setYearDetails] = useState<Record<string, YearDetails>>({});
  const [loadingYears, setLoadingYears] = useState<Set<string>>(new Set());

  useEffect(() => {
    api.get<YearlyData[]>('/years')
      .then(response => {
        setYearlyData(response.data);
        setLoading(false);
      })
      .catch(err => {
        console.error('Failed to load yearly data', err);
        setLoading(false);
      });
  }, []);

  const ensureYearDetails = useCallback((year: string) => {
    setYearDetails(prev => {
      if (prev[year]) return prev;
      setLoadingYears(cur => new Set(cur).add(year));
      Promise.all([
        api.get<Item[]>('/items'),
        api.get<Order[]>('/orders'),
      ])
        .then(([itemsRes, ordersRes]) => {
          const filteredItems = itemsRes.data.filter(i => i.date?.startsWith(year));
          const filteredOrders = ordersRes.data.filter(o => o.date?.startsWith(year));
          setYearDetails(cur => ({ ...cur, [year]: { items: filteredItems, orders: filteredOrders } }));
        })
        .catch(err => console.error('Failed to load year details', err))
        .finally(() => {
          setLoadingYears(cur => {
            const next = new Set(cur);
            next.delete(year);
            return next;
          });
        });
      return prev;
    });
  }, []);

  if (loading) {
    return (
      <div className="mx-auto max-w-[1200px] px-4 py-6 md:px-6">
        <Spinner label="Loading yearly data…" />
      </div>
    );
  }

  const chartData = yearlyData.slice().reverse();

  const columns: TableColumn<YearlyData>[] = [
    { key: 'year', header: 'Year', primary: true, render: (d) => <span className="font-mono text-base font-bold">{d.year}</span> },
    {
      key: 'total_spending',
      header: 'Total spending',
      className: 'text-right',
      render: (d) => <span className="font-mono text-lg font-bold text-alert-amber">${d.total_spending.toFixed(2)}</span>,
    },
    { key: 'order_count', header: 'Orders', className: 'text-center', render: (d) => <Badge tone="teal">{d.order_count}</Badge> },
    { key: 'item_count', header: 'Items', className: 'text-center', render: (d) => <Badge tone="ember">{d.item_count}</Badge> },
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
      <PageHeader eyebrow="Ledger / Years" title="Yearly spending analysis" />

      {/* Overview Chart */}
      <Card className="mb-7">
        <h2 className="mb-4 font-mono text-xs uppercase tracking-wider text-muted">Yearly spending trend</h2>
        <div className="h-72">
          <ResponsiveContainer width="100%" height="100%">
            <BarChart data={chartData}>
              <CartesianGrid strokeDasharray="3 3" stroke="#262c33" />
              <XAxis dataKey="year" tick={AXIS} />
              <YAxis tick={AXIS} />
              <Tooltip formatter={(value: unknown) => `$${Number(value).toFixed(2)}`} contentStyle={TOOLTIP_STYLE} />
              <Bar dataKey="total_spending" fill="#c89b3c" radius={[4, 4, 0, 0]} />
            </BarChart>
          </ResponsiveContainer>
        </div>
      </Card>

      {/* Yearly Details Table */}
      <ResponsiveTable
        columns={columns}
        rows={yearlyData}
        rowKey={(d) => d.year}
        emptyTitle="No yearly data yet"
        expandedContent={(d) => {
          ensureYearDetails(d.year);
          return <YearDetailPanel data={d} details={yearDetails[d.year]} loading={loadingYears.has(d.year)} />;
        }}
      />

      {/* Summary Stats */}
      <div className="mt-7 grid grid-cols-2 gap-4 sm:grid-cols-4">
        <Card className="text-center">
          <div className="mb-2 font-mono text-[11px] uppercase tracking-wider text-muted">Total years</div>
          <div className="font-mono text-2xl font-bold text-alert-amber">{yearlyData.length}</div>
        </Card>
        <Card className="text-center">
          <div className="mb-2 font-mono text-[11px] uppercase tracking-wider text-muted">Highest year</div>
          <div className="font-mono text-xl font-bold text-signal">
            ${yearlyData.length > 0 ? Math.max(...yearlyData.map(y => y.total_spending)).toFixed(2) : '0.00'}
          </div>
          <div className="mt-1 text-xs text-muted">
            {yearlyData.length > 0 ? yearlyData.reduce((max, y) => y.total_spending > max.total_spending ? y : max).year : 'N/A'}
          </div>
        </Card>
        <Card className="text-center">
          <div className="mb-2 font-mono text-[11px] uppercase tracking-wider text-muted">Lowest year</div>
          <div className="font-mono text-xl font-bold text-alert-red">
            ${yearlyData.length > 0 ? Math.min(...yearlyData.map(y => y.total_spending)).toFixed(2) : '0.00'}
          </div>
          <div className="mt-1 text-xs text-muted">
            {yearlyData.length > 0 ? yearlyData.reduce((min, y) => y.total_spending < min.total_spending ? y : min).year : 'N/A'}
          </div>
        </Card>
        <Card className="text-center">
          <div className="mb-2 font-mono text-[11px] uppercase tracking-wider text-muted">Avg per year</div>
          <div className="font-mono text-xl font-bold text-ink-dim">
            ${yearlyData.length > 0 ? (yearlyData.reduce((sum, y) => sum + y.total_spending, 0) / yearlyData.length).toFixed(2) : '0.00'}
          </div>
        </Card>
      </div>
    </div>
  );
};

export default Years;
