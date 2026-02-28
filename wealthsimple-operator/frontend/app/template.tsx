"use client";

import type { ReactNode } from "react";
import { usePathname } from "next/navigation";

export default function AppTemplate({ children }: { children: ReactNode }) {
  const pathname = usePathname();

  return (
    <div key={pathname} className="page-enter">
      {children}
    </div>
  );
}
