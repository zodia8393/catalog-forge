export type PreviewSource = "generic" | "books_to_scrape";

export type PreviewEvidence = {
  value: string;
  source: "json_ld" | "source_selector" | "semantic_fallback" | "derived";
  confidence: number;
  selector: string;
};

export type PreviewProduct = {
  mode: "preview_not_persisted";
  source: PreviewSource;
  external_id: string;
  canonical_url: string;
  title: string;
  price_amount: string | null;
  currency: string | null;
  availability: string | null;
  brand: string | null;
  category: string | null;
  image_url: string | null;
  confidence: number;
  required_field_coverage: number;
  dom_fingerprint: string;
  extraction_path: string[];
  review_required: boolean;
  review_reason: string | null;
};

export type PreviewResult = {
  product: PreviewProduct | null;
  evidence: Record<string, PreviewEvidence>;
  required_field_coverage: number;
  dom_fingerprint: string;
  warnings: string[];
  decision: {
    status: "eligible" | "review" | "rejected";
    label: string;
    reason: string;
  };
};

const REQUIRED_FIELDS = ["title", "price_amount", "currency", "availability"] as const;
const CURRENCY_SYMBOLS: Record<string, string> = { "$": "USD", "£": "GBP", "€": "EUR", "₩": "KRW" };
const PRICE_PATTERN = /([$£€₩])?\s*(\d[\d,]*(?:\.\d{1,2})?)/;

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}

function record(
  evidence: Record<string, PreviewEvidence>,
  field: string,
  rawValue: unknown,
  source: PreviewEvidence["source"],
  confidence: number,
  selector: string,
) {
  if (rawValue === null || rawValue === undefined || rawValue === "" || (Array.isArray(rawValue) && rawValue.length === 0)) return;
  evidence[field] = { value: String(rawValue), source, confidence, selector };
}

function text(node: Element | null) {
  const value = node?.textContent?.replace(/\s+/g, " ").trim();
  return value || null;
}

function attribute(node: Element | null, name: string) {
  const value = node?.getAttribute(name)?.trim();
  return value || null;
}

function parsePrice(value: unknown, currency?: string | null) {
  if (value === null || value === undefined) return { amount: null, currency: currency || null };
  const match = String(value).replace(/\u00a0/g, " ").match(PRICE_PATTERN);
  if (!match) return { amount: null, currency: currency || null };
  return {
    amount: match[2].replace(/,/g, ""),
    currency: currency || CURRENCY_SYMBOLS[match[1] || ""] || null,
  };
}

function availability(value: unknown) {
  if (value === null || value === undefined) return null;
  return String(value).split("/").at(-1)?.trim() || null;
}

function absoluteUrl(value: string | null, baseUrl: string) {
  if (!value) return baseUrl;
  try {
    return new URL(value, baseUrl).toString();
  } catch {
    return value;
  }
}

function brandName(value: unknown) {
  return isRecord(value) ? value.name : value;
}

function firstValue(value: unknown) {
  return Array.isArray(value) ? value[0] : value;
}

function productJsonLd(document: Document) {
  const candidates: unknown[] = [];
  for (const node of document.querySelectorAll('script[type="application/ld+json"]')) {
    try {
      const parsed: unknown = JSON.parse(node.textContent?.trim() || "null");
      candidates.push(...(Array.isArray(parsed) ? parsed : [parsed]));
    } catch {
      continue;
    }
  }
  for (let index = 0; index < candidates.length; index += 1) {
    const candidate = candidates[index];
    if (!isRecord(candidate)) continue;
    if (Array.isArray(candidate["@graph"])) candidates.push(...candidate["@graph"]);
    const rawType = candidate["@type"];
    const types = Array.isArray(rawType) ? rawType : [rawType];
    if (types.some(value => String(value).toLowerCase() === "product")) return candidate;
  }
  return null;
}

