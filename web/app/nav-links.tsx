"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";

const navItems = [
  ["한눈에 보기", "/"],
  ["수집 실행", "/runs/"],
  ["상품 데이터", "/products/"],
  ["샘플 데이터", "/samples/"],
] as const;

export default function NavLinks() {
  const pathname = (usePathname() || "/").replace(/^\/catalog-forge/, "") || "/";

  return (
    <nav aria-label="주요 메뉴">
      {navItems.map(([label, href]) => {
        const route = href === "/" ? href : href.slice(0, -1);
        const active = route === "/" ? pathname === "/" : pathname === route || pathname.startsWith(`${route}/`);
        return (
          <Link aria-current={active ? "page" : undefined} className={active ? "active" : ""} href={href} key={href}>
            <span>{label}</span>
          </Link>
        );
      })}
    </nav>
  );
}
