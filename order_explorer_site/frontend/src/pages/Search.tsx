import React, { useState, useEffect } from 'react';
import { api } from '../api';
import { Link } from 'react-router-dom';
import PageHeader from '../components/ui/PageHeader';
import Card from '../components/ui/Card';
import Badge from '../components/ui/Badge';
import FormField from '../components/ui/form/FormField';
import Input from '../components/ui/form/Input';
import Select from '../components/ui/form/Select';

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
    <div className="mx-auto max-w-[1000px] px-4 py-6 md:px-6">
      <PageHeader eyebrow="Ledger / Search" title="Advanced search" />

      {/* Search Filters */}
      <Card className="mb-6">
        <div className="mb-4 grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3">
          <FormField label="Search term" htmlFor="search-term">
            <Input
              id="search-term"
              type="text"
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              placeholder="Enter item name…"
              onKeyDown={(e) => e.key === 'Enter' && handleSearch()}
            />
          </FormField>

          <FormField label="Category" htmlFor="search-category">
            <Select id="search-category" value={category} onChange={(e) => setCategory(e.target.value)}>
              <option value="">All categories</option>
              {categories.map(cat => (
                <option key={cat} value={cat}>{cat}</option>
              ))}
            </Select>
          </FormField>

          <FormField label="Source" htmlFor="search-source">
            <Select id="search-source" value={source} onChange={(e) => setSource(e.target.value)}>
              <option value="">All sources</option>
              {sources.map(src => (
                <option key={src} value={src}>{src}</option>
              ))}
            </Select>
          </FormField>

          <FormField label="Min price" htmlFor="search-min">
            <Input id="search-min" type="number" value={minPrice} onChange={(e) => setMinPrice(e.target.value)} placeholder="$0" step="0.01" />
          </FormField>

          <FormField label="Max price" htmlFor="search-max">
            <Input id="search-max" type="number" value={maxPrice} onChange={(e) => setMaxPrice(e.target.value)} placeholder="$999" step="0.01" />
          </FormField>
        </div>

        <div className="flex flex-col gap-2.5 sm:flex-row">
          <button
            onClick={handleSearch}
            disabled={loading}
            className="h-10 flex-1 rounded-lg bg-alert-amber px-6 text-sm font-semibold text-white disabled:opacity-55 sm:flex-none"
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
            className="h-10 flex-1 rounded-lg border border-line px-6 text-sm font-medium text-ink-dim sm:flex-none"
          >
            Clear
          </button>
        </div>
      </Card>

      {/* Results */}
      {results.length > 0 && (
        <Card>
          <h2 className="mb-4.5 font-mono text-[13px] uppercase tracking-wider text-muted">
            Found {results.length} items ({Object.keys(groupedResults).length} unique)
          </h2>

          <div className="flex flex-col gap-4">
            {Object.entries(groupedResults).map(([name, items]) => {
              const sortedItems = [...items].sort((a, b) => a.price - b.price);
              const minPriceItem = sortedItems[0];
              const maxPriceItem = sortedItems[sortedItems.length - 1];
              const avgPrice = items.reduce((sum, i) => sum + i.price, 0) / items.length;

              return (
                <div key={name} className="rounded-xl border border-line bg-surface p-4">
                  <div className="mb-3 flex items-start justify-between gap-3">
                    <div className="min-w-0 flex-1">
                      <Link to={`/items/${encodeURIComponent(name)}`} className="text-base font-bold text-signal">
                        {name}
                      </Link>
                      <p className="mt-1 text-sm text-muted">
                        Category: {items[0].category || 'Unknown'}
                      </p>
                    </div>
                    <Badge tone="gold">
                      {items.length} purchase{items.length > 1 ? 's' : ''}
                    </Badge>
                  </div>

                  {/* Price Comparison */}
                  {items.length > 1 ? (
                    <div className="mb-3 rounded-lg border border-line bg-surface-dim p-3">
                      <h4 className="mb-2.5 font-mono text-[11px] uppercase tracking-wider text-muted">
                        Price comparison
                      </h4>
                      <div className="grid grid-cols-3 gap-2.5">
                        <div>
                          <span className="text-[11px] text-muted">Lowest</span>
                          <p className="mt-0.5 font-mono text-base font-bold text-alert-green">
                            ${minPriceItem.price.toFixed(2)}
                          </p>
                          <span className="text-[11px] text-muted">{minPriceItem.source}</span>
                        </div>
                        <div>
                          <span className="text-[11px] text-muted">Average</span>
                          <p className="mt-0.5 font-mono text-base font-bold text-ink">
                            ${avgPrice.toFixed(2)}
                          </p>
                        </div>
                        <div>
                          <span className="text-[11px] text-muted">Highest</span>
                          <p className="mt-0.5 font-mono text-base font-bold text-alert-red">
                            ${maxPriceItem.price.toFixed(2)}
                          </p>
                          <span className="text-[11px] text-muted">{maxPriceItem.source}</span>
                        </div>
                      </div>
                    </div>
                  ) : (
                    <div className="mb-3">
                      <span className="font-mono text-xl font-bold text-alert-amber">
                        ${items[0].price.toFixed(2)}
                      </span>
                      <span className="ml-2.5 text-sm text-muted">
                        from {items[0].source}
                      </span>
                    </div>
                  )}

                  {/* Purchase History */}
                  <details className="cursor-pointer">
                    <summary className="py-1.5 text-sm font-semibold text-signal">
                      View purchase history
                    </summary>
                    <div className="mt-2.5 overflow-x-auto">
                      <table className="w-full text-sm">
                        <thead>
                          <tr className="border-b border-line">
                            <th className="px-2 py-2 text-left font-mono text-[11px] uppercase text-muted">Date</th>
                            <th className="px-2 py-2 text-left font-mono text-[11px] uppercase text-muted">Source</th>
                            <th className="px-2 py-2 text-right font-mono text-[11px] uppercase text-muted">Price</th>
                            <th className="px-2 py-2 text-center font-mono text-[11px] uppercase text-muted">Qty</th>
                          </tr>
                        </thead>
                        <tbody>
                          {sortedItems.map((item, idx) => (
                            <tr key={idx} className="border-b border-line">
                              <td className="px-2 py-2 font-mono text-ink-dim">{item.date}</td>
                              <td className="px-2 py-2 text-ink-dim">{item.source}</td>
                              <td className="px-2 py-2 text-right font-mono font-semibold text-ink">
                                ${item.price.toFixed(2)}
                              </td>
                              <td className="px-2 py-2 text-center text-ink-dim">{item.quantity}</td>
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
        <Card className="py-10 text-center">
          <p className="text-sm text-muted">
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
