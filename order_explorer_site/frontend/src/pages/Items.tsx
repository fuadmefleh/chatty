import React, { useEffect, useState, useMemo, useCallback } from 'react';
import { fetchItems, fetchAllCategories, updateItemCategory } from '../api';
import type { Item } from '../api';
import { Link, useSearchParams } from 'react-router-dom';
import PageHeader from '../components/ui/PageHeader';
import Card from '../components/ui/Card';

type SortField = 'date' | 'name' | 'price' | 'quantity' | 'source' | 'category';
type SortDirection = 'asc' | 'desc';

const ROW_EVEN = 'var(--ink-800)';
const ROW_ODD = 'var(--ink-900)';
const ROW_HOVER = 'var(--ink-750)';

interface ItemRowProps {
  item: Item;
  idx: number;
  isEditing: boolean;
  tempCategory: string;
  availableCategories: string[];
  updating: boolean;
  onEditCategory: (index: number, category: string) => void;
  onSaveCategory: (item: Item) => void;
  onCancelEdit: () => void;
  onTempCategoryChange: (value: string) => void;
}

const ItemRow = React.memo<ItemRowProps>(({ item, idx, isEditing, tempCategory, availableCategories, updating, onEditCategory, onSaveCategory, onCancelEdit, onTempCategoryChange }) => {
  const [isHovered, setIsHovered] = useState(false);

  return (
    <tr
      style={{
        backgroundColor: isHovered ? ROW_HOVER : (idx % 2 === 0 ? ROW_EVEN : ROW_ODD),
        transition: 'background-color 0.15s'
      }}
      onMouseEnter={() => setIsHovered(true)}
      onMouseLeave={() => setIsHovered(false)}
    >
      <td style={{ padding: '13px 14px', borderTop: '1px solid var(--ink-700)', fontFamily: 'var(--font-mono)', fontSize: 13, color: 'var(--paper)' }}>{item.date}</td>
      <td style={{ padding: '13px 14px', borderTop: '1px solid var(--ink-700)' }}>
        <Link
          to={`/items/${encodeURIComponent(item.name || '')}`}
          style={{
            color: 'var(--stamp-teal)',
            fontWeight: 500,
            borderBottom: '1px solid transparent',
          }}
          onMouseEnter={(e) => e.currentTarget.style.borderBottom = '1px solid var(--stamp-teal)'}
          onMouseLeave={(e) => e.currentTarget.style.borderBottom = '1px solid transparent'}
        >
          {item.name || 'Unknown'}
        </Link>
      </td>
      <td style={{ padding: '13px 14px', borderTop: '1px solid var(--ink-700)', textAlign: 'right', fontWeight: 600, fontFamily: 'var(--font-mono)', color: 'var(--paper)' }}>
        ${item.price?.toFixed(2)}
      </td>
      <td style={{ padding: '13px 14px', borderTop: '1px solid var(--ink-700)', textAlign: 'center' }}>
        <span style={{
          background: 'rgba(200, 155, 60, 0.15)',
          color: 'var(--stamp-gold)',
          padding: '3px 10px',
          borderRadius: 12,
          fontSize: 12,
          fontWeight: 600,
          fontFamily: 'var(--font-mono)',
        }}>
          {item.quantity}
        </span>
      </td>
      <td style={{ padding: '13px 14px', borderTop: '1px solid var(--ink-700)' }}>
        {isEditing ? (
          <div style={{ display: 'flex', gap: '8px', alignItems: 'center' }}>
            <div style={{ flex: 1, position: 'relative' }}>
              <input
                type="text"
                list={`categories-${idx}`}
                value={tempCategory}
                onChange={(e) => onTempCategoryChange(e.target.value)}
                disabled={updating}
                placeholder="Type or select category"
                style={{
                  padding: '6px 8px',
                  borderRadius: '4px',
                  fontSize: '13px',
                  width: '100%'
                }}
              />
              <datalist id={`categories-${idx}`}>
                {availableCategories.map(cat => (
                  <option key={cat} value={cat} />
                ))}
              </datalist>
            </div>
            <button
              onClick={() => onSaveCategory(item)}
              disabled={updating || !tempCategory.trim()}
              style={{
                background: 'var(--success)',
                color: 'var(--ink-900)',
                borderRadius: '4px',
                padding: '6px 12px',
                fontSize: '12px',
                fontWeight: '600',
              }}
            >
              {updating ? '…' : '✓'}
            </button>
            <button
              onClick={onCancelEdit}
              disabled={updating}
              style={{
                background: 'var(--danger)',
                color: 'var(--ink-900)',
                borderRadius: '4px',
                padding: '6px 12px',
                fontSize: '12px',
                fontWeight: '600',
              }}
            >
              ✕
            </button>
          </div>
        ) : (
          <span
            onClick={() => onEditCategory(idx, item.category || '')}
            style={{
              background: 'rgba(216, 96, 63, 0.15)',
              color: 'var(--stamp-ember)',
              padding: '4px 10px',
              borderRadius: '12px',
              fontSize: '12px',
              fontWeight: '600',
              cursor: 'pointer',
              display: 'inline-block',
            }}
          >
            {item.category || 'Uncategorized'} ✎
          </span>
        )}
      </td>
      <td style={{ padding: '13px 14px', borderTop: '1px solid var(--ink-700)' }}>
        <span style={{
          background: 'var(--ink-700)',
          color: 'var(--muted)',
          padding: '3px 10px',
          borderRadius: 12,
          fontSize: 12,
          fontWeight: 600
        }}>
          {item.source}
        </span>
      </td>
    </tr>
  );
}, (prevProps, nextProps) => {
  if (prevProps.isEditing !== nextProps.isEditing) return false;
  if (nextProps.isEditing && prevProps.tempCategory !== nextProps.tempCategory) return false;
  if (prevProps.updating !== nextProps.updating) return false;
  if (prevProps.item !== nextProps.item) return false;
  if (prevProps.availableCategories !== nextProps.availableCategories) return false;
  return true;
});

