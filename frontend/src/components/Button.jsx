import { motion } from "framer-motion";
import { forwardRef } from "react";
import { buttonTap, scaleIn } from "../animations/variants";

const variantStyles = {
  primary: "bg-cyan-500 text-slate-950 hover:bg-cyan-400 active:bg-cyan-600",
  secondary: "bg-slate-800 text-slate-100 hover:bg-slate-700 active:bg-slate-600 border border-slate-700",
  outline: "border-2 border-cyan-500 text-cyan-400 hover:bg-cyan-500/10 active:bg-cyan-500/20",
  ghost: "text-slate-300 hover:bg-slate-800 active:bg-slate-700",
  danger: "bg-rose-500 text-white hover:bg-rose-400 active:bg-rose-600",
};

const sizeStyles = {
  sm: "px-3 py-1.5 text-sm gap-1.5",
  md: "px-4 py-2 text-base gap-2",
  lg: "px-6 py-3 text-lg gap-2.5",
};

export const Button = forwardRef(
  (
    {
      variant = "primary",
      size = "md",
      isLoading = false,
      leftIcon,
      rightIcon,
      fullWidth = false,
      disabled,
      className = "",
      children,
      ...props
    },
    ref
  ) => {
    const baseStyles = "inline-flex items-center justify-center font-medium rounded-xl transition-colors disabled:opacity-50 disabled:cursor-not-allowed focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-cyan-500/50 focus-visible:ring-offset-2 focus-visible:ring-offset-slate-950";
    const widthStyle = fullWidth ? "w-full" : "";

    return (
      <motion.button
        ref={ref}
        whileTap="tap"
        initial="hidden"
        animate="visible"
        variants={{ ...scaleIn, ...buttonTap }}
        className={`${baseStyles} ${variantStyles[variant]} ${sizeStyles[size]} ${widthStyle} ${className}`}
        disabled={disabled || isLoading}
        {...props}
      >
        {isLoading ? (
          <>
            <svg className="animate-spin h-4 w-4" viewBox="0 0 24 24" fill="none">
              <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="3" />
              <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z" />
            </svg>
            <span>Loading...</span>
          </>
        ) : (
          <>
            {leftIcon && <span className="flex-shrink-0">{leftIcon}</span>}
            <span>{children}</span>
            {rightIcon && <span className="flex-shrink-0">{rightIcon}</span>}
          </>
        )}
      </motion.button>
    );
  }
);

Button.displayName = "Button";
