import React, { useEffect, useState } from 'react';
import { api } from '../api';
import { PieChart, Pie, Cell, ResponsiveContainer, Tooltip, Legend, BarChart, Bar, XAxis, YAxis, CartesianGrid } from 'recharts';
import type { PieLabelRenderProps } from 'recharts';
import PageHeader from '../components/ui/PageHeader';
import Card from '../components/ui/Card';

interface CategoryData {
  category: string;
  total_spending: number;
  item_count: number;
  order_count: number;
  avg_price: number;
  sources: Record<string, number>;
  monthly_trend: Array<{
    month: string;
    total: number;
  }>;
}

interface CategoryAnalysis {
  categories: CategoryData[];
  total_categories: number;
  top_category: CategoryData | null;
}

const COLORS = ['#c89b3c', '#4fa8a0', '#d8603f', '#e8c478', '#6ea87a', '#8f7fd6', '#4a90c4', '#b6588c', '#a67c9c', '#7fa66b'];
const AXIS = { fontSize: 12, fill: '#8b8f92' };
const TOOLTIP_STYLE = { background: '#1b2026', border: '1px solid #262c33', borderRadius: 8, color: '#e9e6dd' };
const statLabel: React.CSSProperties = { margin: 0, fontSize: '11px', color: 'var(--muted)', fontFamily: 'var(--font-mono)', textTransform: 'uppercase', letterSpacing: '0.04em' };

const thStyle = (align: 'left' | 'right' | 'center'): React.CSSProperties => ({
  padding: '13px 14px', textAlign: align, fontWeight: 600, fontSize: 11,
  fontFamily: 'var(--font-mono)', textTransform: 'uppercase', letterSpacing: '0.05em', color: 'var(--muted)',
});

const pieShareLabel = (props: PieLabelRenderProps) => {
  const { name, percent } = props as unknown as { name: string; percent: number };
  return `${name}: ${(percent * 100).toFixed(0)}%`;
};

