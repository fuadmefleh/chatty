import React, { useEffect, useState, useMemo, useCallback } from 'react';
import { useParams, Link } from 'react-router-dom';
import axios from 'axios';
import { fetchItemHistory, fetchAllCategories, updateItemCategory } from '../api';
import type { Item } from '../api';
import {
  Chart as ChartJS,
  CategoryScale,
  LinearScale,
  PointElement,
  LineElement,
  BarElement,
  Title,
  Tooltip,
  Legend,
  Filler,
} from 'chart.js';
import type { TooltipItem } from 'chart.js';
import { Line, Bar } from 'react-chartjs-2';
import PageHeader from '../components/ui/PageHeader';
import Card from '../components/ui/Card';
import Badge from '../components/ui/Badge';
import StatCard from '../components/ui/StatCard';
import Spinner from '../components/ui/Spinner';
import EmptyState from '../components/ui/EmptyState';
import ResponsiveTable from '../components/ui/ResponsiveTable';
import type { TableColumn } from '../components/ui/ResponsiveTable';

ChartJS.register(
  CategoryScale,
  LinearScale,
  PointElement,
  LineElement,
  BarElement,
  Title,
  Tooltip,
  Legend,
  Filler
);

type SortField = 'date' | 'quantity' | 'price' | 'total' | 'source';
type SortDirection = 'asc' | 'desc';
type HistoryRow = Item & { _idx: number };

const FALLBACK_AXIS_COLOR = '#8b8f92';
const FALLBACK_GRID_COLOR = '#88888833';

// Charts render to a <canvas>, so they can't pick up Tailwind classes — read
// the current theme's actual token values instead, and keep them in sync
// when the user flips light/dark mode.
const readChartColors = () => {
  if (typeof window === 'undefined') {
    return { axis: FALLBACK_AXIS_COLOR, grid: FALLBACK_GRID_COLOR };
  }
  const styles = getComputedStyle(document.documentElement);
  return {
    axis: styles.getPropertyValue('--muted').trim() || FALLBACK_AXIS_COLOR,
    grid: styles.getPropertyValue('--line').trim() || FALLBACK_GRID_COLOR,
  };
};

const useChartColors = () => {
  const [colors, setColors] = useState(readChartColors);
  useEffect(() => {
    const observer = new MutationObserver(() => setColors(readChartColors()));
    observer.observe(document.documentElement, { attributes: true, attributeFilter: ['class'] });
    return () => observer.disconnect();
  }, []);
  return colors;
};

const ChartCard: React.FC<React.PropsWithChildren<{ title: string }>> = ({ title, children }) => (
  <Card>
    <h3 className="mb-4 font-mono text-[13px] uppercase tracking-wider text-muted">{title}</h3>
    <div className="h-[300px]">{children}</div>
  </Card>
);

