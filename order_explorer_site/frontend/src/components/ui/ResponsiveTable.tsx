import { Fragment, useState } from 'react';
import type { ReactNode } from 'react';
import Card from './Card';
import EmptyState from './EmptyState';

export interface TableColumn<T> {
  key: string;
  header: string;
  render: (row: T) => ReactNode;
  /** Rendered as the mobile card's title line instead of a label:value row. */
  primary?: boolean;
  /** Extra classes for the desktop <td>/<th>, e.g. text alignment or width. */
  className?: string;
}

interface ResponsiveTableProps<T> {
  columns: TableColumn<T>[];
  rows: T[];
  rowKey: (row: T) => string | number;
  expandedContent?: (row: T) => ReactNode;
  emptyTitle?: string;
  emptyDescription?: string;
}

function ResponsiveTable<T>({
  columns,
  rows,
  rowKey,
  expandedContent,
  emptyTitle = 'Nothing here yet',
  emptyDescription,
}: ResponsiveTableProps<T>) {
  const [expanded, setExpanded] = useState<Set<string | number>>(new Set());

  const toggle = (key: string | number) => {
    setExpanded((current) => {
      const next = new Set(current);
      if (next.has(key)) next.delete(key);
      else next.add(key);
      return next;
    });
  };

  if (rows.length === 0) {
    return <EmptyState title={emptyTitle} description={emptyDescription} />;
  }

  const primaryColumn = columns.find((c) => c.primary) ?? columns[0];
  const secondaryColumns = columns.filter((c) => c !== primaryColumn);

  return (
    <>
      {/* Desktop / tablet: real table */}
      <div className="hidden overflow-x-auto rounded-xl border border-line md:block">
        <table className="w-full border-collapse text-sm">
          <thead>
            <tr className="border-b border-line bg-surface-dim">
              {expandedContent && <th className="w-9 px-2 py-2.5" />}
              {columns.map((col) => (
                <th
                  key={col.key}
                  className={`px-3 py-2.5 text-left font-mono text-[11px] uppercase tracking-wider text-muted ${col.className ?? ''}`}
                >
                  {col.header}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {rows.map((row) => {
              const key = rowKey(row);
              const isExpanded = expanded.has(key);
              return (
                <Fragment key={key}>
                  <tr className="border-b border-line last:border-b-0 hover:bg-surface-dim/60">
                    {expandedContent && (
                      <td className="px-2 py-2 text-center">
                        <button
                          type="button"
                          onClick={() => toggle(key)}
                          aria-expanded={isExpanded}
                          aria-label={isExpanded ? 'Collapse row' : 'Expand row'}
                          className="inline-flex h-6 w-6 items-center justify-center rounded-md p-0 text-muted hover:text-ink"
                        >
                          <svg
                            viewBox="0 0 24 24"
                            fill="none"
                            stroke="currentColor"
                            strokeWidth={2}
                            strokeLinecap="round"
                            strokeLinejoin="round"
                            className={`h-3.5 w-3.5 transition-transform ${isExpanded ? 'rotate-90' : ''}`}
                          >
                            <path d="m9 6 6 6-6 6" />
                          </svg>
                        </button>
                      </td>
                    )}
                    {columns.map((col) => (
                      <td key={col.key} className={`px-3 py-2.5 text-ink ${col.className ?? ''}`}>
                        {col.render(row)}
                      </td>
                    ))}
                  </tr>
                  {expandedContent && isExpanded && (
                    <tr className="border-b border-line bg-surface-dim/40 last:border-b-0">
                      <td colSpan={columns.length + 1} className="px-4 py-3">
                        {expandedContent(row)}
                      </td>
                    </tr>
                  )}
                </Fragment>
              );
            })}
          </tbody>
        </table>
      </div>

      {/* Mobile: stacked cards */}
      <div className="flex flex-col gap-2 md:hidden">
        {rows.map((row) => {
          const key = rowKey(row);
          const isExpanded = expanded.has(key);
          return (
            <Card key={key} padding="12px 14px">
              <button
                type="button"
                onClick={() => (expandedContent ? toggle(key) : undefined)}
                aria-expanded={expandedContent ? isExpanded : undefined}
                className={`flex w-full items-center justify-between gap-2 bg-transparent p-0 text-left font-medium text-ink ${
                  expandedContent ? '' : 'cursor-default'
                }`}
              >
                <span>{primaryColumn.render(row)}</span>
                {expandedContent && (
                  <svg
                    viewBox="0 0 24 24"
                    fill="none"
                    stroke="currentColor"
                    strokeWidth={2}
                    strokeLinecap="round"
                    strokeLinejoin="round"
                    className={`h-4 w-4 shrink-0 text-muted transition-transform ${isExpanded ? 'rotate-90' : ''}`}
                  >
                    <path d="m9 6 6 6-6 6" />
                  </svg>
                )}
              </button>
              <dl className="mt-2 flex flex-col gap-1">
                {secondaryColumns.map((col) => (
                  <div key={col.key} className="flex items-baseline justify-between gap-3 text-sm">
                    <dt className="text-muted">{col.header}</dt>
                    <dd className="text-right text-ink">{col.render(row)}</dd>
                  </div>
                ))}
              </dl>
              {expandedContent && isExpanded && (
                <div className="mt-3 border-t border-line pt-3">{expandedContent(row)}</div>
              )}
            </Card>
          );
        })}
      </div>
    </>
  );
}

export default ResponsiveTable;
