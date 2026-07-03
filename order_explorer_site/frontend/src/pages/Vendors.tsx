import React, { useEffect, useState } from 'react';
import { api } from '../api';
import { BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer, CartesianGrid, PieChart, Pie, Cell, Legend } from 'recharts';
import type { PieLabelRenderProps } from 'recharts';
import PageHeader from '../components/ui/PageHeader';
import Card from '../components/ui/Card';

interface VendorData {
  vendor: string;
  total_spending: number;
  order_count: number;
  item_count: number;
  avg_order_value: number;
  top_categories: Array<{
    category: string;
    total: number;
  }>;
}

interface VendorAnalysis {
  vendors: VendorData[];
  total_vendors: number;
}

const COLORS = ['#c89b3c', '#4fa8a0', '#d8603f', '#e8c478', '#6ea87a'];
const AXIS = { fontSize: 12, fill: '#8b8f92' };
const TOOLTIP_STYLE = { background: '#1b2026', border: '1px solid #262c33', borderRadius: 8, color: '#e9e6dd' };

const thStyle = (align: 'left' | 'right' | 'center'): React.CSSProperties => ({
  padding: '13px 14px', textAlign: align, fontWeight: 600, fontSize: 11,
  fontFamily: 'var(--font-mono)', textTransform: 'uppercase', letterSpacing: '0.05em', color: 'var(--muted)',
});

const pieShareLabel = (props: PieLabelRenderProps) => {
  const { name, percent } = props as unknown as { name: string; percent: number };
  return `${name}: ${(percent * 100).toFixed(0)}%`;
};

