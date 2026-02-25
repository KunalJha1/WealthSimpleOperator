"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import clsx from "clsx";
import type { ComponentType, SVGProps } from "react";
import { Activity, Globe2, ClipboardList, Settings as SettingsIcon } from "lucide-react";

type NavItem = {
  href: string;
  label: string;
  icon: ComponentType<SVGProps<SVGSVGElement>>;
};

const navItems: NavItem[] = [
  { href: "/operator", label: "Operator Console", icon: Activity },
  { href: "/monitoring-universe", label: "Monitoring Universe", icon: Globe2 },
  { href: "/audit-log", label: "Audit Log", icon: ClipboardList },
  { href: "/settings", label: "Settings", icon: SettingsIcon }
];

export default function Sidebar() {
  const pathname = usePathname();

  return (
    <aside className="w-64 border-r border-ws-border bg-white flex flex-col">
      <div className="px-6 py-4 border-b border-ws-border">
        <div className="text-xs font-semibold text-ws-muted uppercase tracking-[0.18em]">
          Wealthsimple
        </div>
        <div className="mt-2 text-lg font-semibold text-gray-900">Operator Console</div>
      </div>
      <nav className="flex-1 px-4 py-4 space-y-1">
        {navItems.map((item) => {
          const Icon = item.icon;
          const active = pathname === item.href || pathname?.startsWith(item.href + "/");
          return (
            <Link
              key={item.href}
              href={item.href}
              className={clsx(
                "flex items-center px-3 py-2 rounded-lg text-sm gap-2",
                active
                  ? "bg-ws-ink text-white font-medium"
                  : "text-gray-700 hover:bg-gray-100"
              )}
            >
              <Icon className="w-4 h-4" aria-hidden="true" />
              <span>{item.label}</span>
            </Link>
          );
        })}
      </nav>
      <div className="px-4 py-4 border-t border-ws-border text-xs text-ws-muted">
        AI responsibility: monitoring/triage only.
        <br />
        Human responsibility: investment decisions.
      </div>
    </aside>
  );
}

