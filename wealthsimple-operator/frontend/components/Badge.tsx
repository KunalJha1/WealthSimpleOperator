import type { ReactNode } from "react";

interface BadgeProps {
  children: ReactNode;
  className?: string;
}

export default function Badge({ children, className }: BadgeProps) {
  return (
    <span
      className={`inline-flex items-center rounded-full border px-2.5 py-0.5 text-xs font-medium ${className ?? ""}`}
    >
      {children}
    </span>
  );
}

