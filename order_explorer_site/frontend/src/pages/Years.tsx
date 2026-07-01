import React, { useEffect, useState } from 'react';
import axios from 'axios';
import { BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer, CartesianGrid, PieChart, Pie, Cell, Legend, LineChart, Line } from 'recharts';
import type { PieLabelRenderProps } from 'recharts';
import { Link } from 'react-router-dom';
import PageHeader from '../components/ui/PageHeader';
import Card from '../components/ui/Card';

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

const COLORS = ['#c89b3c', '#4fa8a0', '#d8603f', '#e8c478', '#6ea87a', '#8f7fd6', '#4a90c4', '#b6588c'];
const AXIS = { fontSize: 12, fill: '#8b8f92' };
const TOOLTIP_STYLE = { background: '#1b2026', border: '1px solid #262c33', borderRadius: 8, color: '#e9e6dd' };

const statSubLabel: React.CSSProperties = { fontSize: '11px', color: 'var(--muted)', marginBottom: '8px', fontFamily: 'var(--font-mono)', textTransform: 'uppercase', letterSpacing: '0.04em' };

const thStyle = (align: 'left' | 'right' | 'center'): React.CSSProperties => ({
  padding: '13px 14px', textAlign: align, fontWeight: 600, fontSize: 11,
  fontFamily: 'var(--font-mono)', textTransform: 'uppercase', letterSpacing: '0.05em', color: 'var(--muted)',
});

const pieCategoryLabel = (props: PieLabelRenderProps) => {
  const { category, total } = props as unknown as { category: string; total: number };
  return `${category}: $${total.toFixed(0)}`;
};