function parseJsonLd(document: Document, evidence: Record<string, PreviewEvidence>) {
  const product = productJsonLd(document);
  if (!product) return;
  const rawOffers = product.offers;
  const offersCandidate = Array.isArray(rawOffers) ? rawOffers[0] : rawOffers;
  const offers = isRecord(offersCandidate) ? offersCandidate : {};
  record(evidence, "title", product.name, "json_ld", .99, "$.name");
  record(evidence, "brand", brandName(product.brand), "json_ld", .98, "$.brand");
  record(evidence, "category", product.category, "json_ld", .98, "$.category");
  record(evidence, "image_url", firstValue(product.image), "json_ld", .98, "$.image");
  record(evidence, "external_id", product.sku || product.productID, "json_ld", .99, "$.sku");
  record(evidence, "availability", availability(offers.availability), "json_ld", .98, "$.offers.availability");
  const price = parsePrice(offers.price, offers.priceCurrency ? String(offers.priceCurrency) : null);
  record(evidence, "price_amount", price.amount, "json_ld", .99, "$.offers.price");
  record(evidence, "currency", price.currency, "json_ld", .99, "$.offers.priceCurrency");
}

function parseBooksSelector(document: Document, evidence: Record<string, PreviewEvidence>) {
  const table = new Map<string, string>();
  for (const row of document.querySelectorAll("table.table-striped tr")) {
    const key = text(row.querySelector("th"));
    const value = text(row.querySelector("td"));
    if (key && value) table.set(key, value);
  }
  record(evidence, "title", text(document.querySelector(".product_main h1")), "source_selector", .97, ".product_main h1");
  record(evidence, "external_id", table.get("UPC"), "source_selector", .99, "table:UPC");
  record(evidence, "category", table.get("Product Type"), "source_selector", .96, "table:Product Type");
  record(evidence, "availability", table.get("Availability") || text(document.querySelector(".availability")), "source_selector", .96, "table:Availability");
  const price = parsePrice(table.get("Price (incl. tax)") || text(document.querySelector(".price_color")));
  record(evidence, "price_amount", price.amount, "source_selector", .98, "table:Price (incl. tax)");
  record(evidence, "currency", price.currency, "source_selector", .98, "table:Price (incl. tax)");
  record(evidence, "image_url", attribute(document.querySelector(".item.active img"), "src"), "source_selector", .95, ".item.active img");
}

function parseSemanticFallback(document: Document, pageUrl: string, evidence: Record<string, PreviewEvidence>) {
  if (!evidence.title) {
    const openGraph = document.querySelector('meta[property="og:title"]');
    record(evidence, "title", attribute(openGraph, "content") || text(document.querySelector("h1")), "semantic_fallback", .86, "og:title|h1");
  }
  if (!evidence.image_url) {
    record(evidence, "image_url", attribute(document.querySelector('meta[property="og:image"]'), "content"), "semantic_fallback", .85, "og:image");
  }
  if (!evidence.price_amount) {
    const priceNode = document.querySelector('[itemprop="price"], meta[property="product:price:amount"], [data-price]');
    const priceValue = attribute(priceNode, "content") || attribute(priceNode, "data-price") || text(priceNode);
    const currencyNode = document.querySelector('[itemprop="priceCurrency"], meta[property="product:price:currency"]');
    const price = parsePrice(priceValue, attribute(currencyNode, "content"));
    record(evidence, "price_amount", price.amount, "semantic_fallback", .84, "itemprop=price");
    record(evidence, "currency", price.currency, "semantic_fallback", .84, "itemprop=priceCurrency");
  }
  if (!evidence.availability) {
    const node = document.querySelector('[itemprop="availability"], link[itemprop="availability"], [data-availability]');
    const value = attribute(node, "content") || attribute(node, "href") || attribute(node, "data-availability") || text(node);
    record(evidence, "availability", availability(value), "semantic_fallback", .82, "itemprop=availability");
  }
  if (!evidence.external_id) record(evidence, "external_id", pageUrl, "derived", .8, "canonical_url");
}