const ItemDetail: React.FC = () => {
  const { name } = useParams<{ name: string }>();
  const [history, setHistory] = useState<Item[]>([]);
  const [loading, setLoading] = useState(true);
  const [sortField, setSortField] = useState<SortField>('date');
  const [sortDirection, setSortDirection] = useState<SortDirection>('desc');
  const [availableCategories, setAvailableCategories] = useState<string[]>([]);
  const [editingRow, setEditingRow] = useState<number | null>(null);
  const [tempCategory, setTempCategory] = useState<string>('');
  const [updating, setUpdating] = useState(false);
  const chartColors = useChartColors();

  useEffect(() => {
    if (name) {
      fetchItemHistory(name).then(data => {
        setHistory(data);
        setLoading(false);
      });
      fetchAllCategories().then(categories => {
        setAvailableCategories(categories);
      });
    }
  }, [name]);

  const handleEditCategory = useCallback((index: number, currentCategory: string) => {
    setEditingRow(index);
    setTempCategory(currentCategory || '');
  }, []);

  const handleCancelEdit = useCallback(() => {
    setEditingRow(null);
    setTempCategory('');
  }, []);

  const handleSaveCategory = useCallback(async (item: Item) => {
    if (!tempCategory || tempCategory === item.category) {
      handleCancelEdit();
      return;
    }

    if (!item.name) {
      alert('Cannot update category: item name is missing');
      handleCancelEdit();
      return;
    }

    setUpdating(true);
    try {
      await updateItemCategory(item.name, tempCategory);
      setHistory(prevHistory =>
        prevHistory.map(h =>
          h.name === item.name ? { ...h, category: tempCategory } : h
        )
      );
      setEditingRow(null);
      setTempCategory('');
      alert(`Category updated to "${tempCategory}" for all instances of this item`);
    } catch (error) {
      console.error('Failed to update category:', error);
      const detail = axios.isAxiosError(error) ? error.response?.data?.detail : undefined;
      alert(`Failed to update category: ${detail || (error instanceof Error ? error.message : String(error))}`);
    } finally {
      setUpdating(false);
    }
  }, [tempCategory, handleCancelEdit]);

  const { monthSpending, yearSpending, allTimeSpending, avgPrice, monthPurchasesCount, yearPurchasesCount } = useMemo(() => {
    const now = new Date();
    const currentMonth = `${now.getFullYear()}-${String(now.getMonth() + 1).padStart(2, '0')}`;
    const currentYear = `${now.getFullYear()}`;

    const monthPurchases = history.filter(h => h.date?.startsWith(currentMonth));
    const yearPurchases = history.filter(h => h.date?.startsWith(currentYear));

    const monthSpend = monthPurchases.reduce((sum, h) => sum + ((h.price || 0) * (h.quantity || 1)), 0);
    const yearSpend = yearPurchases.reduce((sum, h) => sum + ((h.price || 0) * (h.quantity || 1)), 0);
    const allTimeSpend = history.reduce((sum, h) => sum + ((h.price || 0) * (h.quantity || 1)), 0);
    const avg = history.length > 0 ? history.reduce((sum, h) => sum + (h.price || 0), 0) / history.length : 0;

    return {
      monthSpending: monthSpend,
      yearSpending: yearSpend,
      allTimeSpending: allTimeSpend,
      avgPrice: avg,
      monthPurchasesCount: monthPurchases.length,
      yearPurchasesCount: yearPurchases.length
    };
  }, [history]);

  const sortedHistory = useMemo(() => [...history].sort((a, b) => {
    let comparison = 0;
    if (sortField === 'date') {
      comparison = (a.date || '').localeCompare(b.date || '');
    } else if (sortField === 'quantity') {
      comparison = (a.quantity || 0) - (b.quantity || 0);
    } else if (sortField === 'price') {
      comparison = (a.price || 0) - (b.price || 0);
    } else if (sortField === 'total') {
      const totalA = (a.price || 0) * (a.quantity || 1);
      const totalB = (b.price || 0) * (b.quantity || 1);
      comparison = totalA - totalB;
    } else if (sortField === 'source') {
      comparison = (a.source || '').localeCompare(b.source || '');
    }
    return sortDirection === 'asc' ? comparison : -comparison;
  }), [history, sortField, sortDirection]);

  const rows: HistoryRow[] = useMemo(
    () => sortedHistory.map((h, i) => ({ ...h, _idx: i })),
    [sortedHistory]
  );

  const { priceChartData, qtyChartData } = useMemo(() => {
    const priceData = {
      labels: sortedHistory.map(h => h.date),
      datasets: [
        {
          label: 'Price',
          data: sortedHistory.map(h => h.price),
          borderColor: '#c89b3c',
          backgroundColor: 'rgba(200, 155, 60, 0.12)',
          borderWidth: 2,
          tension: 0.4,
          fill: true,
          pointRadius: 5,
          pointHoverRadius: 7,
          pointBackgroundColor: '#c89b3c',
          pointBorderColor: '#14181c',
          pointBorderWidth: 2,
        },
      ],
    };

    const qtyMap: Record<string, number> = {};
    history.forEach(h => {
      if (h.date) {
        const month = h.date.substring(0, 7);
        qtyMap[month] = (qtyMap[month] || 0) + (h.quantity || 0);
      }
    });
    const sortedMonths = Object.keys(qtyMap).sort();

    const qtyData = {
      labels: sortedMonths,
      datasets: [
        {
          label: 'Quantity purchased',
          data: sortedMonths.map(month => qtyMap[month]),
          backgroundColor: 'rgba(216, 96, 63, 0.75)',
          borderColor: '#d8603f',
          borderWidth: 1,
          borderRadius: 4,
          hoverBackgroundColor: 'rgba(216, 96, 63, 0.95)',
        },
      ],
    };

    return {
      priceChartData: priceData,
      qtyChartData: qtyData
    };
  }, [sortedHistory, history]);

  const priceChartOptions = {
    responsive: true,
    maintainAspectRatio: false,
    plugins: {
      legend: { display: true, position: 'top' as const, labels: { color: chartColors.axis } },
      tooltip: {
        callbacks: {
          label: function (context: TooltipItem<'line'>) {
            return `Price: $${context.parsed.y?.toFixed(2)}`;
          }
        }
      }
    },
    scales: {
      x: { ticks: { color: chartColors.axis }, grid: { color: chartColors.grid } },
      y: {
        beginAtZero: true,
        ticks: { color: chartColors.axis, callback: function (value: number | string) { return '$' + value; } },
        grid: { color: chartColors.grid },
      }
    }
  };

  const qtyChartOptions = {
    responsive: true,
    maintainAspectRatio: false,
    plugins: {
      legend: { display: true, position: 'top' as const, labels: { color: chartColors.axis } },
    },
    scales: {
      x: { ticks: { color: chartColors.axis }, grid: { color: chartColors.grid } },
      y: { beginAtZero: true, ticks: { color: chartColors.axis }, grid: { color: chartColors.grid } },
    }
  };

  const { qtyYearChartData, spendingMonthChartData, spendingYearChartData } = useMemo(() => {
    const qtyYearMap: Record<string, number> = {};
    history.forEach((h: Item) => {
      if (h.date) {
        const year = h.date.substring(0, 4);
        qtyYearMap[year] = (qtyYearMap[year] || 0) + (h.quantity || 0);
      }
    });
    const sortedYears = Object.keys(qtyYearMap).sort();

    const qtyYear = {
      labels: sortedYears,
      datasets: [
        {
          label: 'Quantity purchased (yearly)',
          data: sortedYears.map(year => qtyYearMap[year]),
          backgroundColor: 'rgba(79, 168, 160, 0.75)',
          borderColor: '#4fa8a0',
          borderWidth: 1,
          borderRadius: 4,
          hoverBackgroundColor: 'rgba(79, 168, 160, 0.95)',
        },
      ],
    };

    const spendingMonthMap: Record<string, number> = {};
    history.forEach((h: Item) => {
      if (h.date) {
        const month = h.date.substring(0, 7);
        const spending = (h.price || 0) * (h.quantity || 1);
        spendingMonthMap[month] = (spendingMonthMap[month] || 0) + spending;
      }
    });
    const sortedSpendingMonths = Object.keys(spendingMonthMap).sort();

    const spendingMonth = {
      labels: sortedSpendingMonths,
      datasets: [
        {
          label: 'Spending per month',
          data: sortedSpendingMonths.map(month => spendingMonthMap[month]),
          backgroundColor: 'rgba(200, 155, 60, 0.75)',
          borderColor: '#c89b3c',
          borderWidth: 1,
          borderRadius: 4,
          hoverBackgroundColor: 'rgba(200, 155, 60, 0.95)',
        },
      ],
    };

    const spendingYearMap: Record<string, number> = {};
    history.forEach((h: Item) => {
      if (h.date) {
        const year = h.date.substring(0, 4);
        const spending = (h.price || 0) * (h.quantity || 1);
        spendingYearMap[year] = (spendingYearMap[year] || 0) + spending;
      }
    });
    const sortedSpendingYears = Object.keys(spendingYearMap).sort();

    const spendingYear = {
      labels: sortedSpendingYears,
      datasets: [
        {
          label: 'Spending per year',
          data: sortedSpendingYears.map(year => spendingYearMap[year]),
          backgroundColor: 'rgba(232, 196, 120, 0.75)',
          borderColor: '#e8c478',
          borderWidth: 1,
          borderRadius: 4,
          hoverBackgroundColor: 'rgba(232, 196, 120, 0.95)',
        },
      ],
    };

    return {
      qtyYearChartData: qtyYear,
      spendingMonthChartData: spendingMonth,
      spendingYearChartData: spendingYear
    };
  }, [history]);

  const spendingChartOptions = {
    responsive: true,
    maintainAspectRatio: false,
    plugins: {
      legend: { display: true, position: 'top' as const, labels: { color: chartColors.axis } },
      tooltip: {
        callbacks: {
          label: function (context: TooltipItem<'bar'>) {
            return `Spending: $${context.parsed.y?.toFixed(2)}`;
          }
        }
      }
    },
    scales: {
      x: { ticks: { color: chartColors.axis }, grid: { color: chartColors.grid } },
      y: {
        beginAtZero: true,
        ticks: { color: chartColors.axis, callback: function (value: number | string) { return '$' + value; } },
        grid: { color: chartColors.grid },
      }
    }
  };

  const columns: TableColumn<HistoryRow>[] = [
    {
      key: 'date',
      header: 'Date',
      primary: true,
      render: (row) => <span className="font-mono text-sm text-ink">{row.date}</span>,
    },
    {
      key: 'category',
      header: 'Category',
      render: (row) => {
        const isEditing = editingRow === row._idx;
        if (isEditing) {
          return (
            <div className="flex items-center gap-2">
              <div className="relative flex-1">
                <input
                  type="text"
                  list={`categories-${row._idx}`}
                  value={tempCategory}
                  onChange={(e) => setTempCategory(e.target.value)}
                  disabled={updating}
                  placeholder="Type or select category"
                  className="w-full rounded-md border border-line bg-surface px-2 py-1 text-sm"
                />
                <datalist id={`categories-${row._idx}`}>
                  {availableCategories.map(cat => (
                    <option key={cat} value={cat} />
                  ))}
                </datalist>
              </div>
              <button
                type="button"
                onClick={() => { handleSaveCategory(row); }}
                disabled={updating || !tempCategory.trim()}
                className="rounded-md bg-alert-green px-2.5 py-1 text-xs font-semibold text-white"
              >
                {updating ? '…' : '✓'}
              </button>
              <button
                type="button"
                onClick={handleCancelEdit}
                disabled={updating}
                className="rounded-md bg-alert-red px-2.5 py-1 text-xs font-semibold text-white"
              >
                ✕
              </button>
            </div>
          );
        }
        return (
          <div className="flex items-center gap-2">
            <Badge tone="ember">{row.category || 'Uncategorized'}</Badge>
            <button
              type="button"
              onClick={() => handleEditCategory(row._idx, row.category || '')}
              className="rounded-md border border-line px-2 py-0.5 text-[11px] font-semibold text-ink-dim hover:text-ink"
            >
              Edit
            </button>
          </div>
        );
      },
    },
    {
      key: 'quantity',
      header: 'Quantity',
      className: 'text-center',
      render: (row) => <Badge tone="gold">{row.quantity}</Badge>,
    },
    {
      key: 'price',
      header: 'Price',
      className: 'text-right',
      render: (row) => <span className="font-mono text-sm text-ink-dim">${row.price?.toFixed(2)}</span>,
    },
    {
      key: 'total',
      header: 'Total',
      className: 'text-right',
      render: (row) => (
        <span className="font-mono text-sm font-semibold text-ink">
          ${((row.price || 0) * (row.quantity || 1)).toFixed(2)}
        </span>
      ),
    },
    {
      key: 'source',
      header: 'Source',
      render: (row) => <Badge tone="neutral">{row.source}</Badge>,
    },
  ];

  if (loading) {
    return (
      <div className="mx-auto max-w-[900px] px-4 py-10 md:px-6">
        <Spinner label="Loading history…" />
      </div>
    );
  }
  if (!history.length) {
    return (
      <div className="mx-auto max-w-[900px] px-4 py-10 md:px-6">
        <EmptyState title="No history found" description={`No purchase history found for ${name}.`} />
      </div>
    );
  }

  return (
    <div className="mx-auto max-w-[900px] px-4 py-6 md:px-6">
      <Link to="/items" className="mb-4 inline-block text-sm font-medium text-signal">
        ← Back to items
      </Link>
      <PageHeader eyebrow="Ledger / Items" title={decodeURIComponent(name || '')} />

      <div className="mb-6 grid grid-cols-2 gap-3 md:grid-cols-4">
        <StatCard label="This month" value={`$${monthSpending.toFixed(2)}`} detail={`${monthPurchasesCount} purchase${monthPurchasesCount !== 1 ? 's' : ''}`} tone="amber" />
        <StatCard label="This year" value={`$${yearSpending.toFixed(2)}`} detail={`${yearPurchasesCount} purchase${yearPurchasesCount !== 1 ? 's' : ''}`} tone="amber" />
        <StatCard label="All time" value={`$${allTimeSpending.toFixed(2)}`} detail={`${history.length} purchase${history.length !== 1 ? 's' : ''}`} tone="amber" />
        <StatCard label="Avg price" value={`$${avgPrice.toFixed(2)}`} tone="amber" />
      </div>

      <div className="mb-5">
        <ChartCard title="Purchase timeline (price trend)">
          <Line data={priceChartData} options={priceChartOptions} />
        </ChartCard>
      </div>

      <div className="mb-5 grid grid-cols-1 gap-5 md:grid-cols-2">
        <ChartCard title="Spending per month">
          <Bar data={spendingMonthChartData} options={spendingChartOptions} />
        </ChartCard>
        <ChartCard title="Spending per year">
          <Bar data={spendingYearChartData} options={spendingChartOptions} />
        </ChartCard>
      </div>

      <div className="mb-5 grid grid-cols-1 gap-5 md:grid-cols-2">
        <ChartCard title="Quantity per month">
          <Bar data={qtyChartData} options={qtyChartOptions} />
        </ChartCard>
        <ChartCard title="Quantity per year">
          <Bar data={qtyYearChartData} options={qtyChartOptions} />
        </ChartCard>
      </div>

      {/* Purchase History Table */}
      <Card>
        <div className="mb-4 flex flex-wrap items-center justify-between gap-3">
          <h3 className="font-mono text-[13px] uppercase tracking-wider text-muted">Purchase history</h3>
          <div className="flex items-center gap-2 text-xs text-muted">
            <label htmlFor="sort-field">Sort by</label>
            <select
              id="sort-field"
              value={sortField}
              onChange={(e) => { setSortField(e.target.value as SortField); setSortDirection('desc'); }}
              className="rounded-md border border-line bg-surface px-2 py-1 text-xs text-ink"
            >
              <option value="date">Date</option>
              <option value="quantity">Quantity</option>
              <option value="price">Price</option>
              <option value="total">Total</option>
              <option value="source">Source</option>
            </select>
            <button
              type="button"
              onClick={() => setSortDirection((d) => (d === 'asc' ? 'desc' : 'asc'))}
              className="rounded-md border border-line px-2 py-1 text-xs font-semibold text-ink-dim hover:text-ink"
            >
              {sortDirection === 'asc' ? '↑ Asc' : '↓ Desc'}
            </button>
          </div>
        </div>
        <ResponsiveTable columns={columns} rows={rows} rowKey={(row) => row._idx} />
      </Card>
    </div>
  );
};

export default ItemDetail;
