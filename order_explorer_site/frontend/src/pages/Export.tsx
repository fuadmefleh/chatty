import React, { useState } from 'react';
import axios from 'axios';
import PageHeader from '../components/ui/PageHeader';
import Card from '../components/ui/Card';

type ExportRow = Record<string, unknown>;

const primaryBtn = (disabled: boolean): React.CSSProperties => ({
  background: 'var(--stamp-gold)',
  color: 'var(--ink-900)',
  padding: '13px',
  fontSize: '14px',
  fontWeight: 700,
  opacity: disabled ? 0.55 : 1,
  display: 'flex',
  alignItems: 'center',
  justifyContent: 'center',
});

const rangeBtn = (active: boolean): React.CSSProperties => ({
  background: active ? 'var(--stamp-gold)' : 'transparent',
  color: active ? 'var(--ink-900)' : 'var(--paper)',
  border: `1px solid ${active ? 'var(--stamp-gold)' : 'var(--ink-600)'}`,
  padding: '11px',
  fontSize: '13px',
  fontWeight: 600,
});

const TipRow: React.FC<{ color: string; children: React.ReactNode }> = ({ color, children }) => (
  <div style={{ padding: '13px 16px', background: 'var(--ink-900)', borderRadius: '8px', borderLeft: `3px solid ${color}` }}>
    <p style={{ margin: 0, fontSize: '13.5px', color: 'var(--paper-dim)', lineHeight: 1.5 }}>{children}</p>
  </div>
);

