import React, { useState, useEffect } from 'react';
import { api } from '../api';
import { Link } from 'react-router-dom';
import PageHeader from '../components/ui/PageHeader';
import Card from '../components/ui/Card';

interface Item {
  name: string;
  price: number;
  quantity: number;
  total_price: number;
  category: string;
  date: string;
  source: string;
  order_id: string;
}

const fieldLabel: React.CSSProperties = { display: 'block', marginBottom: '6px', fontSize: '12px', fontWeight: 600, fontFamily: 'var(--font-mono)', textTransform: 'uppercase', letterSpacing: '0.04em', color: 'var(--muted)' };
const fieldInput: React.CSSProperties = { width: '100%', padding: '10px', borderRadius: '6px', fontSize: '14px' };

const Search: React.FC = () => {
  const [query, setQuery] = useState('');
  const [results, setResults] = useState<Item[]>([]);
  const [loading, setLoading] = useState(false);
  const [category, setCategory] = useState('');
  const [source, setSource] = useState('');
  const [minPrice, setMinPrice] = useState('');
  const [maxPrice, setMaxPrice] = useState('');
  const [categories, setCategories] = useState<string[]>([]);
  const [sources, setSources] = useState<string[]>([]);

  // Load all items on mount to get categories and sources
  useEffect(() => {
    api.get<Item[]>('/items')
      .then(response => {
        const uniqueCategories = Array.from(new Set(response.data.map(i => i.category).filter(Boolean)));
        const uniqueSources = Array.from(new Set(response.data.map(i => i.source).filter(Boolean)));

        setCategories(uniqueCategories.sort());
        setSources(uniqueSources.sort());
      })
      .catch(err => console.error('Failed to load items', err));
  }, []);

  const handleSearch = () => {
    setLoading(true);

    const params = new URLSearchParams();
    if (query) params.append('q', query);
    if (category) params.append('category', category);
    if (source) params.append('source', source);
    if (minPrice) params.append('min_price', minPrice);
    if (maxPrice) params.append('max_price', maxPrice);

    api.get<Item[]>(`/search?${params.toString()}`)
      .then(response => {
        setResults(response.data);
        setLoading(false);
      })
      .catch(err => {
        console.error('Search failed', err);
        setLoading(false);
      });
  };

  // Group results by item name for comparison
  const groupedResults = results.reduce((acc, item) => {
    const name = item.name || 'Unknown';
    if (!acc[name]) {
      acc[name] = [];
    }
    acc[name].push(item);
    return acc;
  }, {} as Record<string, Item[]>);

  return (
    <div style={{ padding: '24px 24px 48px' }}>
      <PageHeader eyebrow="Ledger / Search" title="Advanced search" />

      {/* Search Filters */}
      <Card style={{ marginBottom: 28 }}>
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))', gap: '15px', marginBottom: '18px' }}>
          <div>
            <label style={fieldLabel}>Search term</label>
            <input
              type="text"
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              placeholder="Enter item name…"
              style={fieldInput}
              onKeyDown={(e) => e.key === 'Enter' && handleSearch()}
            />
          </div>

          <div>
            <label style={fieldLabel}>Category</label>
            <select value={category} onChange={(e) => setCategory(e.target.value)} style={fieldInput}>
              <option value="">All categories</option>
              {categories.map(cat => (
                <option key={cat} value={cat}>{cat}</option>
              ))}
            </select>
          </div>

          <div>
            <label style={fieldLabel}>Source</label>
            <select value={source} onChange={(e) => setSource(e.target.value)} style={fieldInput}>
              <option value="">All sources</option>
              {sources.map(src => (
                <option key={src} value={src}>{src}</option>
              ))}
            </select>
          </div>

          <div>
            <label style={fieldLabel}>Min price</label>
            <input type="number" value={minPrice} onChange={(e) => setMinPrice(e.target.value)} placeholder="$0" step="0.01" style={fieldInput} />
          </div>

          <div>
            <label style={fieldLabel}>Max price</label>
            <input type="number" value={maxPrice} onChange={(e) => setMaxPrice(e.target.value)} placeholder="$999" step="0.01" style={fieldInput} />
          </div>
        </div>

        <div style={{ display: 'flex', gap: '10px' }}>
          <button
            onClick={handleSearch}
            disabled={loading}
            style={{ background: 'var(--stamp-gold)', color: 'var(--ink-900)', padding: '11px 24px', fontSize: '14px', fontWeight: 700 }}
          >
            {loading ? 'Searching…' : 'Search'}
          </button>

          <button
            onClick={() => {
              setQuery('');
              setCategory('');
              setSource('');
              setMinPrice('');
              setMaxPrice('');
              setResults([]);
            }}
            style={{ padding: '11px 24px', fontSize: '14px', fontWeight: 600 }}
          >
            Clear
          </button>
        </div>
      </Card>

      {/* Results */}
      {results.length > 0 && (
        <Card>
          <h2 style={{ fontSize: 13, fontFamily: 'var(--font-mono)', letterSpacing: '0.06em', textTransform: 'uppercase', marginBottom: 18, color: 'var(--muted)' }}>
            Found {results.length} items ({Object.keys(groupedResults).length} unique)
          </h2>

          <div style={{ display: 'flex', flexDirection: 'column', gap: '16px' }}>
            {Object.entries(groupedResults).map(([name, items]) => {
              const sortedItems = [...items].sort((a, b) => a.price - b.price);
              const minPriceItem = sortedItems[0];
              const maxPriceItem = sortedItems[sortedItems.length - 1];
              const avgPrice = items.reduce((sum, i) => sum + i.price, 0) / items.length;

              return (
                <div
                  key={name}
                  style={{
                    border: '1px solid var(--ink-700)',
                    borderRadius: '10px',
                    padding: '16px',
                    background: 'var(--ink-800)',
                  }}
                >
                  <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'start', marginBottom: '12px' }}>
                    <div style={{ flex: 1 }}>
                      <Link to={`/items/${encodeURIComponent(name)}`} style={{ fontSize: '16px', fontWeight: 700, color: 'var(--stamp-teal)' }}>
                        {name}
                      </Link>
                      <p style={{ margin: '5px 0', fontSize: '13px', color: 'var(--muted)' }}>
                        Category: {items[0].category || 'Unknown'}
                      </p>
                    </div>
                    <span style={{
                      background: 'rgba(200, 155, 60, 0.15)',
                      color: 'var(--stamp-gold)',
                      padding: '4px 12px',
                      borderRadius: '12px',
                      fontSize: '13px',
                      fontWeight: 600,
                      whiteSpace: 'nowrap',
                    }}>
                      {items.length} purchase{items.length > 1 ? 's' : ''}
                    </span>
                  </div>

                  {/* Price Comparison */}
                  {items.length > 1 ? (
                    <div style={{ background: 'var(--ink-900)', padding: '12px', borderRadius: '8px', marginBottom: '12px', border: '1px solid var(--ink-700)' }}>
                      <h4 style={{ margin: '0 0 10px 0', fontSize: '12px', fontFamily: 'var(--font-mono)', textTransform: 'uppercase', letterSpacing: '0.05em', color: 'var(--muted)' }}>
                        Price comparison
                      </h4>
                      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: '10px' }}>
                        <div>
                          <span style={{ fontSize: '11px', color: 'var(--muted)' }}>Lowest</span>
                          <p style={{ margin: '2px 0 0 0', fontSize: '16px', fontWeight: 700, fontFamily: 'var(--font-mono)', color: 'var(--success)' }}>
                            ${minPriceItem.price.toFixed(2)}
                          </p>
                          <span style={{ fontSize: '11px', color: 'var(--muted)' }}>{minPriceItem.source}</span>
                        </div>
                        <div>
                          <span style={{ fontSize: '11px', color: 'var(--muted)' }}>Average</span>
                          <p style={{ margin: '2px 0 0 0', fontSize: '16px', fontWeight: 700, fontFamily: 'var(--font-mono)', color: 'var(--paper)' }}>
                            ${avgPrice.toFixed(2)}
                          </p>
                        </div>
                        <div>
                          <span style={{ fontSize: '11px', color: 'var(--muted)' }}>Highest</span>
                          <p style={{ margin: '2px 0 0 0', fontSize: '16px', fontWeight: 700, fontFamily: 'var(--font-mono)', color: 'var(--danger)' }}>
                            ${maxPriceItem.price.toFixed(2)}
                          </p>
                          <span style={{ fontSize: '11px', color: 'var(--muted)' }}>{maxPriceItem.source}</span>
                        </div>
                      </div>
                    </div>
                  ) : (
                    <div style={{ marginBottom: '12px' }}>
                      <span style={{ fontSize: '22px', fontWeight: 700, fontFamily: 'var(--font-mono)', color: 'var(--stamp-gold)' }}>
                        ${items[0].price.toFixed(2)}
                      </span>
                      <span style={{ fontSize: '13px', color: 'var(--muted)', marginLeft: '10px' }}>
                        from {items[0].source}
                      </span>
                    </div>
                  )}

                  {/* Purchase History */}
                  <details style={{ cursor: 'pointer' }}>
                    <summary style={{ fontSize: '13px', fontWeight: 600, color: 'var(--stamp-teal)', padding: '6px 0' }}>
                      View purchase history
                    </summary>
                    <div style={{ marginTop: '10px' }}>
                      <table style={{ width: '100%', fontSize: '13px' }}>
                        <thead>
                          <tr style={{ borderBottom: '1px solid var(--ink-700)' }}>
                            <th style={{ padding: '8px', textAlign: 'left', color: 'var(--muted)', fontSize: 11, fontFamily: 'var(--font-mono)', textTransform: 'uppercase' }}>Date</th>
                            <th style={{ padding: '8px', textAlign: 'left', color: 'var(--muted)', fontSize: 11, fontFamily: 'var(--font-mono)', textTransform: 'uppercase' }}>Source</th>
                            <th style={{ padding: '8px', textAlign: 'right', color: 'var(--muted)', fontSize: 11, fontFamily: 'var(--font-mono)', textTransform: 'uppercase' }}>Price</th>
                            <th style={{ padding: '8px', textAlign: 'center', color: 'var(--muted)', fontSize: 11, fontFamily: 'var(--font-mono)', textTransform: 'uppercase' }}>Qty</th>
                          </tr>
                        </thead>
                        <tbody>
                          {sortedItems.map((item, idx) => (
                            <tr key={idx} style={{ borderBottom: '1px solid var(--ink-700)' }}>
                              <td style={{ padding: '8px', fontFamily: 'var(--font-mono)', color: 'var(--paper-dim)' }}>{item.date}</td>
                              <td style={{ padding: '8px', color: 'var(--paper-dim)' }}>{item.source}</td>
                              <td style={{ padding: '8px', textAlign: 'right', fontWeight: 600, fontFamily: 'var(--font-mono)', color: 'var(--paper)' }}>
                                ${item.price.toFixed(2)}
                              </td>
                              <td style={{ padding: '8px', textAlign: 'center', color: 'var(--paper-dim)' }}>{item.quantity}</td>
                            </tr>
                          ))}
                        </tbody>
                      </table>
                    </div>
                  </details>
                </div>
              );
            })}
          </div>
        </Card>
      )}

      {results.length === 0 && !loading && (
        <Card style={{ textAlign: 'center', padding: 40 }}>
          <p style={{ margin: 0, fontSize: '14px', color: 'var(--muted)' }}>
            {query || category || source || minPrice || maxPrice
              ? 'No items found. Try adjusting your search filters.'
              : 'Enter search criteria above to find items.'}
          </p>
        </Card>
      )}
    </div>
  );
};

export default Search;
