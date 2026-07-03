import React, { useEffect, useState, useMemo, useCallback } from 'react';
import { useParams, Link } from 'react-router-dom';
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
import { Line, Bar } from 'react-chartjs-2';
import PageHeader from '../components/ui/PageHeader';
import Card from '../components/ui/Card';

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

const AXIS_COLOR = '#8b8f92';
const GRID_COLOR = '#262c33';

const StatCard: React.FC<{ label: string; value: string; sub?: string }> = ({ label, value, sub }) => (
  <Card>
    <div style={{ fontSize: 11, fontFamily: 'var(--font-mono)', letterSpacing: '0.08em', textTransform: 'uppercase', color: 'var(--muted)', marginBottom: 10 }}>{label}</div>
    <div style={{ fontSize: 26, fontWeight: 700, fontFamily: 'var(--font-mono)', color: 'var(--stamp-gold)' }}>{value}</div>
    {sub && <div style={{ fontSize: 12, color: 'var(--muted)', marginTop: 4 }}>{sub}</div>}
  </Card>
);

const ChartCard: React.FC<React.PropsWithChildren<{ title: string }>> = ({ title, children }) => (
  <Card>
    <h3 style={{ fontSize: 13, fontFamily: 'var(--font-mono)', letterSpacing: '0.06em', textTransform: 'uppercase', marginBottom: 16, color: 'var(--muted)' }}>{title}</h3>
    <div style={{ height: '300px' }}>{children}</div>
  </Card>
);

