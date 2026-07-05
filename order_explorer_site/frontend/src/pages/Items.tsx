import React, { useEffect, useState, useMemo, useCallback } from 'react';
import axios from 'axios';
import { fetchItems, fetchAllCategories, updateItemCategory } from '../api';
import type { Item } from '../api';
import { Link, useSearchParams } from 'react-router-dom';
import PageHeader from '../components/ui/PageHeader';
import Card from '../components/ui/Card';
import Badge from '../components/ui/Badge';
import Spinner from '../components/ui/Spinner';
import Input from '../components/ui/form/Input';
import ResponsiveTable from '../components/ui/ResponsiveTable';
import type { TableColumn } from '../components/ui/ResponsiveTable';

type SortField = 'date' | 'name' | 'price' | 'quantity' | 'source' | 'category';
type SortDirection = 'asc' | 'desc';

const SORT_FIELDS: { field: SortField; label: string }[] = [
  { field: 'date', label: 'Date' },
  { field: 'name', label: 'Name' },
  { field: 'price', label: 'Price' },
  { field: 'quantity', label: 'Qty' },
  { field: 'category', label: 'Category' },
  { field: 'source', label: 'Source' },
];

// Each row pairs the item with its index in the current (filtered/sorted/paginated)
// page so the category-editing UI can address a specific row even when names repeat.
interface IndexedItem {
  item: Item;
  key: string;
}

const StatCard: React.FC<{ label: string; value: string; sub?: string }> = ({ label, value, sub }) => (
  <Card>
    <div className="mb-2.5 font-mono text-[11px] uppercase tracking-wider text-muted">{label}</div>
    <div className="font-mono text-2xl font-bold text-alert-amber">{value}</div>
    {sub && <div className="mt-1 text-xs text-muted">{sub}</div>}
  </Card>
);

const pageBtnClass = (active: boolean, disabled: boolean): string =>
  `min-w-[38px] rounded-md px-3 py-1.5 text-sm font-semibold ${
    disabled ? 'bg-surface-dim text-muted' : active ? 'bg-alert-amber text-white' : 'bg-surface-dim text-ink-dim'
  }`;

