import React, { useState } from 'react';
import { api } from '../api';
import PageHeader from '../components/ui/PageHeader';
import Card from '../components/ui/Card';
import Spinner from '../components/ui/Spinner';
import FormField from '../components/ui/form/FormField';
import Input from '../components/ui/form/Input';
import { useToast } from '../hooks/useToast';

type ExportRow = Record<string, unknown>;

const rangeBtnClass = (active: boolean) =>
  `h-10 rounded-lg border px-3 text-sm font-semibold transition-colors ${
    active ? 'border-alert-amber bg-alert-amber text-white' : 'border-line bg-transparent text-ink'
  }`;

const primaryBtnClass = 'h-10 rounded-lg bg-alert-amber px-4 text-sm font-bold text-white disabled:opacity-55';
const amberBtnClass = 'h-9 w-full rounded-lg bg-alert-amber px-4 text-[13px] font-bold text-white disabled:opacity-55';
const tealBtnClass = 'h-9 w-full rounded-lg bg-signal px-4 text-[13px] font-bold text-white disabled:opacity-55';
const redBtnClass = 'h-9 w-full rounded-lg bg-alert-red px-4 text-[13px] font-bold text-white disabled:opacity-55';

const TipRow: React.FC<{ colorClass: string; children: React.ReactNode }> = ({ colorClass, children }) => (
  <div className={`rounded-lg bg-surface-dim px-4 py-3.5 border-l-[3px] ${colorClass}`}>
    <p className="text-sm leading-relaxed text-ink-dim">{children}</p>
  </div>
);

