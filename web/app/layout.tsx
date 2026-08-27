import type { Metadata } from "next";
import Link from "next/link";
import "./globals.css";

export const metadata: Metadata = {
  title: "CatalogForge | 상품 데이터 수집 운영",
  description: "장애 복구와 구조 변경 감지를 갖춘 상품 데이터 수집 운영 화면",
};

const nav = [
  ["한눈에 보기", "/"],
  ["수집 실행", "/runs/"],
  ["상품 데이터", "/products/"],
  ["샘플 데이터", "/samples/"],
];

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
            <nav aria-label="주요 메뉴">
              {nav.map(([label, href]) => <Link key={href} href={href}>{label}</Link>)}
            </nav>
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
