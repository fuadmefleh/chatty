import React, { useEffect, useState } from 'react';
import { api } from '../api';
import { ResponsiveContainer, PieChart, Pie, Cell, Tooltip } from 'recharts';
import type { PieLabelRenderProps } from 'recharts';
import PageHeader from '../components/ui/PageHeader';
import Card from '../components/ui/Card';
import StatCard from '../components/ui/StatCard';
import Spinner from '../components/ui/Spinner';
import FormField from '../components/ui/form/FormField';
import Input from '../components/ui/form/Input';
import { useToast } from '../hooks/useToast';

interface BudgetSummary {
  current_month: string;
  month_spending: number;
  daily_average: number;
  projected_month_end: number;
  avg_monthly_historical: number;
  day_of_month: number;
  category_breakdown: Array<{
    category: string;
    total: number;
    percentage: number;
  }>;
  monthly_limit?: number;
  remaining?: number;
  percentage_used?: number;
  on_track?: boolean;
}

const COLORS = ['#c89b3c', '#4fa8a0', '#d8603f', '#e8c478', '#6ea87a', '#8f7fd6', '#4a90c4', '#b6588c'];

const pieLabel = (props: PieLabelRenderProps) => {
  const { category, percentage } = props as unknown as { category: string; percentage: number };
  return `${category}: ${percentage.toFixed(0)}%`;
};

const sectionTitle = 'mb-4 font-mono text-[13px] uppercase tracking-wider text-muted';