const Export: React.FC = () => {
  const { showToast } = useToast();
  const [loading, setLoading] = useState(false);
  const [dateRange, setDateRange] = useState<'all' | 'year' | 'month' | 'custom'>('all');
  const [startDate, setStartDate] = useState('');
  const [endDate, setEndDate] = useState('');

  const downloadCSV = async (data: ExportRow[], filename: string) => {
    if (data.length === 0) {
      showToast('No data to export', 'amber');
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
    showToast(`Downloaded ${filename}`, 'signal');
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
      const response = await api.get('/orders');
      const filtered = filterByDate(response.data);
      await downloadCSV(filtered, `orders_${dateRange}_${new Date().toISOString().split('T')[0]}.csv`);
    } catch (err) {
      console.error('Export failed', err);
      showToast('Export failed', 'red');
    }
    setLoading(false);
  };

  const exportItems = async () => {
    setLoading(true);
    try {
      const response = await api.get('/items');
      const filtered = filterByDate(response.data);
      await downloadCSV(filtered, `items_${dateRange}_${new Date().toISOString().split('T')[0]}.csv`);
    } catch (err) {
      console.error('Export failed', err);
      showToast('Export failed', 'red');
    }
    setLoading(false);
  };

  const exportCategories = async () => {
    setLoading(true);
    try {
      const response = await api.get('/categories');
      await downloadCSV(response.data.categories, `categories_${new Date().toISOString().split('T')[0]}.csv`);
    } catch (err) {
      console.error('Export failed', err);
      showToast('Export failed', 'red');
    }
    setLoading(false);
  };

  const exportMonthly = async () => {
    setLoading(true);
    try {
      const response = await api.get('/months');
      await downloadCSV(response.data, `monthly_summary_${new Date().toISOString().split('T')[0]}.csv`);
    } catch (err) {
      console.error('Export failed', err);
      showToast('Export failed', 'red');
    }
    setLoading(false);
  };

  const generatePDFReport = () => {
    window.print();
  };

  return (
    <div className="mx-auto max-w-[1000px] px-4 py-6 md:px-6">
      <PageHeader eyebrow="Ledger / Export" title="Export & reports" />

      {/* Date Range Selection */}
      <Card className="mb-6">
        <h2 className="mb-4 text-base font-semibold text-ink">Date range</h2>
        <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
          <button onClick={() => setDateRange('all')} className={rangeBtnClass(dateRange === 'all')}>All time</button>
          <button onClick={() => setDateRange('year')} className={rangeBtnClass(dateRange === 'year')}>This year</button>
          <button onClick={() => setDateRange('month')} className={rangeBtnClass(dateRange === 'month')}>This month</button>
          <button onClick={() => setDateRange('custom')} className={rangeBtnClass(dateRange === 'custom')}>Custom range</button>
        </div>

        {dateRange === 'custom' && (
          <div className="mt-4 grid grid-cols-1 gap-4 sm:grid-cols-2">
            <FormField label="Start date" htmlFor="export-start">
              <Input id="export-start" type="date" value={startDate} onChange={(e) => setStartDate(e.target.value)} />
            </FormField>
            <FormField label="End date" htmlFor="export-end">
              <Input id="export-end" type="date" value={endDate} onChange={(e) => setEndDate(e.target.value)} />
            </FormField>
          </div>
        )}
      </Card>

      {/* CSV Exports */}
      <Card className="mb-6">
        <h2 className="mb-1.5 text-base font-semibold text-ink">Export to CSV</h2>
        <p className="mb-4.5 text-sm text-muted">
          Download your data in CSV format for use in Excel, Google Sheets, or other applications.
        </p>
        <div className="grid grid-cols-1 gap-3.5 sm:grid-cols-2">
          <button onClick={exportOrders} disabled={loading} className={primaryBtnClass}>Export orders</button>
          <button onClick={exportItems} disabled={loading} className={primaryBtnClass}>Export items</button>
          <button onClick={exportCategories} disabled={loading} className={primaryBtnClass}>Export categories</button>
          <button onClick={exportMonthly} disabled={loading} className={primaryBtnClass}>Export monthly summary</button>
        </div>
      </Card>

      {/* PDF Reports */}
      <Card className="mb-6">
        <h2 className="mb-1.5 text-base font-semibold text-ink">Generate reports</h2>
        <p className="mb-4.5 text-sm text-muted">
          Generate printable PDF reports of your spending data.
        </p>
        <button onClick={generatePDFReport} className="h-10 rounded-lg bg-alert-red px-6 text-sm font-bold text-white">
          Generate PDF report
        </button>
        <p className="mt-3.5 text-xs italic text-muted">
          This will open your browser's print dialog where you can save as PDF.
        </p>
      </Card>

      {/* Export Tips */}
      <Card className="mb-6">
        <h2 className="mb-4 text-base font-semibold text-ink">Export tips</h2>
        <div className="flex flex-col gap-2.5">
          <TipRow colorClass="border-alert-amber"><strong>Tax reporting:</strong> Export your yearly data for tax preparation and expense tracking.</TipRow>
          <TipRow colorClass="border-signal"><strong>Budget analysis:</strong> Open CSV files in Excel or Google Sheets for advanced analysis.</TipRow>
          <TipRow colorClass="border-alert-red"><strong>Backup:</strong> Regular exports serve as a backup of your order and spending data.</TipRow>
          <TipRow colorClass="border-alert-green"><strong>Custom analysis:</strong> Use custom date ranges to analyze specific time periods.</TipRow>
        </div>
      </Card>

      {/* Quick Export Templates */}
      <Card>
        <h2 className="mb-4 text-base font-semibold text-ink">Quick export templates</h2>
        <div className="grid grid-cols-1 gap-3.5 sm:grid-cols-3">
          <div className="rounded-lg border border-line p-4">
            <h3 className="mb-2 text-sm font-bold text-ink">Tax year report</h3>
            <p className="mb-3.5 text-xs text-muted">Export all orders and items for the current tax year</p>
            <button
              onClick={() => {
                setDateRange('year');
                setTimeout(() => {
                  exportOrders();
                  setTimeout(() => exportItems(), 1000);
                }, 100);
              }}
              disabled={loading}
              className={amberBtnClass}
            >
              Export tax report
            </button>
          </div>

          <div className="rounded-lg border border-line p-4">
            <h3 className="mb-2 text-sm font-bold text-ink">Monthly summary</h3>
            <p className="mb-3.5 text-xs text-muted">Export current month's spending summary</p>
            <button
              onClick={() => {
                setDateRange('month');
                setTimeout(exportMonthly, 100);
              }}
              disabled={loading}
              className={tealBtnClass}
            >
              Export this month
            </button>
          </div>

          <div className="rounded-lg border border-line p-4">
            <h3 className="mb-2 text-sm font-bold text-ink">Complete backup</h3>
            <p className="mb-3.5 text-xs text-muted">Export all data — orders, items, and categories</p>
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
              className={redBtnClass}
            >
              Full backup
            </button>
          </div>
        </div>
      </Card>

      {loading && (
        <div className="fixed left-1/2 top-1/2 z-[1000] -translate-x-1/2 -translate-y-1/2 rounded-xl border border-line bg-surface px-8 py-5 shadow-xl">
          <Spinner label="Exporting data…" />
        </div>
      )}
    </div>
  );
};

export default Export;
