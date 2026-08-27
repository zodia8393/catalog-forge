import recordedDataset from "../public/sample-products.json";

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
  review_required: boolean;
};

const connectorLabels: Record<string, string> = {
  fixture_chaos: "장애 복구 테스트",
  books_to_scrape: "Books to Scrape",
  fixture_drift: "구조 변경 테스트",
};

const statusLabels: Record<string, string> = {
  queued: "대기",
  running: "처리 중",
  retrying: "재시도",
  succeeded: "완료",
  failed: "실패",
  blocked: "차단",
};

const availabilityLabels: Record<string, string> = {
  InStock: "재고 있음",
  "In stock (3 available)": "재고 있음 (3개)",
  "In stock (22 available)": "재고 있음 (22개)",
};

export function displayConnector(connector: string) {
  return connectorLabels[connector] ?? connector;
}

export function displayStatus(status: string) {
  return statusLabels[status] ?? status;
}

export function displayAvailability(availability: string) {
  return availabilityLabels[availability] ?? availability;
}

export const recordedAt = new Intl.DateTimeFormat("ko-KR", {
  dateStyle: "medium",
  timeStyle: "medium",
  timeZone: "Asia/Seoul",
}).format(new Date(recordedDataset.generated_at));
export const recordedCommand = recordedDataset.generator_command;
export const recordedMetrics = recordedDataset.metrics;
export const recordedSources = recordedDataset.sources;
export const replayRuns: Run[] = recordedDataset.runs;
export const replayProducts: Product[] = recordedDataset.products;
export const replayTimeline = recordedDataset.timeline;