const thStyle = (align: 'left' | 'right' | 'center'): React.CSSProperties => ({
  padding: '12px 14px',
  textAlign: align,
  fontWeight: 600,
  fontSize: 11,
  fontFamily: 'var(--font-mono)',
  textTransform: 'uppercase',
  letterSpacing: '0.05em',
  color: 'var(--muted)',
  cursor: 'pointer',
  userSelect: 'none',
});

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

  const handleSort = useCallback((field: SortField) => {
    setSortField(prevField => {
      if (prevField === field) {
        setSortDirection(prev => prev === 'asc' ? 'desc' : 'asc');
        return field;
      } else {
        setSortDirection('desc');
        return field;
      }
    });
  }, []);

  const getSortIcon = useCallback((field: SortField) => {
    if (sortField !== field) return ' ⇅';
    return sortDirection === 'asc' ? ' ↑' : ' ↓';
  }, [sortField, sortDirection]);

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
    } catch (error: any) {
      console.error('Failed to update category:', error);
      alert(`Failed to update category: ${error.response?.data?.detail || error.message}`);
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
      legend: { display: true, position: 'top' as const, labels: { color: AXIS_COLOR } },
      tooltip: {
        callbacks: {
          label: function (context: any) {
            return `Price: $${context.parsed.y?.toFixed(2)}`;
          }
        }
      }
    },
    scales: {
      x: { ticks: { color: AXIS_COLOR }, grid: { color: GRID_COLOR } },
      y: {
        beginAtZero: true,
        ticks: { color: AXIS_COLOR, callback: function (value: any) { return '$' + value; } },
        grid: { color: GRID_COLOR },
      }
    }
  };

  const qtyChartOptions = {
    responsive: true,
    maintainAspectRatio: false,
    plugins: {
      legend: { display: true, position: 'top' as const, labels: { color: AXIS_COLOR } },
    },
    scales: {
      x: { ticks: { color: AXIS_COLOR }, grid: { color: GRID_COLOR } },
      y: { beginAtZero: true, ticks: { color: AXIS_COLOR }, grid: { color: GRID_COLOR } },
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
      legend: { display: true, position: 'top' as const, labels: { color: AXIS_COLOR } },
      tooltip: {
        callbacks: {
          label: function (context: any) {
            return `Spending: $${context.parsed.y?.toFixed(2)}`;
          }
        }
      }
    },
    scales: {
      x: { ticks: { color: AXIS_COLOR }, grid: { color: GRID_COLOR } },
      y: {
        beginAtZero: true,
        ticks: { color: AXIS_COLOR, callback: function (value: any) { return '$' + value; } },
        grid: { color: GRID_COLOR },
      }
    }
  };

  if (loading) return <div style={{ padding: 24, color: 'var(--muted)' }}>Loading history…</div>;
  if (!history.length) return <div style={{ padding: 24, color: 'var(--muted)' }}>No history found for {name}</div>;

  return (
    <div style={{ padding: '24px 24px 48px' }}>
      <Link to="/items" style={{ color: 'var(--stamp-teal)', fontSize: '13px', fontWeight: 500, marginBottom: '16px', display: 'inline-block' }}>
        ← Back to items
      </Link>
      <PageHeader eyebrow="Ledger / Items" title={decodeURIComponent(name || '')} />

      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(190px, 1fr))', gap: '16px', marginBottom: '24px' }}>
        <StatCard label="This month" value={`$${monthSpending.toFixed(2)}`} sub={`${monthPurchasesCount} purchase${monthPurchasesCount !== 1 ? 's' : ''}`} />
        <StatCard label="This year" value={`$${yearSpending.toFixed(2)}`} sub={`${yearPurchasesCount} purchase${yearPurchasesCount !== 1 ? 's' : ''}`} />
        <StatCard label="All time" value={`$${allTimeSpending.toFixed(2)}`} sub={`${history.length} purchase${history.length !== 1 ? 's' : ''}`} />
        <StatCard label="Avg price" value={`$${avgPrice.toFixed(2)}`} />
      </div>

      <div style={{ marginBottom: 20 }}>
        <ChartCard title="Purchase timeline (price trend)">
          <Line data={priceChartData} options={priceChartOptions} />
        </ChartCard>
      </div>

      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(380px, 1fr))', gap: '20px', marginBottom: '20px' }}>
        <ChartCard title="Spending per month">
          <Bar data={spendingMonthChartData} options={spendingChartOptions} />
        </ChartCard>
        <ChartCard title="Spending per year">
          <Bar data={spendingYearChartData} options={spendingChartOptions} />
        </ChartCard>
      </div>

      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(380px, 1fr))', gap: '20px', marginBottom: '20px' }}>
        <ChartCard title="Quantity per month">
          <Bar data={qtyChartData} options={qtyChartOptions} />
        </ChartCard>
        <ChartCard title="Quantity per year">
          <Bar data={qtyYearChartData} options={qtyChartOptions} />
        </ChartCard>
      </div>

      {/* Purchase History Table */}
      <Card>
        <h3 style={{ fontSize: 13, fontFamily: 'var(--font-mono)', letterSpacing: '0.06em', textTransform: 'uppercase', marginBottom: 16, color: 'var(--muted)' }}>Purchase history</h3>
        <div style={{ overflowX: 'auto', border: '1px solid var(--ink-700)', borderRadius: '10px' }}>
          <table style={{ width: '100%', borderCollapse: 'collapse' }}>
            <thead>
              <tr style={{ background: 'var(--ink-750)' }}>
                <th onClick={() => handleSort('date')} style={thStyle('left')}>Date{getSortIcon('date')}</th>
                <th style={thStyle('left')}>Category</th>
                <th onClick={() => handleSort('quantity')} style={thStyle('center')}>Quantity{getSortIcon('quantity')}</th>
                <th onClick={() => handleSort('price')} style={thStyle('right')}>Price{getSortIcon('price')}</th>
                <th onClick={() => handleSort('total')} style={thStyle('right')}>Total{getSortIcon('total')}</th>
                <th onClick={() => handleSort('source')} style={thStyle('left')}>Source{getSortIcon('source')}</th>
              </tr>
            </thead>
            <tbody>
              {sortedHistory.map((h, i) => {
                const total = (h.price || 0) * (h.quantity || 1);
                const isEditing = editingRow === i;
                return (
                  <tr
                    key={i}
                    style={{
                      backgroundColor: i % 2 === 0 ? 'var(--ink-800)' : 'var(--ink-900)',
                      transition: 'background-color 0.15s'
                    }}
                    onMouseEnter={(e) => e.currentTarget.style.backgroundColor = 'var(--ink-750)'}
                    onMouseLeave={(e) => e.currentTarget.style.backgroundColor = i % 2 === 0 ? 'var(--ink-800)' : 'var(--ink-900)'}
                  >
                    <td style={{ padding: '13px 14px', borderTop: '1px solid var(--ink-700)', fontFamily: 'var(--font-mono)', fontSize: 13, color: 'var(--paper)' }}>{h.date}</td>
                    <td style={{ padding: '13px 14px', borderTop: '1px solid var(--ink-700)' }}>
                      {isEditing ? (
                        <div style={{ display: 'flex', gap: '8px', alignItems: 'center' }}>
                          <div style={{ flex: 1, position: 'relative' }}>
                            <input
                              type="text"
                              list={`categories-${i}`}
                              value={tempCategory}
                              onChange={(e) => setTempCategory(e.target.value)}
                              disabled={updating}
                              placeholder="Type or select category"
                              style={{ padding: '6px 8px', borderRadius: '4px', fontSize: '13px', width: '100%' }}
                            />
                            <datalist id={`categories-${i}`}>
                              {availableCategories.map(cat => (
                                <option key={cat} value={cat} />
                              ))}
                            </datalist>
                          </div>
                          <button
                            onClick={() => { handleSaveCategory(h); }}
                            disabled={updating || !tempCategory.trim()}
                            style={{ background: 'var(--success)', color: 'var(--ink-900)', borderRadius: '4px', padding: '6px 12px', fontSize: '12px', fontWeight: 600 }}
                          >
                            {updating ? '…' : '✓'}
                          </button>
                          <button
                            onClick={handleCancelEdit}
                            disabled={updating}
                            style={{ background: 'var(--danger)', color: 'var(--ink-900)', borderRadius: '4px', padding: '6px 12px', fontSize: '12px', fontWeight: 600 }}
                          >
                            ✕
                          </button>
                        </div>
                      ) : (
                        <div style={{ display: 'flex', gap: '8px', alignItems: 'center' }}>
                          <span style={{ background: 'rgba(216, 96, 63, 0.15)', color: 'var(--stamp-ember)', padding: '3px 10px', borderRadius: '12px', fontSize: '12px', fontWeight: 600 }}>
                            {h.category || 'Uncategorized'}
                          </span>
                          <button
                            onClick={() => handleEditCategory(i, h.category || '')}
                            style={{ background: 'var(--ink-700)', color: 'var(--paper)', borderRadius: '4px', padding: '4px 8px', fontSize: '11px', fontWeight: 600 }}
                          >
                            Edit
                          </button>
                        </div>
                      )}
                    </td>
                    <td style={{ padding: '13px 14px', borderTop: '1px solid var(--ink-700)', textAlign: 'center' }}>
                      <span style={{ background: 'rgba(200, 155, 60, 0.15)', color: 'var(--stamp-gold)', padding: '3px 10px', borderRadius: '12px', fontSize: '12px', fontWeight: 600, fontFamily: 'var(--font-mono)' }}>
                        {h.quantity}
                      </span>
                    </td>
                    <td style={{ padding: '13px 14px', borderTop: '1px solid var(--ink-700)', textAlign: 'right', fontFamily: 'var(--font-mono)', fontSize: 13, color: 'var(--paper-dim)' }}>
                      ${h.price?.toFixed(2)}
                    </td>
                    <td style={{ padding: '13px 14px', borderTop: '1px solid var(--ink-700)', textAlign: 'right', fontWeight: 600, fontFamily: 'var(--font-mono)', color: 'var(--paper)' }}>
                      ${total.toFixed(2)}
                    </td>
                    <td style={{ padding: '13px 14px', borderTop: '1px solid var(--ink-700)' }}>
                      <span style={{ background: 'var(--ink-700)', color: 'var(--muted)', padding: '3px 10px', borderRadius: '12px', fontSize: '12px', fontWeight: 600 }}>
                        {h.source}
                      </span>
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      </Card>
    </div>
  );
};

export default ItemDetail;
