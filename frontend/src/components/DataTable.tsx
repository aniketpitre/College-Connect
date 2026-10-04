import { useMemo, useState } from "react";
import { EmptyState } from "./EmptyState";

export interface Column<T> {
  key: string;
  header: string;
  render: (row: T) => React.ReactNode;
  /** Text used by the search box; omit to exclude the column from search. */
  searchText?: (row: T) => string;
  align?: "left" | "right";
}

interface Props<T> {
  columns: Column<T>[];
  rows: T[];
  rowKey: (row: T) => string;
  searchPlaceholder?: string;
  emptyTitle?: string;
  pageSize?: number;
}

/** Table with client-side search and paging, for the lists staff screens show. */
export function DataTable<T>({ columns, rows, rowKey, searchPlaceholder, emptyTitle = "Nothing to show", pageSize = 25 }: Props<T>) {
  const [query, setQuery] = useState("");
  const [page, setPage] = useState(0);
  const searchable = columns.filter((c) => c.searchText);

  const filtered = useMemo(() => {
    const q = query.trim().toLowerCase();
    if (!q) return rows;
    return rows.filter((r) => searchable.some((c) => c.searchText!(r).toLowerCase().includes(q)));
  }, [rows, query, searchable]);

  const pages = Math.max(1, Math.ceil(filtered.length / pageSize));
  const current = Math.min(page, pages - 1);
  const visible = filtered.slice(current * pageSize, (current + 1) * pageSize);

  return (
    <div className="data-table">
      {searchable.length > 0 && (
        <input
          className="data-table-search"
          type="search"
          value={query}
          placeholder={searchPlaceholder ?? "Search…"}
          aria-label={searchPlaceholder ?? "Search"}
          onChange={(e) => {
            setQuery(e.target.value);
            setPage(0);
          }}
        />
      )}
      {visible.length === 0 ? (
        <EmptyState title={emptyTitle} />
      ) : (
        <div className="data-table-scroll">
          <table>
            <thead>
              <tr>
                {columns.map((c) => (
                  <th key={c.key} className={c.align === "right" ? "num" : undefined}>
                    {c.header}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {visible.map((row) => (
                <tr key={rowKey(row)}>
                  {columns.map((c) => (
                    <td key={c.key} className={c.align === "right" ? "num" : undefined}>
                      {c.render(row)}
                    </td>
                  ))}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
      {pages > 1 && (
        <div className="data-table-pager">
          <button type="button" onClick={() => setPage(current - 1)} disabled={current === 0}>
            Previous
          </button>
          <span>
            Page {current + 1} of {pages} · {filtered.length} rows
          </span>
          <button type="button" onClick={() => setPage(current + 1)} disabled={current >= pages - 1}>
            Next
          </button>
        </div>
      )}
    </div>
  );
}
