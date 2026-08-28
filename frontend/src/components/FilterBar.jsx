import React from "react";
import { Button, Form } from "react-bootstrap";

/**
 * Shared filter strip: free-text search, any number of dropdowns, and a date range.
 *
 * Every list page had grown to the point where finding a specific record meant
 * scrolling the whole history, so the same three controls were needed everywhere.
 * Keeping them in one component means the pages stay consistent and a page only
 * declares which filters it actually has — a page with no date field simply omits
 * the date props and the range disappears.
 *
 * Purely presentational: filtering happens in the page against data it already
 * fetched, so nothing here changes an API call.
 */
export default function FilterBar({
  search,
  onSearch,
  searchPlaceholder = "Search…",
  selects = [],
  dateFrom,
  dateTo,
  onDateFrom,
  onDateTo,
  showing,
  total,
  onClear,
}) {
  const dateEnabled = typeof onDateFrom === "function" && typeof onDateTo === "function";
  const active =
    Boolean(search) ||
    selects.some((s) => s.value && s.value !== "all") ||
    Boolean(dateFrom) ||
    Boolean(dateTo);

  return (
    <div className="ms-filterbar mb-3">
      <div className="ms-filterbar-row">
        <Form.Control
          size="sm"
          className="ms-filter-search"
          placeholder={searchPlaceholder}
          value={search}
          onChange={(e) => onSearch(e.target.value)}
        />

        {selects.map((s) => (
          <Form.Select
            key={s.key}
            size="sm"
            className="ms-filter-select"
            value={s.value}
            onChange={(e) => s.onChange(e.target.value)}
            aria-label={s.label}
          >
            <option value="all">{s.label}: all</option>
            {s.options.map((o) => (
              <option key={o.value ?? o} value={o.value ?? o}>
                {o.label ?? String(o).replace(/_/g, " ")}
              </option>
            ))}
          </Form.Select>
        ))}

        {dateEnabled && (
          <div className="ms-filter-dates">
            <span className="ms-filter-datelabel">From</span>
            <Form.Control
              size="sm" type="date" value={dateFrom || ""}
              onChange={(e) => onDateFrom(e.target.value)}
            />
            <span className="ms-filter-datelabel">to</span>
            <Form.Control
              size="sm" type="date" value={dateTo || ""}
              onChange={(e) => onDateTo(e.target.value)}
            />
          </div>
        )}

        <div className="ms-filter-tail">
          <span className="ms-chip">
            {showing === total ? `${total}` : `${showing} of ${total}`}
          </span>
          {active && (
            <Button size="sm" variant="outline-dark" onClick={onClear}>
              Clear
            </Button>
          )}
        </div>
      </div>
    </div>
  );
}

/** Inclusive date-range test against an ISO timestamp. Shared so every page
 *  treats "to" the same way — as the end of that day, not midnight at its start,
 *  which would otherwise silently exclude everything recorded during the final day. */
export function withinRange(isoDate, from, to) {
  if (!from && !to) return true;
  const t = new Date(isoDate).getTime();
  if (Number.isNaN(t)) return true;
  if (from && t < new Date(`${from}T00:00:00`).getTime()) return false;
  if (to && t > new Date(`${to}T23:59:59.999`).getTime()) return false;
  return true;
}