async function fingerprint(document: Document) {
  const counts = new Map<string, number>();
  for (const element of document.querySelectorAll("*")) {
    const classes = Array.from(element.classList).sort().slice(0, 3).join(".");
    const signature = classes ? `${element.tagName.toLowerCase()}.${classes}` : element.tagName.toLowerCase();
    counts.set(signature, (counts.get(signature) || 0) + 1);
  }
  const payload = Array.from(counts.entries()).sort(([left], [right]) => left.localeCompare(right)).map(([key, count]) => `${key}:${count}`).join("|");
  if (globalThis.crypto?.subtle) {
    const digest = await globalThis.crypto.subtle.digest("SHA-256", new TextEncoder().encode(payload));
    return Array.from(new Uint8Array(digest)).map(value => value.toString(16).padStart(2, "0")).join("").slice(0, 16);
  }
  let fallback = 2166136261;
  for (const character of payload) fallback = Math.imul(fallback ^ character.charCodeAt(0), 16777619);
  return Math.abs(fallback >>> 0).toString(16).padStart(16, "0").slice(0, 16);
}

export function validatePreviewUrl(value: string) {
  try {
    const parsed = new URL(value);
    return parsed.protocol === "http:" || parsed.protocol === "https:" ? null : "http 또는 https URL만 입력할 수 있습니다.";
  } catch {
    return "올바른 절대 URL을 입력해 주세요.";
  }
}

export async function parseProductPreview(html: string, pageUrl: string, source: PreviewSource): Promise<PreviewResult> {
  const document = new DOMParser().parseFromString(html, "text/html");
  const evidence: Record<string, PreviewEvidence> = {};
  parseJsonLd(document, evidence);
  if (source === "books_to_scrape") parseBooksSelector(document, evidence);
  parseSemanticFallback(document, pageUrl, evidence);

  const domFingerprint = await fingerprint(document);
  const coverage = REQUIRED_FIELDS.filter(field => evidence[field]).length / REQUIRED_FIELDS.length;
  const warnings = REQUIRED_FIELDS.filter(field => !evidence[field]).map(field => `missing_${field}`);
  const canonicalNode = document.querySelector('link[rel="canonical"]');
  const canonicalUrl = absoluteUrl(attribute(canonicalNode, "href"), pageUrl);
  const title = evidence.title?.value || "";

  if (!title) {
    return {
      product: null,
      evidence,
      required_field_coverage: coverage,
      dom_fingerprint: domFingerprint,
      warnings: ["missing_title", ...warnings.filter(value => value !== "missing_title")],
      decision: { status: "rejected", label: "상품으로 인식하지 못함", reason: "제목을 찾을 수 없어 product record를 만들지 않았습니다." },
    };
  }

  const confidence = Object.values(evidence).reduce((sum, item) => sum + item.confidence, 0) / Object.keys(evidence).length;
  const reviewReason = coverage < 1 ? "incomplete_required_fields" : confidence < .9 ? "low_confidence" : null;
  const extractionPath = Array.from(new Set(REQUIRED_FIELDS.map(field => evidence[field]?.source).filter((value): value is PreviewEvidence["source"] => Boolean(value))));
  const product: PreviewProduct = {
    mode: "preview_not_persisted",
    source,
    external_id: evidence.external_id?.value || canonicalUrl,
    canonical_url: canonicalUrl,
    title,
    price_amount: evidence.price_amount?.value || null,
    currency: evidence.currency?.value || null,
    availability: evidence.availability?.value || null,
    brand: evidence.brand?.value || null,
    category: evidence.category?.value || null,
    image_url: absoluteUrl(evidence.image_url?.value || null, pageUrl) || null,
    confidence: Math.round(confidence * 10_000) / 10_000,
    required_field_coverage: coverage,
    dom_fingerprint: domFingerprint,
    extraction_path: extractionPath,
    review_required: reviewReason !== null,
    review_reason: reviewReason,
  };
  const decision = reviewReason
    ? { status: "review" as const, label: "사람 검수 필요", reason: reviewReason === "low_confidence" ? "필수 필드는 복구했지만 confidence가 90% 미만입니다." : "필수 필드가 모두 채워지지 않았습니다." }
    : { status: "eligible" as const, label: "자동 저장 가능", reason: "필수 필드 4개와 confidence 기준을 통과했습니다. 이 체험에서는 DB에 저장하지 않습니다." };
  return { product, evidence, required_field_coverage: coverage, dom_fingerprint: domFingerprint, warnings, decision };
}
