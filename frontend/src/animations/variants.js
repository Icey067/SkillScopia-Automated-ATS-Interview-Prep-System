export const EASE_SMOOTH = [0.22, 1, 0.36, 1];
export const EASE_IN_OUT = [0.4, 0, 0.2, 1];

export const fadeIn = {
  hidden: { opacity: 0 },
  visible: { opacity: 1, transition: { duration: 0.25, ease: EASE_SMOOTH } },
};

export const slideUp = {
  hidden: { opacity: 0, y: 12 },
  visible: { opacity: 1, y: 0, transition: { duration: 0.35, ease: EASE_SMOOTH } },
};

export const slideDown = {
  hidden: { opacity: 0, y: -12 },
  visible: { opacity: 1, y: 0, transition: { duration: 0.3, ease: EASE_SMOOTH } },
};

export const slideInLeft = {
  hidden: { opacity: 0, x: -20 },
  visible: { opacity: 1, x: 0, transition: { duration: 0.35, ease: EASE_SMOOTH } },
};

export const slideInRight = {
  hidden: { opacity: 0, x: 20 },
  visible: { opacity: 1, x: 0, transition: { duration: 0.35, ease: EASE_SMOOTH } },
};

export const scaleIn = {
  hidden: { opacity: 0, scale: 0.96 },
  visible: { opacity: 1, scale: 1, transition: { duration: 0.22, ease: EASE_SMOOTH } },
};

export const staggerContainer = {
  hidden: { opacity: 0 },
  visible: {
    opacity: 1,
    transition: { staggerChildren: 0.06, delayChildren: 0.05 },
  },
};

export const staggerItem = {
  hidden: { opacity: 0, y: 8 },
  visible: { opacity: 1, y: 0, transition: { duration: 0.28, ease: EASE_SMOOTH } },
};

export const pulse = {
  pulse: {
    scale: [1, 1.04, 1],
    transition: { duration: 1.8, repeat: Infinity, ease: "easeInOut" },
  },
};

export const shimmer = {
  hidden: { backgroundPosition: "-200% 0" },
  visible: {
    backgroundPosition: "200% 0",
    transition: { duration: 1.5, repeat: Infinity, ease: "linear" },
  },
};

export const pageTransition = {
  initial: { opacity: 0, y: 8, filter: "blur(2px)" },
  animate: {
    opacity: 1,
    y: 0,
    filter: "blur(0px)",
    transition: { duration: 0.32, ease: EASE_SMOOTH },
  },
  exit: {
    opacity: 0,
    y: -8,
    filter: "blur(2px)",
    transition: { duration: 0.2, ease: EASE_IN_OUT },
  },
};

export const questionTransition = {
  initial: { opacity: 0, x: 25, scale: 0.98 },
  animate: {
    opacity: 1,
    x: 0,
    scale: 1,
    transition: { duration: 0.35, ease: EASE_SMOOTH },
  },
  exit: {
    opacity: 0,
    x: -25,
    scale: 0.98,
    transition: { duration: 0.25, ease: EASE_IN_OUT },
  },
};

export const cardHover = {
  rest: { y: 0, boxShadow: "0 4px 6px -1px rgba(0, 0, 0, 0.2)" },
  hover: {
    y: -3,
    boxShadow: "0 16px 24px -4px rgba(0, 0, 0, 0.35), 0 6px 10px -4px rgba(6, 182, 212, 0.15)",
    transition: { duration: 0.2, ease: EASE_SMOOTH },
  },
};

export const buttonTap = {
  tap: { scale: 0.98, transition: { duration: 0.1 } },
};

export const inputFocus = {
  focus: { scale: 1.005, borderColor: "#06b6d4", transition: { duration: 0.15 } },
  blur: { scale: 1, borderColor: "rgba(148, 163, 184, 0.4)", transition: { duration: 0.15 } },
};

export const toastEnter = {
  hidden: { opacity: 0, x: 80, scale: 0.95 },
  visible: { opacity: 1, x: 0, scale: 1, transition: { duration: 0.3, ease: EASE_SMOOTH } },
  exit: { opacity: 0, x: 80, scale: 0.95, transition: { duration: 0.2, ease: EASE_IN_OUT } },
};

export const loadingDots = {
  animate: {
    opacity: [0.3, 1, 0.3],
    transition: { duration: 0.6, repeat: Infinity, staggerChildren: 0.1 },
  },
};

export const typingIndicator = {
  animate: {
    y: [0, -3, 0],
    transition: { duration: 0.6, repeat: Infinity, staggerChildren: 0.15 },
  },
};