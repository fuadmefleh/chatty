import React, { useEffect, useState } from 'react';
import axios from 'axios';
import { BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer, CartesianGrid, PieChart, Pie, Cell } from 'recharts';
import type { PieLabelRenderProps } from 'recharts';
import { Link } from 'react-router-dom';
import PageHeader from '../components/ui/PageHeader';
import Card from '../components/ui/Card';

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

const COLORS = ['#c89b3c', '#4fa8a0', '#d8603f', '#e8c478', '#6ea87a', '#8f7fd6'];
const AXIS = { fontSize: 12, fill: '#8b8f92' };
const TOOLTIP_STYLE = { background: '#1b2026', border: '1px solid #262c33', borderRadius: 8, color: '#e9e6dd' };

const pieCategoryLabel = (props: PieLabelRenderProps) => {
  const { category, total } = props as unknown as { category: string; total: number };
  return `${category}: $${total.toFixed(0)}`;
};

const Months: React.FC = () => {
  const [monthlyData, setMonthlyData] = useState<MonthlyData[]>([]);
  const [loading, setLoading] = useState(true);
  const [expandedMonth, setExpandedMonth] = useState<string | null>(null);
  const [monthOrders, setMonthOrders] = useState<Order[]>([]);
  const [monthItems, setMonthItems] = useState<Item[]>([]);
  const [loadingDetails, setLoadingDetails] = useState(false);
  const [expandedOrderId, setExpandedOrderId] = useState<string | null>(null);
  const [orderItems, setOrderItems] = useState<Record<string, Item[]>>({});

  useEffect(() => {
    axios.get<MonthlyData[]>('http://localhost:8015/months')
      .then(response => {
        setMonthlyData(response.data);
        setLoading(false);
      })
      .catch(err => {
        console.error('Failed to load monthly data', err);
        setLoading(false);
      });
  }, []);

  if (loading) return <div style={{ padding: 24, color: 'var(--muted)' }}>Loading monthly data…</div>;

  const toggleMonth = async (month: string) => {
    if (expandedMonth === month) {
      setExpandedMonth(null);
      setMonthOrders([]);
      setMonthItems([]);
    } else {
      setExpandedMonth(month);
      setLoadingDetails(true);

      try {
        const [ordersRes, itemsRes] = await Promise.all([
          axios.get<Order[]>('http://localhost:8015/orders'),
          axios.get<Item[]>('http://localhost:8015/items')
        ]);

        const filteredOrders = ordersRes.data.filter(o => o.date?.startsWith(month));
        const filteredItems = itemsRes.data.filter(i => i.date?.startsWith(month));

        setMonthOrders(filteredOrders);
        setMonthItems(filteredItems);
      } catch (err) {
        console.error('Failed to load month details', err);
      }

      setLoadingDetails(false);
    }
  };

  const toggleOrderItems = (orderId: string) => {
    if (expandedOrderId === orderId) {
      setExpandedOrderId(null);
    } else {
      setExpandedOrderId(orderId);
      if (!orderItems[orderId]) {
        const items = monthItems.filter(item => item.order_id === orderId);
        setOrderItems(prev => ({ ...prev, [orderId]: items }));
      }
    }
  };

  const chartData = monthlyData.slice(0, 12).reverse();

  return (
    <div style={{ padding: '24px 24px 48px' }}>
      <PageHeader eyebrow="Ledger / Months" title="Monthly spending analysis" />

      {/* Overview Chart */}
      <Card style={{ marginBottom: '28px' }}>
        <h2 style={{ fontSize: 13, fontFamily: 'var(--font-mono)', letterSpacing: '0.06em', textTransform: 'uppercase', marginBottom: 16, color: 'var(--muted)' }}>Monthly spending trend</h2>
        <div style={{ height: '300px' }}>
          <ResponsiveContainer width="100%" height="100%">
            <BarChart data={chartData}>
              <CartesianGrid strokeDasharray="3 3" stroke="#262c33" />
              <XAxis dataKey="month" tick={AXIS} />
              <YAxis tick={AXIS} />
              <Tooltip
                formatter={(value: any) => `$${value.toFixed(2)}`}
                labelFormatter={(label) => `Month: ${label}`}
                contentStyle={TOOLTIP_STYLE}
              />
              <Bar dataKey="total_spending" fill="#c89b3c" radius={[4, 4, 0, 0]} />
            </BarChart>
          </ResponsiveContainer>
        </div>
      </Card>

      {/* Monthly Details Table */}
      <div style={{ border: '1px solid var(--ink-700)', borderRadius: '10px', overflow: 'hidden' }}>
        <table style={{ width: '100%', borderCollapse: 'collapse' }}>
          <thead>
            <tr style={{ background: 'var(--ink-750)' }}>
              <th style={thStyle('left')}>Month</th>
              <th style={thStyle('right')}>Total spending</th>
              <th style={thStyle('center')}>Orders</th>
              <th style={thStyle('center')}>Items</th>
              <th style={thStyle('right')}>Avg order</th>
              <th style={thStyle('left')}>Top category</th>
              <th style={thStyle('center')}>Details</th>
            </tr>
          </thead>
          <tbody>
            {monthlyData.map((data, idx) => (
              <React.Fragment key={data.month}>
                <tr style={{ backgroundColor: idx % 2 === 0 ? 'var(--ink-800)' : 'var(--ink-900)' }}>
                  <td style={{ padding: '14px', fontWeight: 700, fontFamily: 'var(--font-mono)', color: 'var(--paper)' }}>{data.month}</td>
                  <td style={{ padding: '14px', textAlign: 'right', fontSize: '16px', fontWeight: 700, fontFamily: 'var(--font-mono)', color: 'var(--stamp-gold)' }}>
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
                  <td style={{ padding: '14px', textAlign: 'right', color: 'var(--muted)', fontFamily: 'var(--font-mono)', fontSize: 13 }}>
                    ${data.avg_order_value.toFixed(2)}
                  </td>
                  <td style={{ padding: '14px' }}>
                    <div style={{ fontWeight: 600, color: 'var(--paper)', fontSize: 13.5 }}>{data.top_category}</div>
                    <div style={{ fontSize: '12px', color: 'var(--muted)' }}>${data.top_category_spending.toFixed(2)}</div>
                  </td>
                  <td style={{ padding: '14px', textAlign: 'center' }}>
                    <button onClick={() => toggleMonth(data.month)} style={{ padding: '6px 14px', fontSize: '13px', fontWeight: 600 }}>
                      {expandedMonth === data.month ? 'Hide' : 'Show'}
                    </button>
                  </td>
                </tr>
                {expandedMonth === data.month && (
                  <tr>
                    <td colSpan={7} style={{ padding: 0, background: 'var(--ink-900)' }}>
                      {loadingDetails ? (
                        <div style={{ padding: '40px', textAlign: 'center', color: 'var(--muted)' }}>Loading details…</div>
                      ) : (
                        <div style={{ padding: '20px' }}>
                          {/* Summary Cards */}
                          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(150px, 1fr))', gap: '12px', marginBottom: '20px' }}>
                            <Card padding={14}>
                              <div style={statSubLabel}>Total spending</div>
                              <div style={{ fontSize: '20px', fontWeight: 700, fontFamily: 'var(--font-mono)', color: 'var(--stamp-gold)' }}>${data.total_spending.toFixed(2)}</div>
                            </Card>
                            <Card padding={14}>
                              <div style={statSubLabel}>Orders</div>
                              <div style={{ fontSize: '20px', fontWeight: 700, fontFamily: 'var(--font-mono)', color: 'var(--stamp-teal)' }}>{data.order_count}</div>
                            </Card>
                            <Card padding={14}>
                              <div style={statSubLabel}>Items</div>
                              <div style={{ fontSize: '20px', fontWeight: 700, fontFamily: 'var(--font-mono)', color: 'var(--stamp-ember)' }}>{data.item_count}</div>
                            </Card>
                            <Card padding={14}>
                              <div style={statSubLabel}>Avg order</div>
                              <div style={{ fontSize: '20px', fontWeight: 700, fontFamily: 'var(--font-mono)', color: 'var(--paper-dim)' }}>${data.avg_order_value.toFixed(2)}</div>
                            </Card>
                          </div>

                          {/* Charts */}
                          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(300px, 1fr))', gap: '16px', marginBottom: '20px' }}>
                            <Card padding={14}>
                              <h4 style={{ marginBottom: 12, fontSize: 12.5, fontFamily: 'var(--font-mono)', textTransform: 'uppercase', letterSpacing: '0.05em', color: 'var(--muted)' }}>Spending by category</h4>
                              <div style={{ height: '250px' }}>
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
                                    <Tooltip formatter={(value: any) => `$${value.toFixed(2)}`} contentStyle={TOOLTIP_STYLE} />
                                  </PieChart>
                                </ResponsiveContainer>
                              </div>
                            </Card>

                            <Card padding={14}>
                              <h4 style={{ marginBottom: 12, fontSize: 12.5, fontFamily: 'var(--font-mono)', textTransform: 'uppercase', letterSpacing: '0.05em', color: 'var(--muted)' }}>Orders by source</h4>
                              <div style={{ height: '250px' }}>
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
                          <Card style={{ marginBottom: '20px' }} padding={14}>
                            <h4 style={{ marginBottom: 12, fontSize: 12.5, fontFamily: 'var(--font-mono)', textTransform: 'uppercase', letterSpacing: '0.05em', color: 'var(--muted)' }}>Top items this month</h4>
                            <div style={{ maxHeight: '300px', overflowY: 'auto' }}>
                              {monthItems
                                .sort((a, b) => (b.total_price || 0) - (a.total_price || 0))
                                .slice(0, 10)
                                .map((item, idx2) => (
                                  <div
                                    key={idx2}
                                    style={{
                                      display: 'flex',
                                      justifyContent: 'space-between',
                                      alignItems: 'center',
                                      padding: '11px 4px',
                                      borderBottom: '1px solid var(--ink-700)',
                                    }}
                                  >
                                    <div style={{ flex: 1 }}>
                                      <Link to={`/items/${encodeURIComponent(item.name)}`} style={{ fontWeight: 600, color: 'var(--stamp-teal)', fontSize: 14 }}>
                                        {item.name}
                                      </Link>
                                      <div style={{ fontSize: '12px', color: 'var(--muted)', marginTop: '2px' }}>{item.category} · {item.source}</div>
                                    </div>
                                    <div style={{ textAlign: 'right' }}>
                                      <div style={{ fontWeight: 700, fontFamily: 'var(--font-mono)', color: 'var(--paper)' }}>${item.total_price?.toFixed(2)}</div>
                                      <div style={{ fontSize: '12px', color: 'var(--muted)' }}>Qty {item.quantity}</div>
                                    </div>
                                  </div>
                                ))}
                            </div>
                          </Card>

                          {/* Orders List */}
                          <Card padding={14}>
                            <h4 style={{ marginBottom: 12, fontSize: 12.5, fontFamily: 'var(--font-mono)', textTransform: 'uppercase', letterSpacing: '0.05em', color: 'var(--muted)' }}>Orders this month</h4>
                            <div style={{ overflowX: 'auto' }}>
                              <table style={{ width: '100%', borderCollapse: 'collapse' }}>
                                <thead>
                                  <tr style={{ borderBottom: '1px solid var(--ink-700)' }}>
                                    <th style={{ padding: '10px 8px', textAlign: 'left', fontSize: '11px', fontWeight: 600, color: 'var(--muted)', fontFamily: 'var(--font-mono)', textTransform: 'uppercase' }}>Date</th>
                                    <th style={{ padding: '10px 8px', textAlign: 'left', fontSize: '11px', fontWeight: 600, color: 'var(--muted)', fontFamily: 'var(--font-mono)', textTransform: 'uppercase' }}>Source</th>
                                    <th style={{ padding: '10px 8px', textAlign: 'right', fontSize: '11px', fontWeight: 600, color: 'var(--muted)', fontFamily: 'var(--font-mono)', textTransform: 'uppercase' }}>Total</th>
                                    <th style={{ padding: '10px 8px', textAlign: 'left', fontSize: '11px', fontWeight: 600, color: 'var(--muted)', fontFamily: 'var(--font-mono)', textTransform: 'uppercase' }}>Items</th>
                                  </tr>
                                </thead>
                                <tbody>
                                  {monthOrders.map((order) => (
                                    <React.Fragment key={order.id}>
                                      <tr style={{ borderBottom: '1px solid var(--ink-700)' }}>
                                        <td style={{ padding: '9px 8px', fontFamily: 'var(--font-mono)', fontSize: 13, color: 'var(--paper)' }}>{order.date}</td>
                                        <td style={{ padding: '9px 8px' }}>
                                          <span style={{ background: 'rgba(200, 155, 60, 0.15)', color: 'var(--stamp-gold)', padding: '3px 8px', borderRadius: '10px', fontSize: '11px', fontWeight: 600 }}>
                                            {order.source}
                                          </span>
                                        </td>
                                        <td style={{ padding: '9px 8px', textAlign: 'right', fontWeight: 700, fontFamily: 'var(--font-mono)', color: 'var(--paper)' }}>
                                          ${order.total?.toFixed(2)}
                                        </td>
                                        <td style={{ padding: '9px 8px' }}>
                                          <button
                                            onClick={() => toggleOrderItems(order.id)}
                                            style={{ background: 'transparent', color: 'var(--stamp-teal)', border: '1px solid var(--stamp-teal)', padding: '4px 12px', fontSize: '12px', fontWeight: 600 }}
                                          >
                                            {expandedOrderId === order.id ? 'Hide items' : 'View items'}
                                          </button>
                                        </td>
                                      </tr>
                                      {expandedOrderId === order.id && (
                                        <tr>
                                          <td colSpan={4} style={{ padding: '10px', background: 'var(--ink-800)' }}>
                                            {orderItems[order.id] ? (
                                              <div style={{ fontSize: '13px' }}>
                                                <strong style={{ color: 'var(--muted)', fontFamily: 'var(--font-mono)', fontSize: 11, textTransform: 'uppercase' }}>Items in this order</strong>
                                                <div style={{ marginTop: '8px' }}>
                                                  {orderItems[order.id].map((item, itemIdx) => (
                                                    <div
                                                      key={itemIdx}
                                                      style={{
                                                        padding: '8px',
                                                        background: 'var(--ink-900)',
                                                        marginBottom: '6px',
                                                        borderRadius: '6px',
                                                        display: 'flex',
                                                        justifyContent: 'space-between',
                                                        alignItems: 'center'
                                                      }}
                                                    >
                                                      <div style={{ flex: 1 }}>
                                                        <Link to={`/items/${encodeURIComponent(item.name)}`} style={{ fontWeight: 600, color: 'var(--stamp-teal)' }}>
                                                          {item.name}
                                                        </Link>
                                                        <div style={{ fontSize: '11px', color: 'var(--muted)', marginTop: '2px' }}>{item.category}</div>
                                                      </div>
                                                      <div style={{ textAlign: 'right' }}>
                                                        <div style={{ fontWeight: 700, fontFamily: 'var(--font-mono)', color: 'var(--paper)' }}>${item.price?.toFixed(2)} × {item.quantity}</div>
                                                        <div style={{ fontSize: '11px', color: 'var(--muted)' }}>Total ${item.total_price?.toFixed(2)}</div>
                                                      </div>
                                                    </div>
                                                  ))}
                                                </div>
                                              </div>
                                            ) : (
                                              <div style={{ textAlign: 'center', color: 'var(--muted)' }}>Loading items…</div>
                                            )}
                                          </td>
                                        </tr>
                                      )}
                                    </React.Fragment>
                                  ))}
                                </tbody>
                              </table>
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
          <div style={statSubLabel}>Total months</div>
          <div style={{ fontSize: '26px', fontWeight: 700, fontFamily: 'var(--font-mono)', color: 'var(--stamp-gold)' }}>{monthlyData.length}</div>
        </Card>
        <Card style={{ textAlign: 'center' }}>
          <div style={statSubLabel}>Highest month</div>
          <div style={{ fontSize: '20px', fontWeight: 700, fontFamily: 'var(--font-mono)', color: 'var(--stamp-teal)' }}>
            ${monthlyData.length > 0 ? Math.max(...monthlyData.map(m => m.total_spending)).toFixed(2) : '0.00'}
          </div>
          <div style={{ fontSize: '11px', color: 'var(--muted)', marginTop: '4px' }}>
            {monthlyData.length > 0 ? monthlyData.reduce((max, m) => m.total_spending > max.total_spending ? m : max).month : 'N/A'}
          </div>
        </Card>
        <Card style={{ textAlign: 'center' }}>
          <div style={statSubLabel}>Lowest month</div>
          <div style={{ fontSize: '20px', fontWeight: 700, fontFamily: 'var(--font-mono)', color: 'var(--stamp-ember)' }}>
            ${monthlyData.length > 0 ? Math.min(...monthlyData.map(m => m.total_spending)).toFixed(2) : '0.00'}
          </div>
          <div style={{ fontSize: '11px', color: 'var(--muted)', marginTop: '4px' }}>
            {monthlyData.length > 0 ? monthlyData.reduce((min, m) => m.total_spending < min.total_spending ? m : min).month : 'N/A'}
          </div>
        </Card>
        <Card style={{ textAlign: 'center' }}>
          <div style={statSubLabel}>Avg per month</div>
          <div style={{ fontSize: '20px', fontWeight: 700, fontFamily: 'var(--font-mono)', color: 'var(--paper-dim)' }}>
            ${monthlyData.length > 0 ? (monthlyData.reduce((sum, m) => sum + m.total_spending, 0) / monthlyData.length).toFixed(2) : '0.00'}
          </div>
        </Card>
      </div>
    </div>
  );
};

const statSubLabel: React.CSSProperties = { fontSize: '11px', color: 'var(--muted)', marginBottom: '8px', fontFamily: 'var(--font-mono)', textTransform: 'uppercase', letterSpacing: '0.04em' };

const thStyle = (align: 'left' | 'right' | 'center'): React.CSSProperties => ({
  padding: '13px 14px',
  textAlign: align,
  fontWeight: 600,
  fontSize: 11,
  fontFamily: 'var(--font-mono)',
  textTransform: 'uppercase',
  letterSpacing: '0.05em',
  color: 'var(--muted)',
});

export default Months;
