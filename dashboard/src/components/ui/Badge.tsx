import { clsx } from "clsx";

interface BadgeProps {
  children: React.ReactNode;
  variant?: "default" | "crimson" | "success" | "warning" | "danger" | "info";
  className?: string;
}

const variants = {
  default: "bg-rich-creme text-warm-charcoal",
  crimson: "bg-crimson text-creme",
  success: "bg-green-100 text-green-800",
  warning: "bg-amber-100 text-amber-800",
  danger: "bg-red-100 text-red-800",
  info: "bg-blue-100 text-blue-800",
};

export default function Badge({ children, variant = "default", className }: BadgeProps) {
  return (
    <span
      className={clsx(
        "inline-flex items-center px-3 py-1 rounded-full text-xs font-bold font-label tracking-wider uppercase",
        variants[variant],
        className
      )}
    >
      {children}
    </span>
  );
}
