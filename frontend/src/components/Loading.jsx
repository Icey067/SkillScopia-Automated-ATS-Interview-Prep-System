import { motion } from "framer-motion";
import { loadingDots, pulse } from "../animations/variants";

const sizeClasses = {
  sm: "w-4 h-4",
  md: "w-8 h-8",
  lg: "w-12 h-12",
};

export function LoadingSpinner({ size = "md", className = "", label }) {
  return (
    <div className={`flex flex-col items-center gap-2 ${className}`}>
      <motion.div
        animate={{ rotate: 360 }}
        transition={{ duration: 1, repeat: Infinity, ease: "linear" }}
        className={sizeClasses[size]}
      >
        <svg viewBox="0 0 24 24" fill="none" className="text-cyan-400">
          <circle
            cx="12"
            cy="12"
            r="10"
            stroke="currentColor"
            strokeWidth="3"
            strokeLinecap="round"
            strokeDasharray="31.4 31.4"
            className="opacity-25"
          />
          <circle
            cx="12"
            cy="12"
            r="10"
            stroke="currentColor"
            strokeWidth="3"
            strokeLinecap="round"
            strokeDasharray="31.4 31.4"
            strokeDashoffset="31.4"
            className="animate-spin"
          />
        </svg>
      </motion.div>
      {label && <p className="text-sm text-slate-400">{label}</p>}
    </div>
  );
}

export function LoadingDots({ className = "", label }) {
  return (
    <div className={`flex items-center gap-1 ${className}`}>
      <motion.span
        variants={loadingDots}
        animate="animate"
        className="w-2 h-2 rounded-full bg-cyan-400"
        style={{ transitionDelay: "0s" }}
      />
      <motion.span
        variants={loadingDots}
        animate="animate"
        className="w-2 h-2 rounded-full bg-cyan-400"
        style={{ transitionDelay: "0.1s" }}
      />
      <motion.span
        variants={loadingDots}
        animate="animate"
        className="w-2 h-2 rounded-full bg-cyan-400"
        style={{ transitionDelay: "0.2s" }}
      />
      {label && <span className="ml-2 text-sm text-slate-400">{label}</span>}
    </div>
  );
}

export function PulseLoader({ className = "" }) {
  return (
    <motion.div
      variants={pulse}
      animate="pulse"
      className={`rounded-lg bg-slate-800/50 ${className}`}
    />
  );
}

export function Skeleton({ className = "", variant = "text" }) {
  const baseClass = "bg-slate-800/50 rounded animate-pulse";

  const variants = {
    text: "h-4 w-full",
    card: "h-48 w-full rounded-xl",
    circle: "rounded-full",
    rect: "rounded-lg",
  };

  return <div className={`${baseClass} ${variants[variant]} ${className}`} />;
}

export function SkeletonCard({ className = "" }) {
  return (
    <div className={`rounded-2xl border border-slate-800 bg-slate-900/50 p-6 space-y-4 ${className}`}>
      <Skeleton variant="rect" className="h-6 w-3/4" />
      <Skeleton variant="text" />
      <Skeleton variant="text" className="w-5/6" />
      <Skeleton variant="text" className="w-4/6" />
      <div className="flex gap-2 mt-4">
        <Skeleton variant="circle" className="w-8 h-8" />
        <Skeleton variant="circle" className="w-8 h-8" />
        <Skeleton variant="circle" className="w-8 h-8" />
      </div>
    </div>
  );
}

export function SkeletonList({ count = 5, className = "" }) {
  return (
    <div className={`space-y-3 ${className}`}>
      {Array.from({ length: count }).map((_, i) => (
        <SkeletonCard key={i} />
      ))}
    </div>
  );
}