const Budget: React.FC = () => {
  const { showToast } = useToast();
  const [data, setData] = useState<BudgetSummary | null>(null);
  const [loading, setLoading] = useState(true);
  const [budgetLimit, setBudgetLimit] = useState<string>(
    () => localStorage.getItem('monthlyBudgetLimit') ?? ''
  );
  const [savedLimit, setSavedLimit] = useState<number | null>(() => {
    const saved = localStorage.getItem('monthlyBudgetLimit');
    return saved ? parseFloat(saved) : null;
  });

  const loadBudgetData = (limit?: number) => {
    setLoading(true);
    const url = limit
      ? `/budget?monthly_limit=${limit}`
      : '/budget';

    api.get<BudgetSummary>(url)
      .then(response => {
        setData(response.data);
        setLoading(false);
      })
      .catch(err => {
        console.error('Failed to load budget data', err);
        setLoading(false);
      });
  };

  useEffect(() => {
    loadBudgetData(savedLimit ?? undefined);
    // eslint-disable-next-line react-hooks/exhaustive-deps -- run once on mount using the lazily-initialized savedLimit
  }, []);

  const handleSetBudget = () => {
    const limit = parseFloat(budgetLimit);
    if (limit && limit > 0) {
      setSavedLimit(limit);
      localStorage.setItem('monthlyBudgetLimit', budgetLimit);
      loadBudgetData(limit);
      showToast('Monthly budget saved', 'signal');
    }
  };

  const handleClearBudget = () => {
    setSavedLimit(null);
    setBudgetLimit('');
    localStorage.removeItem('monthlyBudgetLimit');
    loadBudgetData();
    showToast('Budget limit cleared', 'signal');
  };

  if (loading) {
    return (
      <div className="mx-auto flex max-w-[1000px] items-center justify-center px-4 py-16 md:px-6">
        <Spinner label="Loading budget data…" />
      </div>
    );
  }
  if (!data) {
    return (
      <div className="mx-auto max-w-[1000px] px-4 py-6 md:px-6">
        <p className="text-sm text-muted">Failed to load budget data</p>
      </div>
    );
  }

  const daysInMonth = 30; // Simplified
  const daysRemaining = daysInMonth - data.day_of_month;
  const budgetStatus = data.on_track !== undefined ? data.on_track : null;

  return (
    <div className="mx-auto max-w-[1000px] px-4 py-6 md:px-6">
      <PageHeader eyebrow="Ledger / Budget" title="Budget tracker" />

      {/* Budget Setup */}
      <Card className="mb-6">
        <h2 className="mb-3.5 text-base font-semibold text-ink">Set monthly budget</h2>
        <div className="flex flex-col gap-3 sm:flex-row sm:items-end sm:flex-wrap">
          <div className="flex-1 sm:min-w-[180px]">
            <FormField label="Monthly limit ($)" htmlFor="budget-limit">
              <Input
                id="budget-limit"
                type="number"
                value={budgetLimit}
                onChange={(e) => setBudgetLimit(e.target.value)}
                placeholder="e.g. 2000"
                step="0.01"
              />
            </FormField>
          </div>
          <div className="flex gap-2">
            <button
              onClick={handleSetBudget}
              className="h-10 flex-1 rounded-lg bg-alert-amber px-5 text-sm font-semibold text-white sm:flex-none"
            >
              Set budget
            </button>
            {savedLimit && (
              <button
                onClick={handleClearBudget}
                className="h-10 flex-1 rounded-lg border border-line px-5 text-sm font-medium text-alert-red sm:flex-none"
              >
                Clear
              </button>
            )}
          </div>
        </div>
      </Card>

      {/* Current Month Overview */}
      <div className="mb-6 grid grid-cols-2 gap-4 lg:grid-cols-4">
        <StatCard
          label={`Current month (${data.current_month})`}
          value={`$${data.month_spending.toFixed(2)}`}
          detail={`Day ${data.day_of_month} of ${daysInMonth}`}
          tone="amber"
        />

        {data.monthly_limit && (
          <>
            <StatCard
              label="Remaining budget"
              value={`$${Math.abs(data.remaining ?? 0).toFixed(2)}`}
              detail={(data.remaining ?? 0) >= 0 ? 'under budget' : 'over budget'}
              tone={(data.remaining ?? 0) > 0 ? 'green' : 'red'}
            />
            <StatCard
              label="Budget used"
              value={`${(data.percentage_used ?? 0).toFixed(1)}%`}
              detail={`of $${data.monthly_limit.toFixed(2)}`}
              tone={(data.percentage_used ?? 0) > 100 ? 'red' : 'signal'}
            />
          </>
        )}

        <StatCard label="Daily average" value={`$${data.daily_average.toFixed(2)}`} detail="per day" tone="red" />
      </div>

      {/* Projection and Status */}
      <div className="mb-6 grid grid-cols-1 gap-5 lg:grid-cols-2">
        <Card>
          <h2 className={sectionTitle}>Projection</h2>
          <div className="mb-4">
            <p className="mb-1 text-sm text-muted">Projected month-end spending</p>
            <p className="font-mono text-xl font-bold text-signal">${data.projected_month_end.toFixed(2)}</p>
          </div>
          <div>
            <p className="mb-1 text-sm text-muted">Historical monthly average</p>
            <p className="font-mono text-lg font-bold text-ink-dim">${data.avg_monthly_historical.toFixed(2)}</p>
          </div>
          {data.monthly_limit && (
            <div
              className={`mt-4 rounded-lg bg-surface-dim px-3.5 py-3 border-l-[3px] ${
                data.projected_month_end > data.monthly_limit ? 'border-alert-red' : 'border-alert-green'
              }`}
            >
              <p className="text-sm text-ink-dim">
                {data.projected_month_end > data.monthly_limit
                  ? `Projected to exceed budget by $${(data.projected_month_end - data.monthly_limit).toFixed(2)}`
                  : `Projected to stay under budget by $${(data.monthly_limit - data.projected_month_end).toFixed(2)}`
                }
              </p>
            </div>
          )}
        </Card>

        {budgetStatus !== null && (
          <Card>
            <h2 className={sectionTitle}>Budget status</h2>
            <div
              className={`rounded-lg bg-surface-dim px-5 py-5 text-center border ${
                budgetStatus ? 'border-alert-green' : 'border-alert-red'
              }`}
            >
              <p className={`mb-2.5 text-lg font-bold ${budgetStatus ? 'text-alert-green' : 'text-alert-red'}`}>
                {budgetStatus ? 'On track' : 'Off track'}
              </p>
              <p className="text-sm text-muted">
                {budgetStatus
                  ? `You're spending at a pace that will keep you under budget.`
                  : `Your current spending pace will exceed your budget.`
                }
              </p>
            </div>
            <div className="mt-4 rounded-lg bg-surface-dim px-3.5 py-3">
              <p className="text-sm text-ink-dim">
                <strong className="text-ink">Recommended daily budget:</strong> ${data.monthly_limit ? (data.monthly_limit / daysInMonth).toFixed(2) : '0.00'}
              </p>
              {daysRemaining > 0 && data.remaining && data.remaining > 0 && (
                <p className="mt-1.5 text-sm text-ink-dim">
                  <strong className="text-ink">Remaining daily budget:</strong> ${(data.remaining / daysRemaining).toFixed(2)}
                </p>
              )}
            </div>
          </Card>
        )}
      </div>

      {/* Category Breakdown */}
      <div className="mb-6 grid grid-cols-1 gap-5 lg:grid-cols-2">
        <Card>
          <h2 className={sectionTitle}>Spending by category</h2>
          <div className="h-[300px]">
            <ResponsiveContainer width="100%" height="100%">
              <PieChart>
                <Pie
                  data={data.category_breakdown}
                  cx="50%"
                  cy="50%"
                  labelLine={false}
                  label={pieLabel}
                  outerRadius={100}
                  dataKey="total"
                >
                  {data.category_breakdown.map((_entry, index) => (
                    <Cell key={`cell-${index}`} fill={COLORS[index % COLORS.length]} />
                  ))}
                </Pie>
                <Tooltip
                  formatter={(value: unknown) => `$${Number(value).toFixed(2)}`}
                  contentStyle={{ background: 'var(--surface)', border: '1px solid var(--line)', borderRadius: 8, color: 'var(--ink)' }}
                />
              </PieChart>
            </ResponsiveContainer>
          </div>
        </Card>

        <Card>
          <h2 className={sectionTitle}>Category details</h2>
          <div className="flex max-h-[300px] flex-col gap-2 overflow-y-auto">
            {data.category_breakdown.map((cat, idx) => (
              <div key={cat.category} className="rounded-lg bg-surface-dim px-3 py-2.5">
                <div className="mb-1.5 flex justify-between">
                  <span className="text-sm font-semibold text-ink">{cat.category}</span>
                  <span className="font-mono text-sm font-bold" style={{ color: COLORS[idx % COLORS.length] }}>
                    ${cat.total.toFixed(2)}
                  </span>
                </div>
                <div className="flex items-center gap-2.5">
                  <div className="h-1.5 flex-1 overflow-hidden rounded-full bg-line">
                    <div
                      className="h-full"
                      style={{ width: `${cat.percentage}%`, background: COLORS[idx % COLORS.length] }}
                    />
                  </div>
                  <span className="min-w-[40px] text-right font-mono text-xs text-muted">
                    {cat.percentage.toFixed(1)}%
                  </span>
                </div>
              </div>
            ))}
          </div>
        </Card>
      </div>

      {/* Tips Section */}
      <Card>
        <h2 className={sectionTitle}>Budget tips</h2>
        <div className="grid grid-cols-1 gap-3 sm:grid-cols-3">
          <div className="rounded-lg bg-surface-dim px-4 py-3.5 border-l-[3px] border-alert-amber">
            <p className="text-sm leading-relaxed text-ink-dim">Track your spending daily to stay aware of where your money goes.</p>
          </div>
          <div className="rounded-lg bg-surface-dim px-4 py-3.5 border-l-[3px] border-signal">
            <p className="text-sm leading-relaxed text-ink-dim">Set category-specific budgets to better control spending.</p>
          </div>
          <div className="rounded-lg bg-surface-dim px-4 py-3.5 border-l-[3px] border-alert-red">
            <p className="text-sm leading-relaxed text-ink-dim">Review your largest spending categories for potential savings.</p>
          </div>
        </div>
      </Card>
    </div>
  );
};

export default Budget;
