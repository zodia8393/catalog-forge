import type { Metadata } from "next";
import Link from "next/link";
import "./globals.css";

export const metadata: Metadata = {
  title: "CatalogForge Control Plane",
  description: "Resilient commerce web ingestion and catalog quality dashboard",
};

const nav = [
  ["Overview", "/"],
  ["Crawl runs", "/runs/"],
  ["Catalog", "/products/"],
];

export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="ko">
      <body>
        <div className="shell">
          <aside className="sidebar">
            <Link className="brand" href="/">
              <span className="brand-mark">CF</span>
              <span><strong>CatalogForge</strong><small>Control plane</small></span>
            </Link>
            <nav>
              {nav.map(([label, href]) => <Link key={href} href={href}>{label}</Link>)}
            </nav>
            <div className="sidebar-foot">
              <span className="pulse" />
              Replay evidence
              <small>Deterministic fixture run</small>
            </div>
          </aside>
          <main>{children}</main>
        </div>
      </body>
    </html>
  );
}
