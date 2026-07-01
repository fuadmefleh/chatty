import React, { useEffect, useState } from 'react';
import axios from 'axios';
import { ResponsiveContainer, PieChart, Pie, Cell, Tooltip } from 'recharts';
import type { PieLabelRenderProps } from 'recharts';
import PageHeader from '../components/ui/PageHeader';
import Card from '../components/ui/Card';

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
const statLabel: React.CSSProperties = { margin: 0, fontSize: '11px', color: 'var(--muted)', fontFamily: 'var(--font-mono)', textTransform: 'uppercase', letterSpacing: '0.04em' };

const pieLabel = (props: PieLabelRenderProps) => {
  const { category, percentage } = props as unknown as { category: string; percentage: number };
  return `${category}: ${percentage.toFixed(0)}%`;
};

const Budget: React.FC = () => {
  const [data, setData] = useState<BudgetSummary | null>(null);
  const [loading, setLoading] = useState(true);
  const [budgetLimit, setBudgetLimit] = useState<string>('');
  const [savedLimit, setSavedLimit] = useState<number | null>(null);

  const loadBudgetData = (limit?: number) => {
    setLoading(true);
    const url = limit
      ? `http://localhost:8015/budget?monthly_limit=${limit}`
      : 'http://localhost:8015/budget';

    axios.get<BudgetSummary>(url)
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
    const saved = localStorage.getItem('monthlyBudgetLimit');
    if (saved) {
      const limit = parseFloat(saved);
      setSavedLimit(limit);
      setBudgetLimit(saved);
      loadBudgetData(limit);
    } else {
      loadBudgetData();
    }
  }, []);

  const handleSetBudget = () => {
    const limit = parseFloat(budgetLimit);
    if (limit && limit > 0) {
      setSavedLimit(limit);
      localStorage.setItem('monthlyBudgetLimit', budgetLimit);
      loadBudgetData(limit);
    }
  };

  const handleClearBudget = () => {
    setSavedLimit(null);
    setBudgetLimit('');
    localStorage.removeItem('monthlyBudgetLimit');
    loadBudgetData();
  };

  if (loading) return <div style={{ padding: 24, color: 'var(--muted)' }}>Loading budget data…</div>;
  if (!data) return <div style={{ padding: 24, color: 'var(--muted)' }}>Failed to load budget data</div>;

  const daysInMonth = 30; // Simplified
  const daysRemaining = daysInMonth - data.day_of_month;
  const budgetStatus = data.on_track !== undefined ? data.on_track : null;

  return (
    <div style={{ padding: '24px 24px 48px' }}>
      <PageHeader eyebrow="Ledger / Budget" title="Budget tracker" />

      {/* Budget Setup */}
      <Card style={{ marginBottom: '28px' }}>
        <h2 style={{ fontSize: 15, marginBottom: 14, color: 'var(--paper)' }}>Set monthly budget</h2>
        <div style={{ display: 'flex', gap: '10px', alignItems: 'flex-end', flexWrap: 'wrap' }}>
          <div style={{ flex: 1, minWidth: 180 }}>
            <label style={{ display: 'block', marginBottom: '6px', fontSize: '12px', fontWeight: 600, color: 'var(--muted)', fontFamily: 'var(--font-mono)', textTransform: 'uppercase' }}>
              Monthly limit ($)
            </label>
            <input
              type="number"
              value={budgetLimit}
              onChange={(e) => setBudgetLimit(e.target.value)}
              placeholder="e.g. 2000"
              step="0.01"
              style={{ width: '100%', padding: '11px', borderRadius: '6px', fontSize: '15px' }}
            />
          </div>
          <button onClick={handleSetBudget} style={{ background: 'var(--stamp-gold)', color: 'var(--ink-900)', padding: '12px 22px', fontSize: '14px', fontWeight: 700 }}>
            Set budget
          </button>
          {savedLimit && (
            <button onClick={handleClearBudget} style={{ padding: '12px 22px', fontSize: '14px', fontWeight: 600, color: 'var(--danger)', border: '1px solid var(--ink-600)' }}>
              Clear
            </button>
          )}
        </div>
      </Card>

      {/* Current Month Overview */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(220px, 1fr))', gap: '16px', marginBottom: '28px' }}>
        <Card>
          <h3 style={statLabel}>Current month ({data.current_month})</h3>
          <p style={{ margin: '10px 0 0', fontSize: '28px', fontWeight: 700, fontFamily: 'var(--font-mono)', color: 'var(--stamp-gold)' }}>${data.month_spending.toFixed(2)}</p>
          <p style={{ margin: '4px 0 0', fontSize: '13px', color: 'var(--muted)' }}>Day {data.day_of_month} of {daysInMonth}</p>
        </Card>

        {data.monthly_limit && (
          <>
            <Card>
              <h3 style={statLabel}>Remaining budget</h3>
              <p style={{ margin: '10px 0 0', fontSize: '28px', fontWeight: 700, fontFamily: 'var(--font-mono)', color: (data.remaining ?? 0) > 0 ? 'var(--success)' : 'var(--danger)' }}>
                ${Math.abs(data.remaining ?? 0).toFixed(2)}
              </p>
              <p style={{ margin: '4px 0 0', fontSize: '13px', color: 'var(--muted)' }}>{(data.remaining ?? 0) >= 0 ? 'under budget' : 'over budget'}</p>
            </Card>

            <Card>
              <h3 style={statLabel}>Budget used</h3>
              <p style={{ margin: '10px 0 0', fontSize: '28px', fontWeight: 700, fontFamily: 'var(--font-mono)', color: (data.percentage_used ?? 0) > 100 ? 'var(--danger)' : 'var(--stamp-teal)' }}>
                {(data.percentage_used ?? 0).toFixed(1)}%
              </p>
              <p style={{ margin: '4px 0 0', fontSize: '13px', color: 'var(--muted)' }}>of ${data.monthly_limit.toFixed(2)}</p>
            </Card>
          </>
        )}

        <Card>
          <h3 style={statLabel}>Daily average</h3>
          <p style={{ margin: '10px 0 0', fontSize: '28px', fontWeight: 700, fontFamily: 'var(--font-mono)', color: 'var(--stamp-ember)' }}>${data.daily_average.toFixed(2)}</p>
          <p style={{ margin: '4px 0 0', fontSize: '13px', color: 'var(--muted)' }}>per day</p>
        </Card>
      </div>

      {/* Projection and Status */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(350px, 1fr))', gap: '20px', marginBottom: '28px' }}>
        <Card>
          <h2 style={{ fontSize: 13, fontFamily: 'var(--font-mono)', letterSpacing: '0.06em', textTransform: 'uppercase', marginBottom: 16, color: 'var(--muted)' }}>Projection</h2>
          <div style={{ marginBottom: '16px' }}>
            <p style={{ margin: '0 0 5px 0', fontSize: '13px', color: 'var(--muted)' }}>Projected month-end spending</p>
            <p style={{ margin: 0, fontSize: '24px', fontWeight: 700, fontFamily: 'var(--font-mono)', color: 'var(--stamp-teal)' }}>${data.projected_month_end.toFixed(2)}</p>
          </div>
          <div>
            <p style={{ margin: '0 0 5px 0', fontSize: '13px', color: 'var(--muted)' }}>Historical monthly average</p>
            <p style={{ margin: 0, fontSize: '20px', fontWeight: 700, fontFamily: 'var(--font-mono)', color: 'var(--paper-dim)' }}>${data.avg_monthly_historical.toFixed(2)}</p>
          </div>
          {data.monthly_limit && (
            <div style={{
              marginTop: '16px',
              padding: '12px 14px',
              background: 'var(--ink-900)',
              borderRadius: '8px',
              borderLeft: `3px solid ${data.projected_month_end > data.monthly_limit ? 'var(--danger)' : 'var(--success)'}`
            }}>
              <p style={{ margin: 0, fontSize: '13px', color: 'var(--paper-dim)' }}>
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
            <h2 style={{ fontSize: 13, fontFamily: 'var(--font-mono)', letterSpacing: '0.06em', textTransform: 'uppercase', marginBottom: 16, color: 'var(--muted)' }}>Budget status</h2>
            <div style={{ padding: '20px', background: 'var(--ink-900)', borderRadius: '8px', textAlign: 'center', border: `1px solid ${budgetStatus ? 'var(--success)' : 'var(--danger)'}` }}>
              <p style={{ margin: '0 0 10px 0', fontSize: '20px', fontWeight: 700, color: budgetStatus ? 'var(--success)' : 'var(--danger)' }}>
                {budgetStatus ? 'On track' : 'Off track'}
              </p>
              <p style={{ margin: 0, fontSize: '13px', color: 'var(--muted)' }}>
                {budgetStatus
                  ? `You're spending at a pace that will keep you under budget.`
                  : `Your current spending pace will exceed your budget.`
                }
              </p>
            </div>
            <div style={{ marginTop: '16px', padding: '12px 14px', background: 'var(--ink-900)', borderRadius: '8px' }}>
              <p style={{ margin: 0, fontSize: '13px', color: 'var(--paper-dim)' }}>
                <strong style={{ color: 'var(--paper)' }}>Recommended daily budget:</strong> ${data.monthly_limit ? (data.monthly_limit / daysInMonth).toFixed(2) : '0.00'}
              </p>
              {daysRemaining > 0 && data.remaining && data.remaining > 0 && (
                <p style={{ margin: '6px 0 0 0', fontSize: '13px', color: 'var(--paper-dim)' }}>
                  <strong style={{ color: 'var(--paper)' }}>Remaining daily budget:</strong> ${(data.remaining / daysRemaining).toFixed(2)}
                </p>
              )}
            </div>
          </Card>
        )}
      </div>

      {/* Category Breakdown */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(380px, 1fr))', gap: '20px', marginBottom: '28px' }}>
        <Card>
          <h2 style={{ fontSize: 13, fontFamily: 'var(--font-mono)', letterSpacing: '0.06em', textTransform: 'uppercase', marginBottom: 16, color: 'var(--muted)' }}>Spending by category</h2>
          <div style={{ height: '300px' }}>
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
                  formatter={(value: any) => `$${value.toFixed(2)}`}
                  contentStyle={{ background: '#1b2026', border: '1px solid #262c33', borderRadius: 8, color: '#e9e6dd' }}
                />
              </PieChart>
            </ResponsiveContainer>
          </div>
        </Card>

        <Card>
          <h2 style={{ fontSize: 13, fontFamily: 'var(--font-mono)', letterSpacing: '0.06em', textTransform: 'uppercase', marginBottom: 16, color: 'var(--muted)' }}>Category details</h2>
          <div style={{ maxHeight: '300px', overflowY: 'auto', display: 'flex', flexDirection: 'column', gap: 8 }}>
            {data.category_breakdown.map((cat, idx) => (
              <div key={cat.category} style={{ padding: '10px 12px', background: 'var(--ink-900)', borderRadius: '8px' }}>
                <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '6px' }}>
                  <span style={{ fontWeight: 600, color: 'var(--paper)', fontSize: 13.5 }}>{cat.category}</span>
                  <span style={{ fontWeight: 700, fontFamily: 'var(--font-mono)', color: COLORS[idx % COLORS.length] }}>
                    ${cat.total.toFixed(2)}
                  </span>
                </div>
                <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
                  <div style={{ flex: 1, height: '6px', background: 'var(--ink-700)', borderRadius: '4px', overflow: 'hidden' }}>
                    <div style={{ width: `${cat.percentage}%`, height: '100%', background: COLORS[idx % COLORS.length] }} />
                  </div>
                  <span style={{ fontSize: '11px', color: 'var(--muted)', minWidth: '40px', textAlign: 'right', fontFamily: 'var(--font-mono)' }}>
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
        <h2 style={{ fontSize: 13, fontFamily: 'var(--font-mono)', letterSpacing: '0.06em', textTransform: 'uppercase', marginBottom: 16, color: 'var(--muted)' }}>Budget tips</h2>
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(220px, 1fr))', gap: '12px' }}>
          <div style={{ padding: '13px 16px', background: 'var(--ink-900)', borderRadius: '8px', borderLeft: '3px solid var(--stamp-gold)' }}>
            <p style={{ margin: 0, fontSize: '13.5px', color: 'var(--paper-dim)' }}>Track your spending daily to stay aware of where your money goes.</p>
          </div>
          <div style={{ padding: '13px 16px', background: 'var(--ink-900)', borderRadius: '8px', borderLeft: '3px solid var(--stamp-teal)' }}>
            <p style={{ margin: 0, fontSize: '13.5px', color: 'var(--paper-dim)' }}>Set category-specific budgets to better control spending.</p>
          </div>
          <div style={{ padding: '13px 16px', background: 'var(--ink-900)', borderRadius: '8px', borderLeft: '3px solid var(--stamp-ember)' }}>
            <p style={{ margin: 0, fontSize: '13.5px', color: 'var(--paper-dim)' }}>Review your largest spending categories for potential savings.</p>
          </div>
        </div>
      </Card>
    </div>
  );
};

export default Budget;
