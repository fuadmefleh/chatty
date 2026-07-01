import React, { useEffect, useState } from 'react';
import { fetchOrders, fetchOrderItems } from '../api';
import type { Order, Item } from '../api';
import {
  Chart as ChartJS,
  CategoryScale,
  LinearScale,
  BarElement,
  Title,
  Tooltip,
  Legend,
} from 'chart.js';
import type { TooltipItem } from 'chart.js';
import { Bar } from 'react-chartjs-2';
import PageHeader from '../components/ui/PageHeader';
import Card from '../components/ui/Card';

ChartJS.register(
  CategoryScale,
  LinearScale,
  BarElement,
  Title,
  Tooltip,
  Legend
);

type SortField = 'date' | 'source' | 'total';
type SortDirection = 'asc' | 'desc';

const ROW_ACTIVE = 'var(--ink-750)';
const ROW_EVEN = 'var(--ink-800)';
const ROW_ODD = 'var(--ink-900)';

const Orders: React.FC = () => {
  const [orders, setOrders] = useState<Order[]>([]);
  const [loading, setLoading] = useState(true);
  const [expandedOrderId, setExpandedOrderId] = useState<string | null>(null);
  const [orderItems, setOrderItems] = useState<Record<string, Item[]>>({});
  const [sortField, setSortField] = useState<SortField>('date');
  const [sortDirection, setSortDirection] = useState<SortDirection>('desc');

  useEffect(() => {
    fetchOrders().then(data => {
      setOrders(data);
      setLoading(false);
    });
  }, []);

  const handleSort = (field: SortField) => {
    if (sortField === field) {
      setSortDirection(sortDirection === 'asc' ? 'desc' : 'asc');
    } else {
      setSortField(field);
      setSortDirection('desc');
    }
  };

  const getSortIcon = (field: SortField) => {
    if (sortField !== field) return ' ⇅';
    return sortDirection === 'asc' ? ' ↑' : ' ↓';
  };

  const toggleOrder = async (orderId: string) => {
    if (expandedOrderId === orderId) {
      setExpandedOrderId(null);
    } else {
      setExpandedOrderId(orderId);
      if (!orderItems[orderId]) {
        try {
          const items = await fetchOrderItems(orderId);
          setOrderItems(prev => ({ ...prev, [orderId]: items }));
        } catch (err) {
          console.error("Failed to fetch items", err);
        }
      }
    }
  };

  if (loading) return <div style={{ padding: 24, color: 'var(--muted)' }}>Loading orders…</div>;

  // Aggregate for timeline (Monthly)
  const monthlyData = orders.reduce((acc, order) => {
    if (!order.date) return acc;
    const date = order.date.substring(0, 7); // YYYY-MM
    if (!acc[date]) acc[date] = 0;
    acc[date] += order.total;
    return acc;
  }, {} as Record<string, number>);

  const sortedMonths = Object.keys(monthlyData).sort();

  const chartData = {
    labels: sortedMonths,
    datasets: [
      {
        label: 'Monthly Spending',
        data: sortedMonths.map(month => monthlyData[month]),
        backgroundColor: 'rgba(200, 155, 60, 0.75)',
        borderColor: '#c89b3c',
        borderWidth: 1,
        borderRadius: 4,
        hoverBackgroundColor: 'rgba(200, 155, 60, 0.95)',
      },
    ],
  };

  const chartOptions = {
    responsive: true,
    maintainAspectRatio: false,
    plugins: {
      legend: {
        display: true,
        position: 'top' as const,
        labels: { color: '#8b8f92', font: { family: 'IBM Plex Mono' } },
      },
      title: {
        display: false,
      },
      tooltip: {
        callbacks: {
          label: function (context: TooltipItem<'bar'>) {
            return `$${(context.parsed.y as number).toFixed(2)}`;
          }
        }
      }
    },
    scales: {
      x: { ticks: { color: '#8b8f92' }, grid: { color: '#262c33' } },
      y: {
        beginAtZero: true,
        ticks: {
          color: '#8b8f92',
          callback: function (value: number | string) {
            return '$' + value;
          }
        },
        grid: { color: '#262c33' },
      }
    }
  };

  // Sort orders
  const sortedOrders = [...orders].sort((a, b) => {
    let comparison = 0;
    if (sortField === 'date') {
      comparison = (a.date || '').localeCompare(b.date || '');
    } else if (sortField === 'source') {
      comparison = (a.source || '').localeCompare(b.source || '');
    } else if (sortField === 'total') {
      comparison = a.total - b.total;
    }
    return sortDirection === 'asc' ? comparison : -comparison;
  });

  return (
    <div style={{ padding: '24px 24px 48px' }}>
      <PageHeader eyebrow="Ledger / Orders" title="Order timeline" />

      <Card style={{ marginBottom: 32 }}>
        <div style={{ height: '360px' }}>
          <Bar data={chartData} options={chartOptions} />
        </div>
      </Card>

      <h2 style={{ fontSize: 16, fontFamily: 'var(--font-mono)', letterSpacing: '0.06em', textTransform: 'uppercase', color: 'var(--muted)', marginBottom: 16 }}>
        All orders
      </h2>
      <div style={{ overflowX: 'auto', border: '1px solid var(--ink-700)', borderRadius: 10 }}>
        <table style={{ width: '100%', borderCollapse: 'collapse' }}>
          <thead>
            <tr style={{ background: 'var(--ink-800)' }}>
              <th
                onClick={() => handleSort('date')}
                style={{ padding: '13px 14px', textAlign: 'left', fontWeight: 600, fontSize: 12, fontFamily: 'var(--font-mono)', textTransform: 'uppercase', letterSpacing: '0.04em', color: 'var(--muted)', cursor: 'pointer', userSelect: 'none' }}
              >
                Date{getSortIcon('date')}
              </th>
              <th
                onClick={() => handleSort('source')}
                style={{ padding: '13px 14px', textAlign: 'left', fontWeight: 600, fontSize: 12, fontFamily: 'var(--font-mono)', textTransform: 'uppercase', letterSpacing: '0.04em', color: 'var(--muted)', cursor: 'pointer', userSelect: 'none' }}
              >
                Source{getSortIcon('source')}
              </th>
              <th style={{ padding: '13px 14px', textAlign: 'left', fontWeight: 600, fontSize: 12, fontFamily: 'var(--font-mono)', textTransform: 'uppercase', letterSpacing: '0.04em', color: 'var(--muted)' }}>Order ID</th>
              <th style={{ padding: '13px 14px', textAlign: 'left', fontWeight: 600, fontSize: 12, fontFamily: 'var(--font-mono)', textTransform: 'uppercase', letterSpacing: '0.04em', color: 'var(--muted)' }}>Details</th>
              <th
                onClick={() => handleSort('total')}
                style={{ padding: '13px 14px', textAlign: 'right', fontWeight: 600, fontSize: 12, fontFamily: 'var(--font-mono)', textTransform: 'uppercase', letterSpacing: '0.04em', color: 'var(--muted)', cursor: 'pointer', userSelect: 'none' }}
              >
                Total{getSortIcon('total')}
              </th>
            </tr>
          </thead>
          <tbody>
            {sortedOrders.map((order, idx) => (
              <React.Fragment key={order.id}>
                <tr
                  style={{
                    backgroundColor: expandedOrderId === order.id ? ROW_ACTIVE : idx % 2 === 0 ? ROW_EVEN : ROW_ODD,
                    transition: 'background-color 0.15s'
                  }}
                  onMouseEnter={(e) => e.currentTarget.style.backgroundColor = ROW_ACTIVE}
                  onMouseLeave={(e) => e.currentTarget.style.backgroundColor = expandedOrderId === order.id ? ROW_ACTIVE : idx % 2 === 0 ? ROW_EVEN : ROW_ODD}
                >
                  <td style={{ padding: '13px 14px', borderTop: '1px solid var(--ink-700)', fontFamily: 'var(--font-mono)', fontSize: 13, color: 'var(--paper)' }}>{order.date}</td>
                  <td style={{ padding: '13px 14px', borderTop: '1px solid var(--ink-700)' }}>
                    <span style={{
                      background: 'rgba(200, 155, 60, 0.15)',
                      color: 'var(--stamp-gold)',
                      padding: '3px 10px',
                      borderRadius: 12,
                      fontSize: 12,
                      fontWeight: 600
                    }}>
                      {order.source}
                    </span>
                  </td>
                  <td style={{ padding: '13px 14px', borderTop: '1px solid var(--ink-700)', fontFamily: 'var(--font-mono)', fontSize: 12, color: 'var(--muted)' }}>{order.original_id}</td>
                  <td style={{ padding: '13px 14px', borderTop: '1px solid var(--ink-700)' }}>
                    <span
                      onClick={() => toggleOrder(order.id)}
                      style={{
                        cursor: 'pointer',
                        color: 'var(--stamp-teal)',
                        fontWeight: 500,
                        borderBottom: '1px solid transparent',
                      }}
                      onMouseEnter={(e) => e.currentTarget.style.borderBottom = '1px solid var(--stamp-teal)'}
                      onMouseLeave={(e) => e.currentTarget.style.borderBottom = '1px solid transparent'}
                    >
                      {order.items_summary || "View items"}
                    </span>
                  </td>
                  <td style={{ padding: '13px 14px', borderTop: '1px solid var(--ink-700)', textAlign: 'right', fontWeight: 600, fontFamily: 'var(--font-mono)', color: 'var(--paper)' }}>
                    ${order.total.toFixed(2)}
                  </td>
                </tr>
                {expandedOrderId === order.id && (
                  <tr>
                    <td colSpan={5} style={{ padding: '18px', background: 'var(--ink-900)', borderTop: '1px solid var(--ink-700)' }}>
                      <strong style={{ color: 'var(--stamp-gold)', fontSize: 12, fontFamily: 'var(--font-mono)', textTransform: 'uppercase', letterSpacing: '0.06em' }}>Order items</strong>
                      {orderItems[order.id] ? (
                        <ul style={{ marginTop: '10px', marginLeft: '20px', padding: 0 }}>
                          {orderItems[order.id].length > 0 ? (
                            orderItems[order.id].map((item, idx) => (
                              <li key={idx} style={{ marginBottom: '6px', color: 'var(--paper-dim)', fontSize: 13.5 }}>
                                <span style={{ fontWeight: 500, color: 'var(--paper)' }}>{item.name}</span> -
                                <span style={{ color: 'var(--muted)', fontFamily: 'var(--font-mono)' }}> ${item.price}</span> x {item.quantity} =
                                <span style={{ fontWeight: 600, fontFamily: 'var(--font-mono)', color: 'var(--paper)' }}> ${item.total_price}</span>
                                <span style={{ marginLeft: '8px', fontSize: '12px', color: 'var(--muted)' }}>({item.category})</span>
                              </li>
                            ))
                          ) : (
                            <li style={{ color: 'var(--muted)' }}>No details available.</li>
                          )}
                        </ul>
                      ) : (
                        <div style={{ marginTop: '10px', color: 'var(--muted)' }}>Loading items…</div>
                      )}
                    </td>
                  </tr>
                )}
              </React.Fragment>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
};

export default Orders;