ItemRow.displayName = 'ItemRow';

const StatCard: React.FC<{ label: string; value: string; sub?: string }> = ({ label, value, sub }) => (
  <Card>
    <div style={{ fontSize: 11, fontFamily: 'var(--font-mono)', letterSpacing: '0.08em', textTransform: 'uppercase', color: 'var(--muted)', marginBottom: 10 }}>{label}</div>
    <div style={{ fontSize: 26, fontWeight: 700, fontFamily: 'var(--font-mono)', color: 'var(--stamp-gold)' }}>{value}</div>
    {sub && <div style={{ fontSize: 12, color: 'var(--muted)', marginTop: 4 }}>{sub}</div>}
  </Card>
);

const PAGE_BTN = (active: boolean, disabled: boolean): React.CSSProperties => ({
  background: disabled ? 'var(--ink-800)' : active ? 'var(--stamp-gold)' : 'var(--ink-700)',
  color: disabled ? 'var(--muted)' : active ? 'var(--ink-900)' : 'var(--paper)',
  borderRadius: '6px',
  padding: '7px 12px',
  fontSize: '13px',
  fontWeight: active ? 700 : 600,
  minWidth: '38px',
});

const Items: React.FC = () => {
  const [searchParams, setSearchParams] = useSearchParams();
  const [items, setItems] = useState<Item[]>([]);
  const [loading, setLoading] = useState(true);
  const [filter, setFilter] = useState('');
  const [debouncedFilter, setDebouncedFilter] = useState('');
  const [sortField, setSortField] = useState<SortField>('date');
  const [sortDirection, setSortDirection] = useState<SortDirection>('desc');
  const [availableCategories, setAvailableCategories] = useState<string[]>([]);
  const [editingRow, setEditingRow] = useState<number | null>(null);
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
      setItems(prevItems =>
        prevItems.map(i =>
          i.name === item.name ? { ...i, category: tempCategory } : i
        )
      );
      handleCancelEdit();
      alert(`Category updated to "${tempCategory}" for all instances of this item`);
    } catch (error: any) {
      console.error('Failed to update category:', error);
      alert(`Failed to update category: ${error.response?.data?.detail || error.message}`);
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

  const getSortIcon = useCallback((field: SortField) => {
    if (sortField !== field) return ' ⇅';
    return sortDirection === 'asc' ? ' ↑' : ' ↓';
  }, [sortField, sortDirection]);

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

  if (loading) return <div style={{ padding: 24, color: 'var(--muted)' }}>Loading items…</div>;

  return (
    <div style={{ padding: '24px 24px 48px' }}>
      <PageHeader eyebrow="Ledger / Items" title="Items" />

      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(190px, 1fr))', gap: '16px', marginBottom: '28px' }}>
        <StatCard label="This month" value={`$${monthSpending.toFixed(2)}`} sub={`${monthItemsCount} items`} />
        <StatCard label="This year" value={`$${yearSpending.toFixed(2)}`} sub={`${yearItemsCount} items`} />
        <StatCard label="All time" value={`$${allTimeSpending.toFixed(2)}`} sub={`${items.length} items`} />
        <StatCard label="Avg item price" value={`$${items.length > 0 ? (allTimeSpending / items.length).toFixed(2) : '0.00'}`} />
      </div>

      <Card>
        <input
          type="text"
          placeholder="Search items…"
          value={filter}
          onChange={e => setFilter(e.target.value)}
          style={{
            marginBottom: '20px',
            padding: '11px 16px',
            width: '100%',
            maxWidth: '380px',
            fontSize: '14px',
            borderRadius: '8px',
            outline: 'none',
          }}
        />
        <div style={{ overflowX: 'auto', border: '1px solid var(--ink-700)', borderRadius: '10px' }}>
          <table style={{ width: '100%', borderCollapse: 'collapse' }}>
            <thead>
              <tr style={{ background: 'var(--ink-750)' }}>
                <th onClick={() => handleSort('date')} style={thStyle('left')}>Date{getSortIcon('date')}</th>
                <th onClick={() => handleSort('name')} style={thStyle('left')}>Item name{getSortIcon('name')}</th>
                <th onClick={() => handleSort('price')} style={thStyle('right')}>Price{getSortIcon('price')}</th>
                <th onClick={() => handleSort('quantity')} style={thStyle('center')}>Qty{getSortIcon('quantity')}</th>
                <th onClick={() => handleSort('category')} style={thStyle('left')}>Category{getSortIcon('category')}</th>
                <th onClick={() => handleSort('source')} style={thStyle('left')}>Source{getSortIcon('source')}</th>
              </tr>
            </thead>
            <tbody>
              {sortedItems.map((item, idx) => (
                <ItemRow
                  key={`${item.name}-${item.date}-${idx}`}
                  item={item}
                  idx={idx}
                  isEditing={editingRow === idx}
                  tempCategory={tempCategory}
                  availableCategories={availableCategories}
                  updating={updating}
                  onEditCategory={handleEditCategory}
                  onSaveCategory={handleSaveCategory}
                  onCancelEdit={handleCancelEdit}
                  onTempCategoryChange={setTempCategory}
                />
              ))}
            </tbody>
          </table>
        </div>

        {/* Pagination Controls */}
        <div style={{ marginTop: '20px', display: 'flex', flexDirection: 'column', alignItems: 'center', gap: '14px' }}>
          <p style={{ color: 'var(--muted)', margin: 0, fontSize: 13 }}>
            Showing {((currentPage - 1) * ITEMS_PER_PAGE) + 1}-{Math.min(currentPage * ITEMS_PER_PAGE, totalFilteredCount)} of {totalFilteredCount} items
            {debouncedFilter && ` (filtered from ${items.length} total)`}
          </p>

          {totalPages > 1 && (
            <div style={{ display: 'flex', gap: '8px', alignItems: 'center', flexWrap: 'wrap', justifyContent: 'center' }}>
              <button onClick={() => setPage(1)} disabled={currentPage === 1} style={PAGE_BTN(false, currentPage === 1)}>« First</button>
              <button onClick={() => setPage(currentPage - 1)} disabled={currentPage === 1} style={PAGE_BTN(false, currentPage === 1)}>‹ Prev</button>

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
                    style={PAGE_BTN(currentPage === pageNum, false)}
                  >
                    {pageNum}
                  </button>
                );
              })}

              <button onClick={() => setPage(currentPage + 1)} disabled={currentPage === totalPages} style={PAGE_BTN(false, currentPage === totalPages)}>Next ›</button>
              <button onClick={() => setPage(totalPages)} disabled={currentPage === totalPages} style={PAGE_BTN(false, currentPage === totalPages)}>Last »</button>
            </div>
          )}
        </div>
      </Card>
    </div>
  );
};

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

export default Items;