const Categories: React.FC = () => {
  const [data, setData] = useState<CategoryAnalysis | null>(null);
  const [loading, setLoading] = useState(true);
  const [selectedCategory, setSelectedCategory] = useState<string | null>(null);

  useEffect(() => {
    api.get<CategoryAnalysis>('/categories')
      .then(response => {
        setData(response.data);
        setLoading(false);
      })
      .catch(err => {
        console.error('Failed to load category analysis', err);
        setLoading(false);
      });
  }, []);

  if (loading) return <div style={{ padding: 24, color: 'var(--muted)' }}>Loading categories…</div>;
  if (!data) return <div style={{ padding: 24, color: 'var(--muted)' }}>Failed to load categories</div>;

  const pieData = data.categories.map(cat => ({
    name: cat.category,
    value: cat.total_spending
  }));

  const selectedCategoryData = data.categories.find(c => c.category === selectedCategory);

  return (
    <div style={{ padding: '24px 24px 48px' }}>
      <PageHeader eyebrow="Ledger / Categories" title="Category analysis" />

      {/* Summary Cards */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(220px, 1fr))', gap: '16px', marginBottom: '28px' }}>
        <Card>
          <h3 style={statLabel}>Total categories</h3>
          <p style={{ margin: '10px 0 0', fontSize: '28px', fontWeight: 700, fontFamily: 'var(--font-mono)', color: 'var(--stamp-gold)' }}>{data.total_categories}</p>
        </Card>

        {data.top_category && (
          <>
            <Card>
              <h3 style={statLabel}>Top category</h3>
              <p style={{ margin: '10px 0 0', fontSize: '20px', fontWeight: 700, color: 'var(--paper)' }}>{data.top_category.category}</p>
              <p style={{ margin: '4px 0 0', fontSize: '13px', color: 'var(--muted)' }}>${data.top_category.total_spending.toFixed(2)}</p>
            </Card>

            <Card>
              <h3 style={statLabel}>Top category items</h3>
              <p style={{ margin: '10px 0 0', fontSize: '28px', fontWeight: 700, fontFamily: 'var(--font-mono)', color: 'var(--stamp-ember)' }}>{data.top_category.item_count}</p>
            </Card>
          </>
        )}
      </div>

      {/* Charts */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(380px, 1fr))', gap: '20px', marginBottom: '28px' }}>
        <Card>
          <h2 style={{ fontSize: 13, fontFamily: 'var(--font-mono)', letterSpacing: '0.06em', textTransform: 'uppercase', marginBottom: 16, color: 'var(--muted)' }}>Spending distribution</h2>
          <div style={{ height: '350px' }}>
            <ResponsiveContainer width="100%" height="100%">
              <PieChart>
                <Pie
                  data={pieData}
                  cx="50%"
                  cy="50%"
                  labelLine={false}
                  label={pieShareLabel}
                  outerRadius={100}
                  dataKey="value"
                >
                  {pieData.map((_entry, index) => (
                    <Cell key={`cell-${index}`} fill={COLORS[index % COLORS.length]} />
                  ))}
                </Pie>
                <Tooltip formatter={(value: any) => `$${value.toFixed(2)}`} contentStyle={TOOLTIP_STYLE} />
                <Legend wrapperStyle={{ fontSize: 12, color: '#8b8f92' }} />
              </PieChart>
            </ResponsiveContainer>
          </div>
        </Card>

        <Card>
          <h2 style={{ fontSize: 13, fontFamily: 'var(--font-mono)', letterSpacing: '0.06em', textTransform: 'uppercase', marginBottom: 16, color: 'var(--muted)' }}>Top categories by spending</h2>
          <div style={{ height: '350px' }}>
            <ResponsiveContainer width="100%" height="100%">
              <BarChart data={data.categories.slice(0, 10)}>
                <CartesianGrid strokeDasharray="3 3" stroke="#262c33" />
                <XAxis dataKey="category" angle={-45} textAnchor="end" height={100} tick={AXIS} />
                <YAxis tick={AXIS} />
                <Tooltip formatter={(value: any) => `$${value.toFixed(2)}`} contentStyle={TOOLTIP_STYLE} />
                <Bar dataKey="total_spending" fill="#c89b3c" radius={[4, 4, 0, 0]} />
              </BarChart>
            </ResponsiveContainer>
          </div>
        </Card>
      </div>

      {/* Category Details Table */}
      <div style={{ border: '1px solid var(--ink-700)', borderRadius: '10px', overflow: 'hidden' }}>
        <h2 style={{ margin: 0, padding: '16px 20px', borderBottom: '1px solid var(--ink-700)', background: 'var(--ink-800)', fontSize: 13, fontFamily: 'var(--font-mono)', letterSpacing: '0.06em', textTransform: 'uppercase', color: 'var(--muted)' }}>
          Category details
        </h2>
        <div style={{ overflowX: 'auto' }}>
          <table style={{ width: '100%', borderCollapse: 'collapse' }}>
            <thead>
              <tr style={{ background: 'var(--ink-750)' }}>
                <th style={thStyle('left')}>Category</th>
                <th style={thStyle('right')}>Total spending</th>
                <th style={thStyle('center')}>Items</th>
                <th style={thStyle('center')}>Orders</th>
                <th style={thStyle('right')}>Avg price</th>
                <th style={thStyle('center')}>Details</th>
              </tr>
            </thead>
            <tbody>
              {data.categories.map((cat, idx) => (
                <React.Fragment key={cat.category}>
                  <tr style={{ backgroundColor: idx % 2 === 0 ? 'var(--ink-800)' : 'var(--ink-900)' }}>
                    <td style={{ padding: '14px', fontWeight: 700, color: 'var(--paper)' }}>{cat.category}</td>
                    <td style={{ padding: '14px', textAlign: 'right', fontSize: '16px', fontWeight: 700, fontFamily: 'var(--font-mono)', color: 'var(--stamp-gold)' }}>
                      ${cat.total_spending.toFixed(2)}
                    </td>
                    <td style={{ padding: '14px', textAlign: 'center', color: 'var(--paper-dim)' }}>{cat.item_count}</td>
                    <td style={{ padding: '14px', textAlign: 'center', color: 'var(--paper-dim)' }}>{cat.order_count}</td>
                    <td style={{ padding: '14px', textAlign: 'right', color: 'var(--muted)', fontFamily: 'var(--font-mono)', fontSize: 13 }}>${cat.avg_price.toFixed(2)}</td>
                    <td style={{ padding: '14px', textAlign: 'center' }}>
                      <button onClick={() => setSelectedCategory(selectedCategory === cat.category ? null : cat.category)} style={{ padding: '6px 14px', fontSize: '13px', fontWeight: 600 }}>
                        {selectedCategory === cat.category ? 'Hide' : 'Show'}
                      </button>
                    </td>
                  </tr>

                  {selectedCategory === cat.category && selectedCategoryData && (
                    <tr>
                      <td colSpan={6} style={{ padding: '20px', background: 'var(--ink-900)' }}>
                        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(280px, 1fr))', gap: '20px' }}>
                          <div>
                            <h4 style={{ marginBottom: 10, fontSize: 12.5, fontFamily: 'var(--font-mono)', textTransform: 'uppercase', letterSpacing: '0.05em', color: 'var(--muted)' }}>Purchase sources</h4>
                            <div style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
                              {Object.entries(selectedCategoryData.sources).map(([source, count]) => (
                                <div key={source} style={{ display: 'flex', justifyContent: 'space-between', padding: '10px 12px', background: 'var(--ink-800)', borderRadius: '6px' }}>
                                  <span style={{ fontWeight: 600, color: 'var(--paper)', fontSize: 13.5 }}>{source}</span>
                                  <span style={{ color: 'var(--muted)', fontSize: 13 }}>{count} orders</span>
                                </div>
                              ))}
                            </div>
                          </div>

                          <div>
                            <h4 style={{ marginBottom: 10, fontSize: 12.5, fontFamily: 'var(--font-mono)', textTransform: 'uppercase', letterSpacing: '0.05em', color: 'var(--muted)' }}>Monthly trend</h4>
                            <div style={{ height: '200px' }}>
                              <ResponsiveContainer width="100%" height="100%">
                                <BarChart data={selectedCategoryData.monthly_trend.slice(-6)}>
                                  <CartesianGrid strokeDasharray="3 3" stroke="#262c33" />
                                  <XAxis dataKey="month" tick={AXIS} />
                                  <YAxis tick={AXIS} />
                                  <Tooltip formatter={(value: any) => `$${value.toFixed(2)}`} contentStyle={TOOLTIP_STYLE} />
                                  <Bar dataKey="total" fill="#4fa8a0" radius={[4, 4, 0, 0]} />
                                </BarChart>
                              </ResponsiveContainer>
                            </div>
                          </div>
                        </div>
                      </td>
                    </tr>
                  )}
                </React.Fragment>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
};

export default Categories;
