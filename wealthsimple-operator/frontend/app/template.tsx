"use client";

import { useEffect } from "react";
import type { ReactNode } from "react";
import { usePathname } from "next/navigation";
import { logAuditActivity } from "../lib/api";

export default function AppTemplate({ children }: { children: ReactNode }) {
  const pathname = usePathname();

  useEffect(() => {
    if (!pathname) return;

    const actor = "Wealthsimple Operator";
    const signInKey = "operator_signed_in_logged";

    if (typeof window !== "undefined" && !window.sessionStorage.getItem(signInKey)) {
      window.sessionStorage.setItem(signInKey, "1");
      void logAuditActivity({
        event_type: "OPERATOR_SIGNED_IN",
        actor,
        page: pathname,
        details: { source: "frontend-template" }
      }).catch(() => undefined);
    }

    void logAuditActivity({
      event_type: "PAGE_VIEWED",
      actor,
      page: pathname,
      details: { source: "frontend-template" }
    }).catch(() => undefined);
  }, [pathname]);

  return (
    <div key={pathname} className="page-enter">
      {children}
    </div>
  );
}
