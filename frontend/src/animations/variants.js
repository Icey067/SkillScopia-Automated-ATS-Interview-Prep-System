export const fadeIn = {
  hidden: { opacity: 0 },
  visible: { opacity: 1, transition: { duration: 0.3 } },
};

export const slideUp = {
  hidden: { opacity: 0, y: 20 },
  visible: { opacity: 1, y: 0, transition: { duration: 0.4, ease: "easeOut" } },
};

export const slideDown = {
  hidden: { opacity: 0, y: -20 },
  visible: { opacity: 1, y: 0, transition: { duration: 0.3, ease: "easeOut" } },
};

export const slideInLeft = {
  hidden: { opacity: 0, x: -30 },
  visible: { opacity: 1, x: 0, transition: { duration: 0.4, ease: "easeOut" } },
};

export const slideInRight = {
  hidden: { opacity: 0, x: 30 },
  visible: { opacity: 1, x: 0, transition: { duration: 0.4, ease: "easeOut" } },
};

export const scaleIn = {
  hidden: { opacity: 0, scale: 0.95 },
  visible: { opacity: 1, scale: 1, transition: { duration: 0.2, ease: "easeOut" } },
};

export const staggerContainer = {
  hidden: { opacity: 0 },
  visible: {
    opacity: 1,
    transition: { staggerChildren: 0.08, delayChildren: 0.1 },
  },
};

export const staggerItem = {
  hidden: { opacity: 0, y: 10 },
  visible: { opacity: 1, y: 0, transition: { duration: 0.3, ease: "easeOut" } },
};

export const pulse = {
  pulse: {
    scale: [1, 1.05, 1],
    transition: { duration: 1.5, repeat: Infinity, ease: "easeInOut" },
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
  initial: { opacity: 0, y: 20 },
  animate: { opacity: 1, y: 0, transition: { duration: 0.4, ease: "easeOut" } },
  exit: { opacity: 0, y: -20, transition: { duration: 0.3, ease: "easeIn" } },
};

export const cardHover = {
  rest: { y: 0, boxShadow: "0 4px 6px -1px rgba(0, 0, 0, 0.1)" },
  hover: {
    y: -4,
    boxShadow: "0 20px 25px -5px rgba(0, 0, 0, 0.1), 0 10px 10px -5px rgba(0, 0, 0, 0.04)",
    transition: { duration: 0.2, ease: "easeOut" },
  },
};

export const buttonTap = {
  tap: { scale: 0.97 },
};

export const inputFocus = {
  focus: { scale: 1.01, borderColor: "#06b6d4", transition: { duration: 0.15 } },
  blur: { scale: 1, borderColor: "rgba(148, 163, 184, 0.5)", transition: { duration: 0.15 } },
};

export const toastEnter = {
  hidden: { opacity: 0, x: 300, scale: 0.9 },
  visible: { opacity: 1, x: 0, scale: 1, transition: { duration: 0.3, ease: "easeOut" } },
  exit: { opacity: 0, x: 300, scale: 0.9, transition: { duration: 0.2, ease: "easeIn" } },
};

export const loadingDots = {
  animate: {
    opacity: [0.3, 1, 0.3],
    transition: { duration: 0.6, repeat: Infinity, staggerChildren: 0.1 },
  },
};

export const typingIndicator = {
  animate: {
    y: [0, -4, 0],
    transition: { duration: 0.6, repeat: Infinity, staggerChildren: 0.15 },
  },
};