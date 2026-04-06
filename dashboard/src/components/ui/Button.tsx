import { clsx } from "clsx";

interface ButtonProps extends React.ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: "primary" | "secondary" | "outline" | "danger";
  size?: "sm" | "md" | "lg";
}

const variants = {
  primary: "bg-crimson text-creme hover:bg-crimson-dark",
  secondary: "bg-rich-creme text-crimson-dark hover:bg-creme",
  outline: "border border-crimson text-crimson hover:bg-crimson hover:text-creme",
  danger: "bg-red-600 text-white hover:bg-red-700",
};

const sizes = {
  sm: "px-4 py-2 text-xs",
  md: "px-4 py-2 text-sm",
  lg: "px-6 py-3 text-base",
};

export default function Button({
  variant = "primary",
  size = "md",
  className,
  children,
  ...props
}: ButtonProps) {
  return (
    <button
      className={clsx(
        "inline-flex items-center justify-center gap-2 rounded font-bold transition-colors disabled:opacity-50 disabled:cursor-not-allowed",
        variants[variant],
        sizes[size],
        className
      )}
      {...props}
    >
      {children}
    </button>
  );
}
