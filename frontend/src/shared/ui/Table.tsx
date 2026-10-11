// Плотная таблица (IBM Carbon): строка 40 px, на телефоне — список карточек «подпись — значение».
import type { KeyboardEvent, ReactNode } from "react";

import styles from "./Table.module.css";

export interface Column<T> {
  key: string;
  header: string;
  render: (row: T) => ReactNode;
  align?: "start" | "end";
  /** Колонка-заголовок строки: на телефоне идёт первой и без подписи. */
  primary?: boolean;
}

interface TableProps<T> {
  caption: string;
  columns: readonly Column<T>[];
  rows: readonly T[];
  rowKey: (row: T) => string;
  onRowClick?: (row: T) => void;
  selectedKey?: string | null;
}

export function Table<T>({ caption, columns, rows, rowKey, onRowClick, selectedKey }: TableProps<T>) {
  const onKeyDown = (event: KeyboardEvent<HTMLTableRowElement>, row: T) => {
    if (onRowClick && (event.key === "Enter" || event.key === " ")) {
      event.preventDefault();
      onRowClick(row);
    }
  };
  return (
    <div className={styles.scroll}>
      <table className={styles.table}>
        <caption className="visually-hidden">{caption}</caption>
        <thead>
          <tr>
            {columns.map((column) => (
              <th key={column.key} scope="col" className={column.align === "end" ? styles.end : undefined}>
                {column.header}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {rows.map((row) => {
            const key = rowKey(row);
            return (
              <tr
                key={key}
                className={[
                  onRowClick ? styles.clickable : "",
                  key === selectedKey ? styles.selected : "",
                ].join(" ")}
                tabIndex={onRowClick ? 0 : undefined}
                aria-selected={onRowClick ? key === selectedKey : undefined}
                onClick={
                  onRowClick
                    ? () => {
                        onRowClick(row);
                      }
                    : undefined
                }
                onKeyDown={
                  onRowClick
                    ? (event) => {
                        onKeyDown(event, row);
                      }
                    : undefined
                }
              >
                {columns.map((column) => (
                  <td
                    key={column.key}
                    data-label={column.primary ? undefined : column.header}
                    className={[
                      column.align === "end" ? styles.end : "",
                      column.primary ? styles.primary : "",
                    ].join(" ")}
                  >
                    {column.render(row)}
                  </td>
                ))}
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}
