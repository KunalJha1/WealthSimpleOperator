"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import clsx from "clsx";
import type { ComponentType, SVGProps } from "react";
import {
  Activity,
  Globe2,
  ClipboardList,
  Settings as SettingsIcon,
  LineChart,
  FileText,
  Scale,
  CalendarClock,
  Scissors,
  TrendingUp
} from "lucide-react";

type NavItem = {
  href: string;
  label: string;
  icon: ComponentType<SVGProps<SVGSVGElement>>;
};

const navItems: NavItem[] = [
  { href: "/operator", label: "Operator Console", icon: Activity },
  { href: "/auto-reallocation", label: "Auto Reallocation", icon: Scale },
  { href: "/meeting-notes", label: "Meeting Notes", icon: FileText },
  { href: "/monitoring-universe", label: "Monitoring Universe", icon: Globe2 },
  { href: "/simulations", label: "Scenario Lab", icon: LineChart },
  { href: "/contact-scheduler", label: "Contact Scheduler", icon: CalendarClock },
  { href: "/tax-loss-harvesting", label: "Tax-Loss Harvesting", icon: Scissors },
  { href: "/risk-dashboard", label: "Risk Dashboard", icon: TrendingUp },
  { href: "/audit-log", label: "Audit Log", icon: ClipboardList },
  { href: "/settings", label: "Settings", icon: SettingsIcon }
];

export default function Sidebar() {
  const pathname = usePathname();

  return (
    <aside className="w-64 border-r border-ws-border bg-white flex flex-col">
      <div className="px-6 py-4 border-b border-ws-border">
        <div className="flex items-center gap-3">
          <div className="rounded-lg border border-gray-200 bg-white p-2 shadow-sm flex-shrink-0">
            <svg width="28" height="28" viewBox="0 0 32 32" xmlns="http://www.w3.org/2000/svg">
              <rect width="32" height="32" rx="6" fill="#ffffff"/>
              <g transform="translate(1.35,7.35) scale(0.90)">
                <path fillRule="evenodd" clipRule="evenodd"
                  d="M24.977 2.13069V2.38056C25.7127 2.56628 26.267 2.94446 26.6432 3.51511C27.0195 4.08914 27.2076 4.88264 27.2076 5.89563C27.2076 6.96602 27.043 8.04991 26.7104 9.14732C26.3812 10.2447 25.9008 11.4232 25.2793 12.6793L24.6007 14.1751L21.2581 6.0881C21.0935 5.69978 20.9591 5.30472 20.8584 4.89615C20.7576 4.49095 20.7072 4.17693 20.7072 3.95407C20.7072 3.0694 21.1943 2.54264 22.1685 2.37719V2.12732H12.1979V2.37719C12.5842 2.45147 12.9134 2.56628 13.1889 2.7216C13.4644 2.8803 13.7264 3.15043 13.975 3.53875C14.2236 3.92706 14.5024 4.49771 14.8148 5.25407L16.4173 8.97849L13.5853 14.6006L9.38946 4.83537C9.2618 4.61251 9.17446 4.41667 9.12743 4.24108C9.08039 4.0655 9.06024 3.90342 9.06024 3.75485C9.06024 3.46108 9.16102 3.19095 9.36258 2.95121C9.56414 2.71147 9.85977 2.51901 10.2427 2.37043V2.12056H0.0772705V2.37043C0.88688 2.61017 1.60915 3.06264 2.25415 3.72784C2.89579 4.39303 3.53071 5.40939 4.15555 6.77355L10.6022 21.1985H10.8777L16.6927 9.61329L21.6747 21.1985H21.9502L27.8727 8.37745C28.7361 6.53043 29.5289 5.15615 30.2545 4.25121C30.9802 3.34628 31.736 2.71823 32.5288 2.36706V2.11719H24.977V2.13069Z"
                  fill="#32302F"/>
              </g>
            </svg>
          </div>
          <div>
            <div className="text-xs font-semibold text-ws-muted uppercase tracking-[0.18em]">
              Wealthsimple
            </div>
            <div className="text-sm font-semibold text-gray-900">Operator</div>
          </div>
        </div>
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
    </aside>
  );
}

