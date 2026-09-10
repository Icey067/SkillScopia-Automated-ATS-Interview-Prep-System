import { motion } from "framer-motion";
import React from "react";
import { cardHover, fadeIn, slideUp, staggerContainer, staggerItem } from "../animations/variants";

const variantStyles = {
  default: "bg-slate-900/50 border border-slate-800",
  elevated: "bg-slate-900/70 shadow-xl shadow-slate-950/50 border border-slate-800/50",
  outlined: "bg-transparent border-2 border-slate-700",
  interactive: "bg-slate-900/50 border border-slate-800 cursor-pointer",
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
  const isInteractive = variant === "interactive" || hover;

  return (
    <motion.div
      variants={isInteractive ? cardHover : fadeIn}
      initial="hidden"
      animate={isInteractive ? "rest" : "visible"}
      whileHover={isInteractive ? "hover" : undefined}
      className={`${variantStyles[variant]} ${paddingStyles[padding]} rounded-2xl ${className}`}
      {...props}
    >
      {children}
    </motion.div>
  );
}

export function CardStack({ children, className = "", ...props }) {
  return (
    <motion.div
      variants={staggerContainer}
      initial="hidden"
      animate="visible"
      className={`space-y-4 ${className}`}
      {...props}
    >
      {React.Children.map(children, (child) =>
        React.isValidElement(child) ? React.cloneElement(child, { variants: staggerItem }) : child
      )}
    </motion.div>
  );
}

export function AnimatedCard({ children, delay = 0, className = "", ...props }) {
  return (
    <motion.div
      variants={slideUp}
      initial="hidden"
      animate="visible"
      transition={{ delay }}
      className={`${variantStyles.default} ${paddingStyles.md} rounded-2xl ${className}`}
      {...props}
    >
      {children}
    </motion.div>
  );
}
