export type Run = {
  id: string;
  connector: string;
  status: string;
  created_at: string;
  queued: number;
  running: number;
  retrying: number;
  succeeded: number;
  failed: number;
  blocked: number;
};

export type Product = {
  id: string;
  title: string;
  source: string;
  price_amount: string;
  currency: string;
  availability: string;
  confidence: number;
  dom_fingerprint: string;
};

export const replayRuns: Run[] = [
  {
    id: "run-chaos-1000",
    connector: "fixture_chaos",
    status: "succeeded",
    created_at: "2026-08-27T09:30:00+09:00",
    queued: 0,
    running: 0,
    retrying: 0,
    succeeded: 1000,
    failed: 0,
    blocked: 0,
  },
  {
    id: "run-books-20",
    connector: "books_to_scrape",
    status: "succeeded",
    created_at: "2026-08-27T09:42:00+09:00",
    queued: 0,
    running: 0,
    retrying: 0,
    succeeded: 20,
    failed: 0,
    blocked: 0,
  },
  {
    id: "run-drift-holdout",
    connector: "fixture_drift",
    status: "succeeded",
    created_at: "2026-08-27T09:48:00+09:00",
    queued: 0,
    running: 0,
    retrying: 0,
    succeeded: 2,
    failed: 0,
    blocked: 0,
  },
];

export const replayProducts: Product[] = [
  {
    id: "p-001",
    title: "Reliable Product 42",
    source: "fixture_chaos",
    price_amount: "52.90",
    currency: "USD",
    availability: "InStock",
    confidence: 0.992,
    dom_fingerprint: "2a41c9fdf1b71521",
  },
  {
    id: "p-002",
    title: "The Lean Startup",
    source: "books_to_scrape",
    price_amount: "33.92",
    currency: "GBP",
    availability: "In stock (3 available)",
    confidence: 0.973,
    dom_fingerprint: "813c1ce9fd4e6014",
  },
  {
    id: "p-003",
    title: "Redesigned Product 91",
    source: "fixture_drift",
    price_amount: "21.90",
    currency: "USD",
    availability: "InStock",
    confidence: 0.835,
    dom_fingerprint: "91d34c10af054d72",
  },
  {
    id: "p-004",
    title: "Recovered Product 117",
    source: "fixture_chaos",
    price_amount: "19.90",
    currency: "USD",
    availability: "InStock",
    confidence: 0.989,
    dom_fingerprint: "2a41c9fdf1b71521",
  },
];

export const replayTimeline = [
  { time: "09:30:00", event: "Run accepted", detail: "1,000 targets written with idempotency keys" },
  { time: "09:30:02", event: "Rate limit observed", detail: "83 responses returned 429 · Retry-After honored" },
  { time: "09:30:07", event: "Worker reclaimed", detail: "17 stale messages recovered after simulated crash" },
  { time: "09:30:13", event: "Schema drift", detail: "DOM fingerprint changed · 1 record sent to review" },
  { time: "09:30:21", event: "Run complete", detail: "1,000 terminal targets · 0 lost · 0 duplicate" },
];