const Years: React.FC = () => {
  const [yearlyData, setYearlyData] = useState<YearlyData[]>([]);
  const [loading, setLoading] = useState(true);
  const [expandedYear, setExpandedYear] = useState<string | null>(null);
  const [yearItems, setYearItems] = useState<Item[]>([]);
  const [yearOrders, setYearOrders] = useState<Order[]>([]);
  const [loadingDetails, setLoadingDetails] = useState(false);
  const [sortBy, setSortBy] = useState<'date' | 'price' | 'name'>('price');
  const [sortOrder, setSortOrder] = useState<'asc' | 'desc'>('desc');

  useEffect(() => {
    axios.get<YearlyData[]>('http://localhost:8015/years')
      .then(response => {
        setYearlyData(response.data);
        setLoading(false);
      })
      .catch(err => {
        console.error('Failed to load yearly data', err);
        setLoading(false);
      });
  }, []);

  if (loading) return <div style={{ padding: 24, color: 'var(--muted)' }}>Loading yearly data…</div>;

  const toggleYear = async (year: string) => {
    if (expandedYear === year) {
      setExpandedYear(null);
      setYearItems([]);
      setYearOrders([]);
    } else {
      setExpandedYear(year);
      setLoadingDetails(true);

      try {
        const [itemsRes, ordersRes] = await Promise.all([
          axios.get<Item[]>('http://localhost:8015/items'),
          axios.get<Order[]>('http://localhost:8015/orders')
        ]);

        const filteredItems = itemsRes.data.filter(i => i.date?.startsWith(year));
        const filteredOrders = ordersRes.data.filter(o => o.date?.startsWith(year));

        setYearItems(filteredItems);
        setYearOrders(filteredOrders);
      } catch (err) {
        console.error('Failed to load year details', err);
      }

      setLoadingDetails(false);
    }
  };

  const handleSort = (field: 'date' | 'price' | 'name') => {
    if (sortBy === field) {
      setSortOrder(sortOrder === 'asc' ? 'desc' : 'asc');
    } else {
      setSortBy(field);
      setSortOrder(field === 'price' ? 'desc' : 'asc');
    }
  };

  const getSortedItems = () => {
    const sorted = [...yearItems];

    sorted.sort((a, b) => {
      let compareA, compareB;

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
  };

  const getMonthlyBreakdown = () => {
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

  const getCategoryBreakdown = () => {
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

  const getSourceBreakdown = () => {
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

  const getTopItems = () => {
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

  const getExpensiveOrders = () => {
    return [...yearOrders].sort((a, b) => (b.total || 0) - (a.total || 0)).slice(0, 10);
  };

  const getWeekdayBreakdown = () => {
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

  const chartData = yearlyData.slice().reverse();

  return (
    <div style={{ padding: '24px 24px 48px' }}>
      <PageHeader eyebrow="Ledger / Years" title="Yearly spending analysis" />

      {/* Overview Chart */}
      <Card style={{ marginBottom: '28px' }}>
        <h2 style={{ fontSize: 13, fontFamily: 'var(--font-mono)', letterSpacing: '0.06em', textTransform: 'uppercase', marginBottom: 16, color: 'var(--muted)' }}>Yearly spending trend</h2>
        <div style={{ height: '300px' }}>
          <ResponsiveContainer width="100%" height="100%">
            <BarChart data={chartData}>
              <CartesianGrid strokeDasharray="3 3" stroke="#262c33" />
              <XAxis dataKey="year" tick={AXIS} />
              <YAxis tick={AXIS} />
              <Tooltip formatter={(value: any) => `$${value.toFixed(2)}`} contentStyle={TOOLTIP_STYLE} />
              <Bar dataKey="total_spending" fill="#c89b3c" radius={[4, 4, 0, 0]} />
            </BarChart>
          </ResponsiveContainer>
        </div>
      </Card>

      {/* Yearly Details Table */}
      <div style={{ border: '1px solid var(--ink-700)', borderRadius: '10px', overflow: 'hidden' }}>
        <table style={{ width: '100%', borderCollapse: 'collapse' }}>
          <thead>
            <tr style={{ background: 'var(--ink-750)' }}>
              <th style={thStyle('left')}>Year</th>
              <th style={thStyle('right')}>Total spending</th>
              <th style={thStyle('center')}>Orders</th>
              <th style={thStyle('center')}>Items</th>
              <th style={thStyle('right')}>Avg order</th>
              <th style={thStyle('left')}>Top category</th>
              <th style={thStyle('center')}>Details</th>
            </tr>
          </thead>
          <tbody>
            {yearlyData.map((data, idx) => (
              <React.Fragment key={data.year}>
                <tr style={{ backgroundColor: idx % 2 === 0 ? 'var(--ink-800)' : 'var(--ink-900)' }}>
                  <td style={{ padding: '14px', fontWeight: 700, fontFamily: 'var(--font-mono)', fontSize: 16, color: 'var(--paper)' }}>{data.year}</td>
                  <td style={{ padding: '14px', textAlign: 'right', fontSize: '18px', fontWeight: 700, fontFamily: 'var(--font-mono)', color: 'var(--stamp-gold)' }}>
                    ${data.total_spending.toFixed(2)}
                  </td>
                  <td style={{ padding: '14px', textAlign: 'center' }}>
                    <span style={{ background: 'rgba(79, 168, 160, 0.15)', color: 'var(--stamp-teal)', padding: '4px 11px', borderRadius: '12px', fontWeight: 600, fontSize: 12 }}>
                      {data.order_count}
                    </span>
                  </td>
                  <td style={{ padding: '14px', textAlign: 'center' }}>
                    <span style={{ background: 'rgba(216, 96, 63, 0.15)', color: 'var(--stamp-ember)', padding: '4px 11px', borderRadius: '12px', fontWeight: 600, fontSize: 12 }}>
                      {data.item_count}
                    </span>
                  </td>
                  <td style={{ padding: '14px', textAlign: 'right', color: 'var(--muted)', fontFamily: 'var(--font-mono)', fontSize: 13 }}>${data.avg_order_value.toFixed(2)}</td>
                  <td style={{ padding: '14px' }}>
                    <div style={{ fontWeight: 600, color: 'var(--paper)', fontSize: 13.5 }}>{data.top_category}</div>
                    <div style={{ fontSize: '12px', color: 'var(--muted)' }}>${data.top_category_spending.toFixed(2)}</div>
                  </td>
                  <td style={{ padding: '14px', textAlign: 'center' }}>
                    <button onClick={() => toggleYear(data.year)} style={{ padding: '6px 14px', fontSize: '13px', fontWeight: 600 }}>
                      {expandedYear === data.year ? 'Hide' : 'Show'}
                    </button>
                  </td>
                </tr>
                {expandedYear === data.year && (
                  <tr>
                    <td colSpan={7} style={{ padding: 0, background: 'var(--ink-900)' }}>
                      {loadingDetails ? (
                        <div style={{ padding: '40px', textAlign: 'center', color: 'var(--muted)' }}>Loading details…</div>
                      ) : (
                        <div style={{ padding: '20px' }}>
                          <h3 style={{ fontSize: 15, marginBottom: '18px', color: 'var(--paper)' }}>Detailed analysis for {data.year}</h3>

                          {/* Summary Stats */}
                          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(170px, 1fr))', gap: '12px', marginBottom: '22px' }}>
                            <Card padding={14}>
                              <div style={statSubLabel}>Total spending</div>
                              <div style={{ fontSize: '22px', fontWeight: 700, fontFamily: 'var(--font-mono)', color: 'var(--stamp-gold)' }}>${data.total_spending.toFixed(2)}</div>
                            </Card>
                            <Card padding={14}>
                              <div style={statSubLabel}>Orders</div>
                              <div style={{ fontSize: '22px', fontWeight: 700, fontFamily: 'var(--font-mono)', color: 'var(--stamp-teal)' }}>{data.order_count}</div>
                              <div style={{ fontSize: '11px', color: 'var(--muted)', marginTop: '2px' }}>Avg ${data.avg_order_value.toFixed(2)}</div>
                            </Card>
                            <Card padding={14}>
                              <div style={statSubLabel}>Items purchased</div>
                              <div style={{ fontSize: '22px', fontWeight: 700, fontFamily: 'var(--font-mono)', color: 'var(--stamp-ember)' }}>{data.item_count}</div>
                              <div style={{ fontSize: '11px', color: 'var(--muted)', marginTop: '2px' }}>Unique: {getTopItems().length}</div>
                            </Card>
                            <Card padding={14}>
                              <div style={statSubLabel}>Avg per month</div>
                              <div style={{ fontSize: '22px', fontWeight: 700, fontFamily: 'var(--font-mono)', color: 'var(--paper-dim)' }}>${(data.total_spending / 12).toFixed(2)}</div>
                            </Card>
                            <Card padding={14}>
                              <div style={statSubLabel}>Avg per day</div>
                              <div style={{ fontSize: '22px', fontWeight: 700, fontFamily: 'var(--font-mono)', color: '#e8c478' }}>${(data.total_spending / 365).toFixed(2)}</div>
                            </Card>
                          </div>

                          {/* Monthly Trend */}
                          <Card style={{ marginBottom: '20px' }} padding={14}>
                            <h4 style={{ marginBottom: 14, fontSize: 12.5, fontFamily: 'var(--font-mono)', textTransform: 'uppercase', letterSpacing: '0.05em', color: 'var(--muted)' }}>Monthly spending trend</h4>
                            <div style={{ height: '300px' }}>
                              <ResponsiveContainer width="100%" height="100%">
                                <LineChart data={getMonthlyBreakdown()}>
                                  <CartesianGrid strokeDasharray="3 3" stroke="#262c33" />
                                  <XAxis dataKey="month" angle={-45} textAnchor="end" height={80} tick={AXIS} />
                                  <YAxis tick={AXIS} />
                                  <Tooltip
                                    formatter={(value: any, name: any) => {
                                      if (name === 'spending') return `$${value.toFixed(2)}`;
                                      return value;
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
                          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(380px, 1fr))', gap: '16px', marginBottom: '20px' }}>
                            <Card padding={14}>
                              <h4 style={{ marginBottom: 14, fontSize: 12.5, fontFamily: 'var(--font-mono)', textTransform: 'uppercase', letterSpacing: '0.05em', color: 'var(--muted)' }}>Spending by category</h4>
                              <div style={{ height: '300px' }}>
                                <ResponsiveContainer width="100%" height="100%">
                                  <PieChart>
                                    <Pie
                                      data={getCategoryBreakdown().slice(0, 8)}
                                      dataKey="total"
                                      nameKey="category"
                                      cx="50%"
                                      cy="50%"
                                      outerRadius={100}
                                      label={pieCategoryLabel}
                                    >
                                      {getCategoryBreakdown().slice(0, 8).map((_entry, index) => (
                                        <Cell key={`cell-${index}`} fill={COLORS[index % COLORS.length]} />
                                      ))}
                                    </Pie>
                                    <Tooltip formatter={(value: any) => `$${value.toFixed(2)}`} contentStyle={TOOLTIP_STYLE} />
                                  </PieChart>
                                </ResponsiveContainer>
                              </div>
                            </Card>

                            <Card padding={14}>
                              <h4 style={{ marginBottom: 14, fontSize: 12.5, fontFamily: 'var(--font-mono)', textTransform: 'uppercase', letterSpacing: '0.05em', color: 'var(--muted)' }}>Spending by source</h4>
                              <div style={{ height: '300px' }}>
                                <ResponsiveContainer width="100%" height="100%">
                                  <BarChart data={getSourceBreakdown()}>
                                    <CartesianGrid strokeDasharray="3 3" stroke="#262c33" />
                                    <XAxis dataKey="source" tick={AXIS} />
                                    <YAxis tick={AXIS} />
                                    <Tooltip formatter={(value: any) => `$${value.toFixed(2)}`} contentStyle={TOOLTIP_STYLE} />
                                    <Bar dataKey="total" fill="#4fa8a0" radius={[4, 4, 0, 0]} />
                                  </BarChart>
                                </ResponsiveContainer>
                              </div>
                            </Card>
                          </div>

                          {/* Weekday Analysis */}
                          <Card style={{ marginBottom: '20px' }} padding={14}>
                            <h4 style={{ marginBottom: 14, fontSize: 12.5, fontFamily: 'var(--font-mono)', textTransform: 'uppercase', letterSpacing: '0.05em', color: 'var(--muted)' }}>Spending by day of week</h4>
                            <div style={{ height: '250px' }}>
                              <ResponsiveContainer width="100%" height="100%">
                                <BarChart data={getWeekdayBreakdown()}>
                                  <CartesianGrid strokeDasharray="3 3" stroke="#262c33" />
                                  <XAxis dataKey="day" tick={AXIS} />
                                  <YAxis tick={AXIS} />
                                  <Tooltip
                                    formatter={(value: any, name: any) => {
                                      if (name === 'spending') return `$${value.toFixed(2)}`;
                                      return value;
                                    }}
                                    contentStyle={TOOLTIP_STYLE}
                                  />
                                  <Bar dataKey="spending" fill="#4fa8a0" radius={[4, 4, 0, 0]} />
                                </BarChart>
                              </ResponsiveContainer>
                            </div>
                          </Card>

                          {/* Top Items & Expensive Orders */}
                          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(420px, 1fr))', gap: '16px', marginBottom: '20px' }}>
                            <Card padding={14}>
                              <h4 style={{ marginBottom: 14, fontSize: 12.5, fontFamily: 'var(--font-mono)', textTransform: 'uppercase', letterSpacing: '0.05em', color: 'var(--muted)' }}>Top 10 items (by total spent)</h4>
                              <div style={{ maxHeight: '400px', overflowY: 'auto' }}>
                                {getTopItems().map((item, idx) => (
                                  <div key={idx} style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', padding: '10px 4px', borderBottom: idx < 9 ? '1px solid var(--ink-700)' : 'none' }}>
                                    <div style={{ flex: 1 }}>
                                      <div style={{ fontSize: '13.5px', fontWeight: 600, color: 'var(--paper)', marginBottom: '4px' }}>
                                        {idx + 1}. <Link to={`/items/${encodeURIComponent(item.name)}`} style={{ color: 'var(--stamp-teal)' }}>{item.name}</Link>
                                      </div>
                                      <div style={{ fontSize: '11px', color: 'var(--muted)' }}>
                                        <span style={{ background: 'var(--ink-700)', color: 'var(--muted)', padding: '2px 6px', borderRadius: '4px', marginRight: '6px' }}>
                                          {item.category}
                                        </span>
                                        Qty {item.quantity} · Avg ${item.avgPrice.toFixed(2)}
                                      </div>
                                    </div>
                                    <div style={{ fontWeight: 700, fontFamily: 'var(--font-mono)', color: 'var(--stamp-gold)', fontSize: 15 }}>
                                      ${item.total.toFixed(2)}
                                    </div>
                                  </div>
                                ))}
                              </div>
                            </Card>

                            <Card padding={14}>
                              <h4 style={{ marginBottom: 14, fontSize: 12.5, fontFamily: 'var(--font-mono)', textTransform: 'uppercase', letterSpacing: '0.05em', color: 'var(--muted)' }}>Most expensive orders</h4>
                              <div style={{ maxHeight: '400px', overflowY: 'auto' }}>
                                {getExpensiveOrders().map((order, idx) => (
                                  <div key={idx} style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', padding: '10px 4px', borderBottom: idx < 9 ? '1px solid var(--ink-700)' : 'none' }}>
                                    <div style={{ flex: 1 }}>
                                      <div style={{ fontSize: '13.5px', fontWeight: 600, color: 'var(--paper)', marginBottom: '4px' }}>{idx + 1}. {order.date}</div>
                                      <div style={{ fontSize: '11px', color: 'var(--muted)' }}>
                                        <span style={{ background: 'rgba(200, 155, 60, 0.15)', color: 'var(--stamp-gold)', padding: '2px 6px', borderRadius: '4px', marginRight: '6px' }}>
                                          {order.source}
                                        </span>
                                        {order.items_summary}
                                      </div>
                                    </div>
                                    <div style={{ fontWeight: 700, fontFamily: 'var(--font-mono)', color: 'var(--stamp-ember)', fontSize: 15 }}>
                                      ${order.total.toFixed(2)}
                                    </div>
                                  </div>
                                ))}
                              </div>
                            </Card>
                          </div>

                          {/* Category Details Table */}
                          <Card style={{ marginBottom: '20px' }} padding={14}>
                            <h4 style={{ marginBottom: 14, fontSize: 12.5, fontFamily: 'var(--font-mono)', textTransform: 'uppercase', letterSpacing: '0.05em', color: 'var(--muted)' }}>Category breakdown details</h4>
                            <div style={{ overflowX: 'auto' }}>
                              <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: '13px' }}>
                                <thead>
                                  <tr style={{ borderBottom: '1px solid var(--ink-700)' }}>
                                    <th style={{ padding: '9px', textAlign: 'left', fontWeight: 600, fontSize: 11, fontFamily: 'var(--font-mono)', color: 'var(--muted)', textTransform: 'uppercase' }}>Category</th>
                                    <th style={{ padding: '9px', textAlign: 'right', fontWeight: 600, fontSize: 11, fontFamily: 'var(--font-mono)', color: 'var(--muted)', textTransform: 'uppercase' }}>Total spent</th>
                                    <th style={{ padding: '9px', textAlign: 'center', fontWeight: 600, fontSize: 11, fontFamily: 'var(--font-mono)', color: 'var(--muted)', textTransform: 'uppercase' }}>Items</th>
                                    <th style={{ padding: '9px', textAlign: 'right', fontWeight: 600, fontSize: 11, fontFamily: 'var(--font-mono)', color: 'var(--muted)', textTransform: 'uppercase' }}>% of total</th>
                                  </tr>
                                </thead>
                                <tbody>
                                  {getCategoryBreakdown().map((cat, idx) => (
                                    <tr key={idx} style={{ borderBottom: '1px solid var(--ink-700)' }}>
                                      <td style={{ padding: '9px', fontWeight: 600, color: 'var(--paper)' }}>{cat.category}</td>
                                      <td style={{ padding: '9px', textAlign: 'right', color: 'var(--stamp-gold)', fontWeight: 700, fontFamily: 'var(--font-mono)' }}>${cat.total.toFixed(2)}</td>
                                      <td style={{ padding: '9px', textAlign: 'center', color: 'var(--paper-dim)' }}>{cat.count}</td>
                                      <td style={{ padding: '9px', textAlign: 'right', color: 'var(--muted)', fontFamily: 'var(--font-mono)' }}>{((cat.total / data.total_spending) * 100).toFixed(1)}%</td>
                                    </tr>
                                  ))}
                                </tbody>
                              </table>
                            </div>
                          </Card>

                          {/* All Items List with Sorting */}
                          <Card padding={14}>
                            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '14px', flexWrap: 'wrap', gap: 10 }}>
                              <h4 style={{ fontSize: 12.5, fontFamily: 'var(--font-mono)', textTransform: 'uppercase', letterSpacing: '0.05em', color: 'var(--muted)' }}>All items ({yearItems.length})</h4>
                              <div style={{ display: 'flex', gap: '8px' }}>
                                <button onClick={() => handleSort('price')} style={sortToggle(sortBy === 'price')}>
                                  Price {sortBy === 'price' && (sortOrder === 'desc' ? '↓' : '↑')}
                                </button>
                                <button onClick={() => handleSort('date')} style={sortToggle(sortBy === 'date')}>
                                  Date {sortBy === 'date' && (sortOrder === 'desc' ? '↓' : '↑')}
                                </button>
                                <button onClick={() => handleSort('name')} style={sortToggle(sortBy === 'name')}>
                                  Name {sortBy === 'name' && (sortOrder === 'desc' ? '↓' : '↑')}
                                </button>
                              </div>
                            </div>
                            <div style={{ maxHeight: '600px', overflowY: 'auto' }}>
                              {getSortedItems().map((item, idx) => (
                                <div key={idx} style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', padding: '11px 4px', borderBottom: idx < yearItems.length - 1 ? '1px solid var(--ink-700)' : 'none' }}>
                                  <div style={{ flex: 1 }}>
                                    <Link to={`/items/${encodeURIComponent(item.name)}`} style={{ fontWeight: 600, color: 'var(--stamp-teal)', fontSize: '14px' }}>
                                      {item.name}
                                    </Link>
                                    <div style={{ fontSize: '12px', color: 'var(--muted)', marginTop: '4px' }}>
                                      <span style={{ background: 'var(--ink-700)', color: 'var(--muted)', padding: '2px 6px', borderRadius: '4px', marginRight: '8px' }}>{item.category}</span>
                                      <span style={{ background: 'rgba(200, 155, 60, 0.15)', color: 'var(--stamp-gold)', padding: '2px 6px', borderRadius: '4px', marginRight: '8px' }}>{item.source}</span>
                                      <span>{item.date}</span>
                                    </div>
                                  </div>
                                  <div style={{ textAlign: 'right' }}>
                                    <div style={{ fontWeight: 700, fontFamily: 'var(--font-mono)', color: 'var(--paper)', fontSize: 15 }}>${item.total_price?.toFixed(2)}</div>
                                    <div style={{ fontSize: '11px', color: 'var(--muted)' }}>${item.price?.toFixed(2)} × {item.quantity}</div>
                                  </div>
                                </div>
                              ))}
                            </div>
                          </Card>
                        </div>
                      )}
                    </td>
                  </tr>
                )}
              </React.Fragment>
            ))}
          </tbody>
        </table>
      </div>

      {/* Summary Stats */}
      <div style={{ marginTop: '28px', display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))', gap: '16px' }}>
        <Card style={{ textAlign: 'center' }}>
          <div style={statSubLabel}>Total years</div>
          <div style={{ fontSize: '26px', fontWeight: 700, fontFamily: 'var(--font-mono)', color: 'var(--stamp-gold)' }}>{yearlyData.length}</div>
        </Card>
        <Card style={{ textAlign: 'center' }}>
          <div style={statSubLabel}>Highest year</div>
          <div style={{ fontSize: '20px', fontWeight: 700, fontFamily: 'var(--font-mono)', color: 'var(--stamp-teal)' }}>
            ${yearlyData.length > 0 ? Math.max(...yearlyData.map(y => y.total_spending)).toFixed(2) : '0.00'}
          </div>
          <div style={{ fontSize: '11px', color: 'var(--muted)', marginTop: '4px' }}>
            {yearlyData.length > 0 ? yearlyData.reduce((max, y) => y.total_spending > max.total_spending ? y : max).year : 'N/A'}
          </div>
        </Card>
        <Card style={{ textAlign: 'center' }}>
          <div style={statSubLabel}>Lowest year</div>
          <div style={{ fontSize: '20px', fontWeight: 700, fontFamily: 'var(--font-mono)', color: 'var(--stamp-ember)' }}>
            ${yearlyData.length > 0 ? Math.min(...yearlyData.map(y => y.total_spending)).toFixed(2) : '0.00'}
          </div>
          <div style={{ fontSize: '11px', color: 'var(--muted)', marginTop: '4px' }}>
            {yearlyData.length > 0 ? yearlyData.reduce((min, y) => y.total_spending < min.total_spending ? y : min).year : 'N/A'}
          </div>
        </Card>
        <Card style={{ textAlign: 'center' }}>
          <div style={statSubLabel}>Avg per year</div>
          <div style={{ fontSize: '20px', fontWeight: 700, fontFamily: 'var(--font-mono)', color: 'var(--paper-dim)' }}>
            ${yearlyData.length > 0 ? (yearlyData.reduce((sum, y) => sum + y.total_spending, 0) / yearlyData.length).toFixed(2) : '0.00'}
          </div>
        </Card>
      </div>
    </div>
  );
};

const sortToggle = (active: boolean): React.CSSProperties => ({
  background: active ? 'var(--stamp-gold)' : 'transparent',
  color: active ? 'var(--ink-900)' : 'var(--muted)',
  border: '1px solid var(--ink-600)',
  padding: '6px 12px',
  fontSize: '12px',
  fontWeight: 600,
});

export default Years;
