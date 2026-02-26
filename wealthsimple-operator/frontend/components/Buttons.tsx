import type { ButtonHTMLAttributes, ReactNode } from "react";
import clsx from "clsx";

interface ButtonProps extends ButtonHTMLAttributes<HTMLButtonElement> {
  children: ReactNode;
  variant?: "primary" | "secondary" | "ghost";
}

export function Button({
  children,
  variant = "primary",
  className,
  ...props
}: ButtonProps) {
  const base =
    "inline-flex items-center justify-center rounded-lg text-sm font-medium px-3 py-2 border transition-colors disabled:opacity-60 disabled:cursor-not-allowed";

  const variantClasses =
    variant === "primary"
      ? "bg-ws-ink text-white border-ws-ink hover:bg-gray-800"
      : variant === "secondary"
        ? "bg-white text-gray-900 border-ws-border hover:bg-gray-100"
        : "bg-transparent text-gray-700 border-transparent hover:bg-gray-100";

  return (
    <button className={clsx(base, variantClasses, className)} {...props}>
      {children}
    </button>
  );
}

