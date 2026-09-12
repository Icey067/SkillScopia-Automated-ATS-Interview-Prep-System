import React from "react";

const variantStyles = {
  default: "bg-slate-900/50 border border-slate-800",
  elevated: "bg-slate-900/70 shadow-xl shadow-slate-950/50 border border-slate-800/50",
  outlined: "bg-transparent border-2 border-slate-700",
  interactive: "bg-slate-900/50 border border-slate-800 cursor-pointer hover:border-slate-700 transition-colors",
};

const paddingStyles = {
  none: "",
  sm: "p-4",
  md: "p-6",
  lg: "p-8",
};

export function Card({
  variant = "default",
  padding = "md",
  hover = false,
  className = "",
  children,
  ...props
}) {
  return (
    <div
      className={`${variantStyles[variant]} ${paddingStyles[padding]} rounded-2xl ${className}`}
      {...props}
    >
      {children}
    </div>
  );
}

export function CardStack({ children, className = "", ...props }) {
  return (
    <div className={`space-y-4 ${className}`} {...props}>
      {children}
    </div>
  );
}

export function AnimatedCard({ children, delay = 0, className = "", ...props }) {
  return (
    <div
      className={`${variantStyles.default} ${paddingStyles.md} rounded-2xl ${className}`}
      {...props}
    >
      {children}
    </div>
  );
}
