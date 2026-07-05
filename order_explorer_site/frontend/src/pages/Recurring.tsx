import React, { useEffect, useState } from 'react';
import { api } from '../api';
import { Link } from 'react-router-dom';
import PageHeader from '../components/ui/PageHeader';
import Card from '../components/ui/Card';
import Badge from '../components/ui/Badge';
import Spinner from '../components/ui/Spinner';
import ResponsiveTable from '../components/ui/ResponsiveTable';
import type { TableColumn } from '../components/ui/ResponsiveTable';

interface RecurringItem {
  name: string;
  purchase_count: number;
  total_spent: number;
  avg_price: number;
  category: string;
  sources: string[];
  avg_days_between: number | null;
  last_purchase: string | null;
  first_purchase: string | null;
}

const sortBtnClass = (active: boolean): string =>
  `rounded-md px-4 py-1.5 text-sm font-semibold ${active ? 'bg-alert-amber text-white' : 'border border-line text-muted'}`;

const Recurring: React.FC = () => {
  const [items, setItems] = useState<RecurringItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [sortBy, setSortBy] = useState<'count' | 'frequency' | 'total'>('count');

  useEffect(() => {
    api.get<RecurringItem[]>('/recurring')
      .then(response => {
        setItems(response.data);
        setLoading(false);
      })
      .catch(err => {
        console.error('Failed to load recurring items', err);
        setLoading(false);
      });
  }, []);

  if (loading) {
    return (
      <div className="mx-auto max-w-[1200px] px-4 py-6 md:px-6">
        <Spinner label="Loading recurring items…" />
      </div>
    );
  }

  const sortedItems = [...items].sort((a, b) => {
    if (sortBy === 'count') {
      return b.purchase_count - a.purchase_count;
    } else if (sortBy === 'frequency') {
      const aFreq = a.avg_days_between ?? Infinity;
      const bFreq = b.avg_days_between ?? Infinity;
      return aFreq - bFreq;
    } else {
      return b.total_spent - a.total_spent;
    }
  });

  const getDaysSinceLastPurchase = (lastPurchase: string | null): number | null => {
    if (!lastPurchase) return null;
    try {
      const lastDate = new Date(lastPurchase);
      const now = new Date();
      const diffTime = Math.abs(now.getTime() - lastDate.getTime());
      const diffDays = Math.ceil(diffTime / (1000 * 60 * 60 * 24));
      return diffDays;
    } catch {
      return null;
    }
  };

  const getFrequencyLabel = (avgDays: number | null): string => {
    if (!avgDays) return 'Unknown';
    if (avgDays < 7) return 'Weekly';
    if (avgDays < 30) return 'Bi-weekly';
    if (avgDays < 60) return 'Monthly';
    if (avgDays < 120) return 'Bi-monthly';
    if (avgDays < 365) return 'Quarterly';
    return 'Yearly';
  };

  const getReorderAlert = (item: RecurringItem): boolean => {
    if (!item.avg_days_between || !item.last_purchase) return false;
    const daysSince = getDaysSinceLastPurchase(item.last_purchase);
    if (daysSince === null) return false;
    return daysSince >= item.avg_days_between * 0.9;
  };

  const reorderAlerts = sortedItems.filter(getReorderAlert);

  const columns: TableColumn<RecurringItem>[] = [
    {
      key: 'name',
      header: 'Item',
      primary: true,
      render: (item) => {
        const isAlert = getReorderAlert(item);
        return (
          <div>
            <Link to={`/items/${encodeURIComponent(item.name)}`} className="font-bold text-signal hover:underline">
              {item.name}
            </Link>
            {isAlert && <span className="ml-2 align-middle"><Badge tone="ember">Reorder</Badge></span>}
            <p className="mt-1 text-xs text-muted">{item.category} · {item.sources.join(', ')}</p>
          </div>
        );
      },
    },
    {
      key: 'purchase_count',
      header: 'Purchases',
      className: 'text-right',
      render: (item) => <span className="font-mono font-bold text-alert-amber">{item.purchase_count}x</span>,
    },
    {
      key: 'frequency',
      header: 'Frequency',
      render: (item) => (
        <div>
          <div className="text-sm font-bold text-ink">{getFrequencyLabel(item.avg_days_between)}</div>
          {item.avg_days_between && <div className="text-xs text-muted">Every ~{item.avg_days_between.toFixed(0)} days</div>}
        </div>
      ),
    },
    {
      key: 'avg_price',
      header: 'Avg price',
      className: 'text-right',
      render: (item) => <span className="font-mono font-bold text-ink">${item.avg_price.toFixed(2)}</span>,
    },
    {
      key: 'total_spent',
      header: 'Total spent',
      className: 'text-right',
      render: (item) => <span className="font-mono font-bold text-alert-amber">${item.total_spent.toFixed(2)}</span>,
    },
    {
      key: 'last_purchase',
      header: 'Last purchase',
      render: (item) => {
        const daysSince = getDaysSinceLastPurchase(item.last_purchase);
        return (
          <div>
            <div className="text-sm font-medium text-ink">{daysSince !== null ? `${daysSince} days ago` : 'Unknown'}</div>
            {item.last_purchase && <div className="text-xs text-muted">{new Date(item.last_purchase).toLocaleDateString()}</div>}
          </div>
        );
      },
    },
  ];

  return (
    <div className="mx-auto max-w-[1200px] px-4 py-6 md:px-6">
      <PageHeader eyebrow="Ledger / Recurring" title="Recurring items & subscriptions" />

      {/* Summary Cards */}
      <div className="mb-7 grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
        <Card>
          <h3 className="m-0 font-mono text-[11px] uppercase tracking-wider text-muted">Recurring items</h3>
          <p className="mt-2.5 font-mono text-3xl font-bold text-alert-amber">{items.length}</p>
          <p className="mt-1 text-sm text-muted">purchased multiple times</p>
        </Card>

        <Card>
          <h3 className="m-0 font-mono text-[11px] uppercase tracking-wider text-muted">Reorder alerts</h3>
          <p className={`mt-2.5 font-mono text-3xl font-bold ${reorderAlerts.length > 0 ? 'text-alert-red' : 'text-alert-green'}`}>
            {reorderAlerts.length}
          </p>
          <p className="mt-1 text-sm text-muted">
            {reorderAlerts.length > 0 ? 'items may need reordering' : 'all items up to date'}
          </p>
        </Card>

        {items.length > 0 && (
          <>
            <Card>
              <h3 className="m-0 font-mono text-[11px] uppercase tracking-wider text-muted">Most purchased</h3>
              <p className="mt-2.5 text-lg font-bold text-ink">{items[0].name}</p>
              <p className="mt-1 text-sm text-muted">{items[0].purchase_count} times</p>
            </Card>

            <Card>
              <h3 className="m-0 font-mono text-[11px] uppercase tracking-wider text-muted">Total on recurring</h3>
              <p className="mt-2.5 font-mono text-3xl font-bold text-alert-amber">
                ${items.reduce((sum, item) => sum + item.total_spent, 0).toFixed(2)}
              </p>
            </Card>
          </>
        )}
      </div>

      {/* Reorder Alerts */}
      {reorderAlerts.length > 0 && (
        <Card className="mb-7 border-l-[3px] border-l-alert-red">
          <h2 className="mb-2 text-base font-semibold text-ink">Reorder alerts</h2>
          <p className="mb-4 text-sm text-muted">
            These items may need reordering based on your typical purchase frequency:
          </p>
          <div className="flex flex-col gap-2.5">
            {reorderAlerts.map(item => (
              <div
                key={item.name}
                className="flex items-center justify-between rounded-lg border border-line bg-surface-dim px-4 py-3"
              >
                <div>
                  <Link to={`/items/${encodeURIComponent(item.name)}`} className="text-sm font-semibold text-signal hover:underline">
                    {item.name}
                  </Link>
                  <p className="mt-1 text-xs text-muted">
                    Last purchased {getDaysSinceLastPurchase(item.last_purchase)} days ago · Typically every {item.avg_days_between?.toFixed(0)} days
                  </p>
                </div>
                <Badge tone="ember">Reorder</Badge>
              </div>
            ))}
          </div>
        </Card>
      )}

      {/* Sort Controls */}
      <Card className="mb-5 p-3.5 px-5">
        <div className="flex flex-wrap items-center gap-2.5">
          <span className="font-mono text-xs font-semibold uppercase text-muted">Sort by</span>
          <button type="button" onClick={() => setSortBy('count')} className={sortBtnClass(sortBy === 'count')}>Purchase count</button>
          <button type="button" onClick={() => setSortBy('frequency')} className={sortBtnClass(sortBy === 'frequency')}>Frequency</button>
          <button type="button" onClick={() => setSortBy('total')} className={sortBtnClass(sortBy === 'total')}>Total spent</button>
        </div>
      </Card>

      {/* Recurring Items List */}
      <h2 className="mb-4 font-mono text-xs uppercase tracking-wider text-muted">All recurring items</h2>
      <ResponsiveTable
        columns={columns}
        rows={sortedItems}
        rowKey={(item) => item.name}
        emptyTitle="No recurring items found"
        emptyDescription="Items appear here after being purchased multiple times."
      />
    </div>
  );
};

export default Recurring;
