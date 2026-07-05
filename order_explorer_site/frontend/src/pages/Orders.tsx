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
import Badge from '../components/ui/Badge';
import Spinner from '../components/ui/Spinner';
import ResponsiveTable from '../components/ui/ResponsiveTable';
import type { TableColumn } from '../components/ui/ResponsiveTable';

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

const SORT_FIELDS: { field: SortField; label: string }[] = [
  { field: 'date', label: 'Date' },
  { field: 'source', label: 'Source' },
  { field: 'total', label: 'Total' },
];

// Fetches and displays a single order's line items, lazily on first expand,
// and caches the result in the parent's `itemsCache` so re-expanding is instant.
const OrderItemsPanel: React.FC<{
  order: Order;
  itemsCache: Record<string, Item[]>;
  onNeedItems: (orderId: string) => void;
}> = ({ order, itemsCache, onNeedItems }) => {
  useEffect(() => {
    onNeedItems(order.id);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [order.id]);

  const items = itemsCache[order.id];

  return (
    <div>
      <div className="mb-2 font-mono text-[11px] uppercase tracking-wider text-muted">Order items</div>
      {items ? (
        items.length > 0 ? (
          <ul className="flex flex-col gap-1.5">
            {items.map((item, idx) => (
              <li key={idx} className="text-sm text-ink-dim">
                <span className="font-medium text-ink">{item.name}</span>{' '}
                <span className="font-mono text-muted">${item.price}</span> x {item.quantity} ={' '}
                <span className="font-mono font-semibold text-ink">${item.total_price}</span>
                <span className="ml-2 text-xs text-muted">({item.category})</span>
              </li>
            ))}
          </ul>
        ) : (
          <p className="text-sm text-muted">No details available.</p>
        )
      ) : (
        <Spinner size="sm" label="Loading items…" />
      )}
    </div>
  );
};

const Orders: React.FC = () => {
  const [orders, setOrders] = useState<Order[]>([]);
  const [loading, setLoading] = useState(true);
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

  const handleNeedItems = (orderId: string) => {
    setOrderItems(prev => {
      if (prev[orderId]) return prev;
      fetchOrderItems(orderId)
        .then(items => setOrderItems(cur => ({ ...cur, [orderId]: items })))
        .catch(err => console.error('Failed to fetch items', err));
      return prev;
    });
  };

  if (loading) {
    return (
      <div className="mx-auto max-w-[1200px] px-4 py-6 md:px-6">
        <Spinner label="Loading orders…" />
      </div>
    );
  }

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

  const columns: TableColumn<Order>[] = [
    {
      key: 'date',
      header: 'Date',
      primary: true,
      render: (o) => <span className="font-mono">{o.date}</span>,
    },
    {
      key: 'source',
      header: 'Source',
      render: (o) => <Badge tone="gold">{o.source}</Badge>,
    },
    {
      key: 'original_id',
      header: 'Order ID',
      render: (o) => <span className="font-mono text-xs text-muted">{o.original_id}</span>,
    },
    {
      key: 'items_summary',
      header: 'Details',
      render: (o) => <span className="text-ink-dim">{o.items_summary || 'View items'}</span>,
    },
    {
      key: 'total',
      header: 'Total',
      className: 'text-right',
      render: (o) => <span className="font-mono font-semibold text-ink">${o.total.toFixed(2)}</span>,
    },
  ];

  return (
    <div className="mx-auto max-w-[1200px] px-4 py-6 md:px-6">
      <PageHeader eyebrow="Ledger / Orders" title="Order timeline" />

      <Card className="mb-8">
        <div className="h-64 sm:h-80 md:h-96">
          <Bar data={chartData} options={chartOptions} />
        </div>
      </Card>

      <div className="mb-4 flex flex-wrap items-center justify-between gap-3">
        <h2 className="font-mono text-sm uppercase tracking-wider text-muted">All orders</h2>
        <div className="flex flex-wrap items-center gap-2">
          <span className="font-mono text-[11px] uppercase tracking-wider text-muted">Sort</span>
          {SORT_FIELDS.map(({ field, label }) => (
            <button
              key={field}
              type="button"
              onClick={() => handleSort(field)}
              className={`rounded-md px-3 py-1.5 text-xs font-semibold ${
                sortField === field ? 'bg-signal text-white' : 'bg-surface-dim text-muted'
              }`}
            >
              {label} {sortField === field ? (sortDirection === 'asc' ? '↑' : '↓') : ''}
            </button>
          ))}
        </div>
      </div>

      <ResponsiveTable
        columns={columns}
        rows={sortedOrders}
        rowKey={(o) => o.id}
        expandedContent={(o) => (
          <OrderItemsPanel order={o} itemsCache={orderItems} onNeedItems={handleNeedItems} />
        )}
        emptyTitle="No orders yet"
      />
    </div>
  );
};

export default Orders;
