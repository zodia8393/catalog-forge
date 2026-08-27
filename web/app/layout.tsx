import type { Metadata, Viewport } from "next";
import Link from "next/link";
import "./globals.css";
import NavLinks from "./nav-links";

export const metadata: Metadata = {
  metadataBase: new URL("https://zodia8393.github.io"),
  title: "CatalogForge | 복원력 있는 상품 데이터 수집",
  description: "직접 입력하는 실시간 파서와 1,022건 실제 실행으로 증명한 웹 수집·복구 파이프라인",
  openGraph: {
    title: "CatalogForge | 복원력 있는 상품 데이터 수집",
    description: "HTML을 직접 입력해 구조화 결과를 보고, 실제 run UUID와 attempt 근거까지 확인하세요.",
    type: "website",
    url: "https://zodia8393.github.io/catalog-forge/",
  },
};

export const viewport: Viewport = {
  colorScheme: "dark",
  themeColor: "#071018",
};

const sampleDataHref = process.env.GITHUB_PAGES === "true"
  ? "/catalog-forge/sample-products.json"
  : "/sample-products.json";

export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="ko">
      <body>
        <div className="shell">
          <aside className="sidebar">
            <Link className="brand" href="/">
              <span className="brand-mark">CF</span>
              <span><strong>CatalogForge</strong><small>수집 운영 화면</small></span>
            </Link>
            <NavLinks />
            <div className="sidebar-resources" aria-label="프로젝트 링크">
              <a href="https://github.com/zodia8393/catalog-forge" rel="noreferrer" target="_blank">GitHub 저장소 <span>↗</span></a>
              <a download href={sampleDataHref}>실제 실행 JSON <span>↓</span></a>
            </div>
            <div className="sidebar-foot">
              <span className="pulse" />
              실제 실행 snapshot
              <small>generator가 저장한 실행 기록</small>
            </div>
          </aside>
          <main>{children}</main>
        </div>
      </body>
    </html>
  );
}
