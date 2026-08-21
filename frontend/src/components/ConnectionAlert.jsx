import React from "react";
import { Alert, Button } from "react-bootstrap";

/**
 * Shown when a page cannot load its data. Exists so an unreachable backend is
 * distinguishable from an empty one — without it, both states render as "nothing here",
 * and the only way to tell them apart is to reload and see if anything changes.
 */
export default function ConnectionAlert({ error, onRetry }) {
  if (!error) return null;
  return (
    <Alert variant="warning" className="d-flex justify-content-between align-items-center py-2">
      <span className="small">{error}</span>
      {onRetry && (
        <Button size="sm" variant="outline-dark" onClick={onRetry}>
          Retry
        </Button>
      )}
    </Alert>
  );
}
