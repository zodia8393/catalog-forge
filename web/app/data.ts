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
    confidence: 0.985,
    dom_fingerprint: "3fa5dc9e52eb63dd",
  },
  {
    id: "p-002",
    title: "A Light in the Attic",
    source: "books_to_scrape",
    price_amount: "51.77",
    currency: "GBP",
    availability: "In stock (22 available)",
    confidence: 0.97,
    dom_fingerprint: "69b715b335c5081b",
  },
  {
    id: "p-003",
    title: "Redesigned Product 91",
    source: "fixture_drift",
    price_amount: "21.90",
    currency: "USD",
    availability: "InStock",
    confidence: 0.832,
    dom_fingerprint: "18fdf70e66a429aa",
  },
  {
    id: "p-004",
    title: "Recovered Product 117",
    source: "fixture_chaos",
    price_amount: "19.90",
    currency: "USD",
    availability: "InStock",
    confidence: 0.985,
    dom_fingerprint: "3fa5dc9e52eb63dd",
  },
];

export const replayTimeline = [
  { time: "09:30:00", event: "수집 실행 접수", detail: "대상 1,000개를 중복 방지 키와 함께 저장" },
  { time: "09:30:02", event: "요청 제한 감지", detail: "429 응답 83건을 확인하고 Retry-After에 맞춰 재시도" },
  { time: "09:30:07", event: "중단 작업 회수", detail: "작업자 중단을 가정해 멈춘 메시지 17건을 다른 작업자가 처리" },
  { time: "09:30:13", event: "문서 구조 변경 감지", detail: "DOM fingerprint가 바뀐 상품 1건을 사람 검수로 분리" },
  { time: "09:30:21", event: "수집 실행 완료", detail: "1,000건 처리 완료 · 유실 0 · 중복 0" },
];