const Items: React.FC = () => {
  const [searchParams, setSearchParams] = useSearchParams();
  const [items, setItems] = useState<Item[]>([]);
  const [loading, setLoading] = useState(true);
  const [filter, setFilter] = useState('');
  const [debouncedFilter, setDebouncedFilter] = useState('');
  const [sortField, setSortField] = useState<SortField>('date');
  const [sortDirection, setSortDirection] = useState<SortDirection>('desc');
  const [availableCategories, setAvailableCategories] = useState<string[]>([]);
  const [editingKey, setEditingKey] = useState<string | null>(null);
  const [tempCategory, setTempCategory] = useState<string>('');
  const [updating, setUpdating] = useState(false);

  const ITEMS_PER_PAGE = 100;
  const currentPage = parseInt(searchParams.get('page') || '1', 10);

  useEffect(() => {
    fetchItems().then(data => {
      setItems(data);
      setLoading(false);
    });
    fetchAllCategories().then(categories => {
      setAvailableCategories(categories);
    });
  }, []);

  // Debounce filter input
  useEffect(() => {
    const timer = setTimeout(() => {
      setDebouncedFilter(filter);
      if (currentPage !== 1) {
        setSearchParams({ page: '1' });
      }
    }, 300);
    return () => clearTimeout(timer);
  }, [filter, currentPage, setSearchParams]);

  const setPage = useCallback((page: number) => {
    setSearchParams({ page: page.toString() });
    window.scrollTo({ top: 0, behavior: 'smooth' });
  }, [setSearchParams]);

  const handleEditCategory = useCallback((key: string, currentCategory: string) => {
    setEditingKey(key);
    setTempCategory(currentCategory || '');
  }, []);

  const handleCancelEdit = useCallback(() => {
    setEditingKey(null);
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
      setItems(prevItems =>
        prevItems.map(i =>
          i.name === item.name ? { ...i, category: tempCategory } : i
        )
      );
      handleCancelEdit();
      alert(`Category updated to "${tempCategory}" for all instances of this item`);
    } catch (error) {
      console.error('Failed to update category:', error);
      const detail = axios.isAxiosError(error) ? error.response?.data?.detail : undefined;
      alert(`Failed to update category: ${detail || (error instanceof Error ? error.message : String(error))}`);
    } finally {
      setUpdating(false);
    }
  }, [tempCategory, handleCancelEdit]);

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

  const { monthSpending, yearSpending, allTimeSpending, monthItemsCount, yearItemsCount } = useMemo(() => {
    const now = new Date();
    const currentMonth = `${now.getFullYear()}-${String(now.getMonth() + 1).padStart(2, '0')}`;
    const currentYear = `${now.getFullYear()}`;

    const monthItems = items.filter(item => item.date?.startsWith(currentMonth));
    const yearItems = items.filter(item => item.date?.startsWith(currentYear));

    return {
      monthSpending: monthItems.reduce((sum, item) => sum + (item.total_price || 0), 0),
      yearSpending: yearItems.reduce((sum, item) => sum + (item.total_price || 0), 0),
      allTimeSpending: items.reduce((sum, item) => sum + (item.total_price || 0), 0),
      monthItemsCount: monthItems.length,
      yearItemsCount: yearItems.length
    };
  }, [items]);

  const { sortedItems, totalFilteredCount, totalPages } = useMemo(() => {
    const filteredItems = items.filter(item =>
      item.name && item.name.toLowerCase().includes(debouncedFilter.toLowerCase())
    );

    const sorted = [...filteredItems].sort((a, b) => {
      let comparison = 0;
      if (sortField === 'date') {
        comparison = (a.date || '').localeCompare(b.date || '');
      } else if (sortField === 'name') {
        comparison = (a.name || '').localeCompare(b.name || '');
      } else if (sortField === 'price') {
        comparison = (a.price || 0) - (b.price || 0);
      } else if (sortField === 'quantity') {
        comparison = (a.quantity || 0) - (b.quantity || 0);
      } else if (sortField === 'source') {
        comparison = (a.source || '').localeCompare(b.source || '');
      } else if (sortField === 'category') {
        comparison = (a.category || '').localeCompare(b.category || '');
      }
      return sortDirection === 'asc' ? comparison : -comparison;
    });

    const totalPages = Math.ceil(sorted.length / ITEMS_PER_PAGE);
    const startIdx = (currentPage - 1) * ITEMS_PER_PAGE;
    const endIdx = startIdx + ITEMS_PER_PAGE;
    const paginatedItems = sorted.slice(startIdx, endIdx);

    return {
      sortedItems: paginatedItems,
      totalFilteredCount: sorted.length,
      totalPages
    };
  }, [items, debouncedFilter, sortField, sortDirection, currentPage, ITEMS_PER_PAGE]);

  const indexedItems: IndexedItem[] = useMemo(
    () => sortedItems.map((item, idx) => ({ item, key: `${item.name}-${item.date}-${idx}` })),
    [sortedItems]
  );

  if (loading) {
    return (
      <div className="mx-auto max-w-[1200px] px-4 py-6 md:px-6">
        <Spinner label="Loading items…" />
      </div>
    );
  }

  const columns: TableColumn<IndexedItem>[] = [
    {
      key: 'date',
      header: 'Date',
      render: ({ item }) => <span className="font-mono">{item.date}</span>,
    },
    {
      key: 'name',
      header: 'Item name',
      primary: true,
      render: ({ item }) => (
        <Link to={`/items/${encodeURIComponent(item.name || '')}`} className="font-medium text-signal hover:underline">
          {item.name || 'Unknown'}
        </Link>
      ),
    },
    {
      key: 'price',
      header: 'Price',
      className: 'text-right',
      render: ({ item }) => <span className="font-mono font-semibold text-ink">${item.price?.toFixed(2)}</span>,
    },
    {
      key: 'quantity',
      header: 'Qty',
      className: 'text-center',
      render: ({ item }) => <Badge tone="gold">{item.quantity}</Badge>,
    },
    {
      key: 'category',
      header: 'Category',
      render: ({ item, key }) => {
        const isEditing = editingKey === key;
        if (isEditing) {
          return (
            <div className="flex items-center gap-2">
              <div className="relative flex-1">
                <input
                  type="text"
                  list={`categories-${key}`}
                  value={tempCategory}
                  onChange={(e) => setTempCategory(e.target.value)}
                  disabled={updating}
                  placeholder="Type or select category"
                  className="w-full rounded-md border border-line bg-surface px-2 py-1.5 text-sm text-ink outline-none focus:border-signal"
                />
                <datalist id={`categories-${key}`}>
                  {availableCategories.map(cat => (
                    <option key={cat} value={cat} />
                  ))}
                </datalist>
              </div>
              <button
                type="button"
                onClick={() => handleSaveCategory(item)}
                disabled={updating || !tempCategory.trim()}
                className="rounded-md bg-alert-green px-3 py-1.5 text-xs font-semibold text-white"
              >
                {updating ? '…' : '✓'}
              </button>
              <button
                type="button"
                onClick={handleCancelEdit}
                disabled={updating}
                className="rounded-md bg-alert-red px-3 py-1.5 text-xs font-semibold text-white"
              >
                ✕
              </button>
            </div>
          );
        }
        return (
          <button
            type="button"
            onClick={() => handleEditCategory(key, item.category || '')}
            className="inline-flex items-center rounded-full bg-alert-red/15 px-2.5 py-1 text-xs font-semibold text-alert-red"
          >
            {item.category || 'Uncategorized'} ✎
          </button>
        );
      },
    },
    {
      key: 'source',
      header: 'Source',
      render: ({ item }) => <Badge tone="neutral">{item.source}</Badge>,
    },
  ];

  return (
    <div className="mx-auto max-w-[1200px] px-4 py-6 md:px-6">
      <PageHeader eyebrow="Ledger / Items" title="Items" />

      <div className="mb-7 grid grid-cols-2 gap-4 sm:grid-cols-4">
        <StatCard label="This month" value={`$${monthSpending.toFixed(2)}`} sub={`${monthItemsCount} items`} />
        <StatCard label="This year" value={`$${yearSpending.toFixed(2)}`} sub={`${yearItemsCount} items`} />
        <StatCard label="All time" value={`$${allTimeSpending.toFixed(2)}`} sub={`${items.length} items`} />
        <StatCard label="Avg item price" value={`$${items.length > 0 ? (allTimeSpending / items.length).toFixed(2) : '0.00'}`} />
      </div>

      <Card>
        <Input
          type="text"
          placeholder="Search items…"
          value={filter}
          onChange={e => setFilter(e.target.value)}
          className="mb-5 max-w-[380px]"
        />

        <div className="mb-4 flex flex-wrap items-center gap-2">
          <span className="font-mono text-[11px] uppercase tracking-wider text-muted">Sort</span>
          {SORT_FIELDS.map(({ field, label }) => (
            <button
              key={field}
              type="button"
              onClick={() => handleSort(field)}
              className={`rounded-md px-3 py-1.5 text-xs font-semibold ${
                sortField === field ? 'bg-signal text-white' : 'bg-surface-dim text-muted'
              }`}
            >
              {label} {sortField === field ? (sortDirection === 'asc' ? '↑' : '↓') : ''}
            </button>
          ))}
        </div>

        <ResponsiveTable
          columns={columns}
          rows={indexedItems}
          rowKey={(r) => r.key}
          emptyTitle="No items found"
          emptyDescription={debouncedFilter ? 'Try a different search term.' : undefined}
        />

        {/* Pagination Controls */}
        <div className="mt-5 flex flex-col items-center gap-3.5">
          <p className="m-0 text-sm text-muted">
            Showing {((currentPage - 1) * ITEMS_PER_PAGE) + 1}-{Math.min(currentPage * ITEMS_PER_PAGE, totalFilteredCount)} of {totalFilteredCount} items
            {debouncedFilter && ` (filtered from ${items.length} total)`}
          </p>

          {totalPages > 1 && (
            <div className="flex flex-wrap items-center justify-center gap-2">
              <button onClick={() => setPage(1)} disabled={currentPage === 1} className={pageBtnClass(false, currentPage === 1)}>« First</button>
              <button onClick={() => setPage(currentPage - 1)} disabled={currentPage === 1} className={pageBtnClass(false, currentPage === 1)}>‹ Prev</button>

              {Array.from({ length: Math.min(totalPages, 7) }, (_, i) => {
                let pageNum;
                if (totalPages <= 7) {
                  pageNum = i + 1;
                } else if (currentPage <= 4) {
                  pageNum = i + 1;
                } else if (currentPage >= totalPages - 3) {
                  pageNum = totalPages - 6 + i;
                } else {
                  pageNum = currentPage - 3 + i;
                }

                return (
                  <button
                    key={pageNum}
                    onClick={() => setPage(pageNum)}
                    className={pageBtnClass(currentPage === pageNum, false)}
                  >
                    {pageNum}
                  </button>
                );
              })}

              <button onClick={() => setPage(currentPage + 1)} disabled={currentPage === totalPages} className={pageBtnClass(false, currentPage === totalPages)}>Next ›</button>
              <button onClick={() => setPage(totalPages)} disabled={currentPage === totalPages} className={pageBtnClass(false, currentPage === totalPages)}>Last »</button>
            </div>
          )}
        </div>
      </Card>
    </div>
  );
};

export default Items;
