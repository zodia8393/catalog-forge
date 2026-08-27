# Data Contract

## ProductSnapshot

| Field | Required | Contract |
|---|:---:|---|
| `source`, `external_id`, `canonical_url` | Y | 원천과 상품 identity를 재현할 수 있어야 한다. |
| `title`, `price_amount`, `currency`, `availability` | Y | Required-field accuracy 평가 단위다. 누락 시 review 대상이다. |
| `brand`, `category`, `image_url` | N | 원문에 존재할 때만 저장하며 추정값을 만들지 않는다. |
| `confidence`, `field_evidence` | Y | field별 source와 selector를 포함한다. |
| `captured_at`, `dom_fingerprint` | Y | 시점 비교와 drift 추적에 사용한다. |

가격은 `Decimal`로 parsing한 뒤 DB에는 손실 없는 문자열로 저장한다. 통화는 ISO 4217 code를 사용한다. 원문 HTML은 v1에서 영구 저장하지 않아 개인정보와 저작물 보존 범위를 줄인다.

## 공개 데이터

- Local fixture는 프로젝트가 생성한 합성 commerce 문서다.
- 외부 connector는 scraping 학습용 sandbox인 `https://books.toscrape.com/`만 기본 allowlist에 둔다.
- 상용몰 URL, 로그인 정보, cookie, 개인 profile은 fixture·test·report에 넣지 않는다.
