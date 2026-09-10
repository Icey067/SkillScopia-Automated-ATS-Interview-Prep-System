import { motion } from "framer-motion";
import { forwardRef, useState, useId } from "react";
import { fadeIn } from "../animations/variants";

export const Input = forwardRef(
  (
    {
      label,
      error,
      hint,
      leftIcon,
      rightIcon,
      fullWidth = true,
      className = "",
      id: providedId,
      disabled,
      ...props
    },
    ref
  ) => {
    const generatedId = useId();
    const id = providedId || generatedId;
    const errorId = `${id}-error`;
    const hintId = `${id}-hint`;
    const [isFocused, setIsFocused] = useState(false);

    const inputClasses = `
      w-full bg-slate-950 text-slate-100 placeholder-slate-500
      rounded-xl px-4 py-3 text-base
      border-2 transition-all duration-150
      disabled:opacity-50 disabled:cursor-not-allowed
      focus:outline-none focus:ring-2 focus:ring-cyan-500/20
      ${error ? "border-rose-500 focus:border-rose-500 focus:ring-rose-500/20" : "border-slate-700 hover:border-slate-600 focus:border-cyan-500"}
      ${isFocused && !error ? "ring-2 ring-cyan-500/20 scale-[1.01]" : ""}
      ${className}
    `;

    const labelClasses = `
      block text-sm font-medium text-slate-300 mb-1.5
      ${error ? "text-rose-400" : ""}
      ${isFocused && !error ? "text-cyan-400" : ""}
      transition-colors duration-150
    `;

    return (
      <div className={`${fullWidth ? "w-full" : ""}`}>
        {label && <label htmlFor={id} className={labelClasses}>{label}</label>}
        <div className="relative">
          {leftIcon && (
            <div className="absolute left-3 top-1/2 -translate-y-1/2 text-slate-500 pointer-events-none">
              {leftIcon}
            </div>
          )}
          <motion.input
            ref={ref}
            id={id}
            className={inputClasses}
            aria-invalid={error ? "true" : "false"}
            aria-describedby={error ? errorId : hint ? hintId : undefined}
            onFocus={() => setIsFocused(true)}
            onBlur={() => setIsFocused(false)}
            disabled={disabled}
            {...props}
          />
          {rightIcon && (
            <div className="absolute right-3 top-1/2 -translate-y-1/2 text-slate-500 pointer-events-none">
              {rightIcon}
            </div>
          )}
        </div>
        {error && (
          <motion.p
            id={errorId}
            className="mt-1.5 text-sm text-rose-400 flex items-center gap-1"
            variants={fadeIn}
            initial="hidden"
            animate="visible"
          >
            <svg className="w-4 h-4 flex-shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z" />
            </svg>
            {error}
          </motion.p>
        )}
        {hint && !error && (
          <p id={hintId} className="mt-1.5 text-sm text-slate-500">
            {hint}
          </p>
        )}
      </div>
    );
  }
);

Input.displayName = "Input";