const Vendors: React.FC = () => {
  const [data, setData] = useState<VendorAnalysis | null>(null);
  const [loading, setLoading] = useState(true);
  const [selectedVendor, setSelectedVendor] = useState<string | null>(null);

  useEffect(() => {
    api.get<VendorAnalysis>('/vendors')
      .then(response => {
        setData(response.data);
        setLoading(false);
      })
      .catch(err => {
        console.error('Failed to load vendor analysis', err);
        setLoading(false);
      });
  }, []);

  if (loading) return <div style={{ padding: 24, color: 'var(--muted)' }}>Loading vendors…</div>;
  if (!data) return <div style={{ padding: 24, color: 'var(--muted)' }}>Failed to load vendors</div>;

  const selectedVendorData = data.vendors.find(v => v.vendor === selectedVendor);

  return (
    <div style={{ padding: '24px 24px 48px' }}>
      <PageHeader eyebrow="Ledger / Vendors" title="Vendor analysis" />

      {/* Summary Cards */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(220px, 1fr))', gap: '16px', marginBottom: '28px' }}>
        {data.vendors.map((vendor, idx) => (
          <Card key={vendor.vendor}>
            <h3 style={{ margin: '0 0 10px 0', fontSize: '15px', color: 'var(--paper)', fontWeight: 700 }}>{vendor.vendor}</h3>
            <p style={{ margin: 0, fontSize: '24px', fontWeight: 700, fontFamily: 'var(--font-mono)', color: COLORS[idx % COLORS.length] }}>
              ${vendor.total_spending.toFixed(2)}
            </p>
            <p style={{ margin: '6px 0 0', fontSize: '13px', color: 'var(--muted)' }}>{vendor.order_count} orders · {vendor.item_count} items</p>
            <p style={{ margin: '2px 0 0', fontSize: '13px', color: 'var(--muted)' }}>Avg ${vendor.avg_order_value.toFixed(2)}/order</p>
          </Card>
        ))}
      </div>

      {/* Charts */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(380px, 1fr))', gap: '20px', marginBottom: '28px' }}>
        <Card>
          <h2 style={{ fontSize: 13, fontFamily: 'var(--font-mono)', letterSpacing: '0.06em', textTransform: 'uppercase', marginBottom: 16, color: 'var(--muted)' }}>Total spending by vendor</h2>
          <div style={{ height: '300px' }}>
            <ResponsiveContainer width="100%" height="100%">
              <BarChart data={data.vendors}>
                <CartesianGrid strokeDasharray="3 3" stroke="#262c33" />
                <XAxis dataKey="vendor" tick={AXIS} />
                <YAxis tick={AXIS} />
                <Tooltip formatter={(value: any) => `$${value.toFixed(2)}`} contentStyle={TOOLTIP_STYLE} />
                <Bar dataKey="total_spending" fill="#c89b3c" radius={[4, 4, 0, 0]} />
              </BarChart>
            </ResponsiveContainer>
          </div>
        </Card>

        <Card>
          <h2 style={{ fontSize: 13, fontFamily: 'var(--font-mono)', letterSpacing: '0.06em', textTransform: 'uppercase', marginBottom: 16, color: 'var(--muted)' }}>Order distribution</h2>
          <div style={{ height: '300px' }}>
            <ResponsiveContainer width="100%" height="100%">
              <PieChart>
                <Pie
                  data={data.vendors.map(v => ({ name: v.vendor, value: v.order_count }))}
                  cx="50%"
                  cy="50%"
                  labelLine={false}
                  label={pieShareLabel}
                  outerRadius={100}
                  dataKey="value"
                >
                  {data.vendors.map((_entry, index) => (
                    <Cell key={`cell-${index}`} fill={COLORS[index % COLORS.length]} />
                  ))}
                </Pie>
                <Tooltip contentStyle={TOOLTIP_STYLE} />
                <Legend wrapperStyle={{ fontSize: 12, color: '#8b8f92' }} />
              </PieChart>
            </ResponsiveContainer>
          </div>
        </Card>
      </div>

      {/* Vendor Comparison Table */}
      <div style={{ border: '1px solid var(--ink-700)', borderRadius: '10px', overflow: 'hidden' }}>
        <h2 style={{ margin: 0, padding: '16px 20px', borderBottom: '1px solid var(--ink-700)', background: 'var(--ink-800)', fontSize: 13, fontFamily: 'var(--font-mono)', letterSpacing: '0.06em', textTransform: 'uppercase', color: 'var(--muted)' }}>
          Vendor comparison
        </h2>
        <div style={{ overflowX: 'auto' }}>
          <table style={{ width: '100%', borderCollapse: 'collapse' }}>
            <thead>
              <tr style={{ background: 'var(--ink-750)' }}>
                <th style={thStyle('left')}>Vendor</th>
                <th style={thStyle('right')}>Total spending</th>
                <th style={thStyle('center')}>Orders</th>
                <th style={thStyle('center')}>Items</th>
                <th style={thStyle('right')}>Avg order value</th>
                <th style={thStyle('center')}>Details</th>
              </tr>
            </thead>
            <tbody>
              {data.vendors.map((vendor, idx) => (
                <React.Fragment key={vendor.vendor}>
                  <tr style={{ backgroundColor: idx % 2 === 0 ? 'var(--ink-800)' : 'var(--ink-900)' }}>
                    <td style={{ padding: '14px', fontWeight: 700, color: 'var(--paper)' }}>{vendor.vendor}</td>
                    <td style={{ padding: '14px', textAlign: 'right', fontSize: '16px', fontWeight: 700, fontFamily: 'var(--font-mono)', color: 'var(--stamp-gold)' }}>
                      ${vendor.total_spending.toFixed(2)}
                    </td>
                    <td style={{ padding: '14px', textAlign: 'center', color: 'var(--paper-dim)' }}>{vendor.order_count}</td>
                    <td style={{ padding: '14px', textAlign: 'center', color: 'var(--paper-dim)' }}>{vendor.item_count}</td>
                    <td style={{ padding: '14px', textAlign: 'right', color: 'var(--muted)', fontFamily: 'var(--font-mono)', fontSize: 13 }}>${vendor.avg_order_value.toFixed(2)}</td>
                    <td style={{ padding: '14px', textAlign: 'center' }}>
                      <button onClick={() => setSelectedVendor(selectedVendor === vendor.vendor ? null : vendor.vendor)} style={{ padding: '6px 14px', fontSize: '13px', fontWeight: 600 }}>
                        {selectedVendor === vendor.vendor ? 'Hide' : 'Show'}
                      </button>
                    </td>
                  </tr>

                  {selectedVendor === vendor.vendor && selectedVendorData && (
                    <tr>
                      <td colSpan={6} style={{ padding: '20px', background: 'var(--ink-900)' }}>
                        <h4 style={{ marginBottom: 12, fontSize: 12.5, fontFamily: 'var(--font-mono)', textTransform: 'uppercase', letterSpacing: '0.05em', color: 'var(--muted)' }}>Top categories at {vendor.vendor}</h4>
                        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))', gap: '10px' }}>
                          {selectedVendorData.top_categories.map((cat, catIdx) => (
                            <div key={catIdx} style={{ display: 'flex', justifyContent: 'space-between', padding: '10px 12px', background: 'var(--ink-800)', borderRadius: '8px', border: '1px solid var(--ink-700)' }}>
                              <span style={{ fontWeight: 600, color: 'var(--paper)', fontSize: 13.5 }}>{cat.category}</span>
                              <span style={{ color: 'var(--stamp-gold)', fontWeight: 700, fontFamily: 'var(--font-mono)' }}>${cat.total.toFixed(2)}</span>
                            </div>
                          ))}
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

      {/* Insights Section */}
      <Card style={{ marginTop: '28px' }}>
        <h2 style={{ fontSize: 13, fontFamily: 'var(--font-mono)', letterSpacing: '0.06em', textTransform: 'uppercase', marginBottom: 16, color: 'var(--muted)' }}>Insights</h2>
        <div style={{ display: 'flex', flexDirection: 'column', gap: '10px' }}>
          {data.vendors.length > 0 && (
            <>
              <div style={{ padding: '13px 16px', background: 'var(--ink-900)', borderRadius: '8px', borderLeft: '3px solid var(--stamp-gold)' }}>
                <p style={{ margin: 0, fontSize: '13.5px', color: 'var(--paper-dim)' }}>
                  <strong style={{ color: 'var(--paper)' }}>{data.vendors[0].vendor}</strong> is your most used vendor with ${data.vendors[0].total_spending.toFixed(2)} in total spending.
                </p>
              </div>
              {data.vendors.length > 1 && (
                <div style={{ padding: '13px 16px', background: 'var(--ink-900)', borderRadius: '8px', borderLeft: '3px solid var(--stamp-teal)' }}>
                  <p style={{ margin: 0, fontSize: '13.5px', color: 'var(--paper-dim)' }}>
                    Your average order value is highest at <strong style={{ color: 'var(--paper)' }}>{data.vendors.reduce((max, v) => v.avg_order_value > max.avg_order_value ? v : max).vendor}</strong>
                    {' '}(${data.vendors.reduce((max, v) => v.avg_order_value > max.avg_order_value ? v : max).avg_order_value.toFixed(2)}/order).
                  </p>
                </div>
              )}
              <div style={{ padding: '13px 16px', background: 'var(--ink-900)', borderRadius: '8px', borderLeft: '3px solid var(--stamp-ember)' }}>
                <p style={{ margin: 0, fontSize: '13.5px', color: 'var(--paper-dim)' }}>
                  You've placed a total of <strong style={{ color: 'var(--paper)' }}>{data.vendors.reduce((sum, v) => sum + v.order_count, 0)} orders</strong> across all vendors.
                </p>
              </div>
            </>
          )}
        </div>
      </Card>
    </div>
  );
};

export default Vendors;