const Export: React.FC = () => {
  const [loading, setLoading] = useState(false);
  const [dateRange, setDateRange] = useState<'all' | 'year' | 'month' | 'custom'>('all');
  const [startDate, setStartDate] = useState('');
  const [endDate, setEndDate] = useState('');

  const downloadCSV = async (data: ExportRow[], filename: string) => {
    if (data.length === 0) {
      alert('No data to export');
      return;
    }

    const headers = Object.keys(data[0]);
    const csvContent = [
      headers.join(','),
      ...data.map(row =>
        headers.map(header => {
          const value = row[header];
          if (value === null || value === undefined) return '';
          const stringValue = String(value);
          if (stringValue.includes(',') || stringValue.includes('"') || stringValue.includes('\n')) {
            return `"${stringValue.replace(/"/g, '""')}"`;
          }
          return stringValue;
        }).join(',')
      )
    ].join('\n');

    const blob = new Blob([csvContent], { type: 'text/csv;charset=utf-8;' });
    const link = document.createElement('a');
    const url = URL.createObjectURL(blob);
    link.setAttribute('href', url);
    link.setAttribute('download', filename);
    link.style.visibility = 'hidden';
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
  };

  const filterByDate = (items: ExportRow[]) => {
    if (dateRange === 'all') return items;

    const now = new Date();
    let start: Date;
    let end = now;

    if (dateRange === 'year') {
      start = new Date(now.getFullYear(), 0, 1);
    } else if (dateRange === 'month') {
      start = new Date(now.getFullYear(), now.getMonth(), 1);
    } else if (dateRange === 'custom') {
      if (!startDate || !endDate) return items;
      start = new Date(startDate);
      end = new Date(endDate);
    } else {
      return items;
    }

    return items.filter(item => {
      if (!item.date) return false;
      const itemDate = new Date(item.date as string);
      return itemDate >= start && itemDate <= end;
    });
  };

  const exportOrders = async () => {
    setLoading(true);
    try {
      const response = await axios.get('http://localhost:8015/orders');
      const filtered = filterByDate(response.data);
      await downloadCSV(filtered, `orders_${dateRange}_${new Date().toISOString().split('T')[0]}.csv`);
    } catch (err) {
      console.error('Export failed', err);
      alert('Export failed');
    }
    setLoading(false);
  };

  const exportItems = async () => {
    setLoading(true);
    try {
      const response = await axios.get('http://localhost:8015/items');
      const filtered = filterByDate(response.data);
      await downloadCSV(filtered, `items_${dateRange}_${new Date().toISOString().split('T')[0]}.csv`);
    } catch (err) {
      console.error('Export failed', err);
      alert('Export failed');
    }
    setLoading(false);
  };

  const exportCategories = async () => {
    setLoading(true);
    try {
      const response = await axios.get('http://localhost:8015/categories');
      await downloadCSV(response.data.categories, `categories_${new Date().toISOString().split('T')[0]}.csv`);
    } catch (err) {
      console.error('Export failed', err);
      alert('Export failed');
    }
    setLoading(false);
  };

  const exportMonthly = async () => {
    setLoading(true);
    try {
      const response = await axios.get('http://localhost:8015/months');
      await downloadCSV(response.data, `monthly_summary_${new Date().toISOString().split('T')[0]}.csv`);
    } catch (err) {
      console.error('Export failed', err);
      alert('Export failed');
    }
    setLoading(false);
  };

  const generatePDFReport = () => {
    window.print();
  };

  return (
    <div style={{ padding: '24px 24px 48px' }}>
      <PageHeader eyebrow="Ledger / Export" title="Export & reports" />

      {/* Date Range Selection */}
      <Card style={{ marginBottom: '24px' }}>
        <h2 style={{ fontSize: 15, marginBottom: 16, color: 'var(--paper)' }}>Date range</h2>
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(180px, 1fr))', gap: '12px' }}>
          <button onClick={() => setDateRange('all')} style={rangeBtn(dateRange === 'all')}>All time</button>
          <button onClick={() => setDateRange('year')} style={rangeBtn(dateRange === 'year')}>This year</button>
          <button onClick={() => setDateRange('month')} style={rangeBtn(dateRange === 'month')}>This month</button>
          <button onClick={() => setDateRange('custom')} style={rangeBtn(dateRange === 'custom')}>Custom range</button>
        </div>

        {dateRange === 'custom' && (
          <div style={{ marginTop: '16px', display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '15px' }}>
            <div>
              <label style={{ display: 'block', marginBottom: '6px', fontSize: '12px', fontWeight: 600, color: 'var(--muted)', fontFamily: 'var(--font-mono)', textTransform: 'uppercase' }}>Start date</label>
              <input type="date" value={startDate} onChange={(e) => setStartDate(e.target.value)} style={{ width: '100%', padding: '10px', borderRadius: '6px', fontSize: '14px' }} />
            </div>
            <div>
              <label style={{ display: 'block', marginBottom: '6px', fontSize: '12px', fontWeight: 600, color: 'var(--muted)', fontFamily: 'var(--font-mono)', textTransform: 'uppercase' }}>End date</label>
              <input type="date" value={endDate} onChange={(e) => setEndDate(e.target.value)} style={{ width: '100%', padding: '10px', borderRadius: '6px', fontSize: '14px' }} />
            </div>
          </div>
        )}
      </Card>

      {/* CSV Exports */}
      <Card style={{ marginBottom: '24px' }}>
        <h2 style={{ fontSize: 15, marginBottom: 8, color: 'var(--paper)' }}>Export to CSV</h2>
        <p style={{ margin: '0 0 18px 0', fontSize: '13px', color: 'var(--muted)' }}>
          Download your data in CSV format for use in Excel, Google Sheets, or other applications.
        </p>
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))', gap: '14px' }}>
          <button onClick={exportOrders} disabled={loading} style={primaryBtn(loading)}>Export orders</button>
          <button onClick={exportItems} disabled={loading} style={primaryBtn(loading)}>Export items</button>
          <button onClick={exportCategories} disabled={loading} style={primaryBtn(loading)}>Export categories</button>
          <button onClick={exportMonthly} disabled={loading} style={primaryBtn(loading)}>Export monthly summary</button>
        </div>
      </Card>

      {/* PDF Reports */}
      <Card style={{ marginBottom: '24px' }}>
        <h2 style={{ fontSize: 15, marginBottom: 8, color: 'var(--paper)' }}>Generate reports</h2>
        <p style={{ margin: '0 0 18px 0', fontSize: '13px', color: 'var(--muted)' }}>
          Generate printable PDF reports of your spending data.
        </p>
        <button onClick={generatePDFReport} style={{ background: 'var(--stamp-ember)', color: 'var(--ink-900)', padding: '13px 26px', fontSize: '14px', fontWeight: 700 }}>
          Generate PDF report
        </button>
        <p style={{ margin: '14px 0 0 0', fontSize: '12px', color: 'var(--muted)', fontStyle: 'italic' }}>
          This will open your browser's print dialog where you can save as PDF.
        </p>
      </Card>

      {/* Export Tips */}
      <Card style={{ marginBottom: '24px' }}>
        <h2 style={{ fontSize: 15, marginBottom: 16, color: 'var(--paper)' }}>Export tips</h2>
        <div style={{ display: 'flex', flexDirection: 'column', gap: '10px' }}>
          <TipRow color="var(--stamp-gold)"><strong>Tax reporting:</strong> Export your yearly data for tax preparation and expense tracking.</TipRow>
          <TipRow color="var(--stamp-teal)"><strong>Budget analysis:</strong> Open CSV files in Excel or Google Sheets for advanced analysis.</TipRow>
          <TipRow color="var(--stamp-ember)"><strong>Backup:</strong> Regular exports serve as a backup of your order and spending data.</TipRow>
          <TipRow color="#e8c478"><strong>Custom analysis:</strong> Use custom date ranges to analyze specific time periods.</TipRow>
        </div>
      </Card>

      {/* Quick Export Templates */}
      <Card>
        <h2 style={{ fontSize: 15, marginBottom: 16, color: 'var(--paper)' }}>Quick export templates</h2>
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(230px, 1fr))', gap: '14px' }}>
          <div style={{ padding: '16px', border: '1px solid var(--ink-700)', borderRadius: '8px' }}>
            <h3 style={{ margin: '0 0 8px 0', fontSize: '14px', fontWeight: 700, color: 'var(--paper)' }}>Tax year report</h3>
            <p style={{ margin: '0 0 14px 0', fontSize: '12.5px', color: 'var(--muted)' }}>Export all orders and items for the current tax year</p>
            <button
              onClick={() => {
                setDateRange('year');
                setTimeout(() => {
                  exportOrders();
                  setTimeout(() => exportItems(), 1000);
                }, 100);
              }}
              disabled={loading}
              style={{ ...primaryBtn(loading), width: '100%', padding: '9px 16px', fontSize: '13px' }}
            >
              Export tax report
            </button>
          </div>

          <div style={{ padding: '16px', border: '1px solid var(--ink-700)', borderRadius: '8px' }}>
            <h3 style={{ margin: '0 0 8px 0', fontSize: '14px', fontWeight: 700, color: 'var(--paper)' }}>Monthly summary</h3>
            <p style={{ margin: '0 0 14px 0', fontSize: '12.5px', color: 'var(--muted)' }}>Export current month's spending summary</p>
            <button
              onClick={() => {
                setDateRange('month');
                setTimeout(exportMonthly, 100);
              }}
              disabled={loading}
              style={{ background: 'var(--stamp-teal)', color: 'var(--ink-900)', width: '100%', padding: '9px 16px', fontSize: '13px', fontWeight: 700, opacity: loading ? 0.55 : 1 }}
            >
              Export this month
            </button>
          </div>

          <div style={{ padding: '16px', border: '1px solid var(--ink-700)', borderRadius: '8px' }}>
            <h3 style={{ margin: '0 0 8px 0', fontSize: '14px', fontWeight: 700, color: 'var(--paper)' }}>Complete backup</h3>
            <p style={{ margin: '0 0 14px 0', fontSize: '12.5px', color: 'var(--muted)' }}>Export all data — orders, items, and categories</p>
            <button
              onClick={() => {
                setDateRange('all');
                setTimeout(() => {
                  exportOrders();
                  setTimeout(() => {
                    exportItems();
                    setTimeout(exportCategories, 1000);
                  }, 1000);
                }, 100);
              }}
              disabled={loading}
              style={{ background: 'var(--stamp-ember)', color: 'var(--ink-900)', width: '100%', padding: '9px 16px', fontSize: '13px', fontWeight: 700, opacity: loading ? 0.55 : 1 }}
            >
              Full backup
            </button>
          </div>
        </div>
      </Card>

      {loading && (
        <div style={{
          position: 'fixed',
          top: '50%',
          left: '50%',
          transform: 'translate(-50%, -50%)',
          background: 'var(--ink-800)',
          border: '1px solid var(--ink-700)',
          padding: '20px 40px',
          borderRadius: '10px',
          zIndex: 1000
        }}>
          <p style={{ margin: 0, fontSize: '14px', fontWeight: 700, color: 'var(--paper)' }}>Exporting data…</p>
        </div>
      )}
    </div>
  );
};

export default Export;
