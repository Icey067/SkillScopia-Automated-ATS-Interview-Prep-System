import { motion, AnimatePresence } from "framer-motion";
import React from "react";
import { useLocation } from "react-router-dom";
import { pageTransition } from "../animations/variants";

export function PageTransition({ children }) {
  const location = useLocation();

  return (
    <AnimatePresence mode="wait">
      <motion.div
        key={location.pathname}
        variants={pageTransition}
        initial="initial"
        animate="animate"
        exit="exit"
        className="min-h-screen"
      >
        {children}
      </motion.div>
    </AnimatePresence>
  );
}

export function AnimatedRoutes({ children }) {
  const location = useLocation();

  return (
    <AnimatePresence mode="wait">
      <motion.div
        key={location.pathname}
        variants={pageTransition}
        initial="initial"
        animate="animate"
        exit="exit"
      >
        {children}
      </motion.div>
    </AnimatePresence>
  );
}

export function FadeInSection({ children, delay = 0, className = "", ...props }) {
  return (
    <motion.section
      variants={{ hidden: { opacity: 0, y: 20 }, visible: { opacity: 1, y: 0, transition: { duration: 0.5, delay, ease: "easeOut" } } }}
      initial="hidden"
      animate="visible"
      className={className}
      {...props}
    >
      {children}
    </motion.section>
  );
}

export function StaggeredList({ children, className = "", stagger = 0.08, ...props }) {
  return (
    <motion.div
      variants={{
        hidden: { opacity: 0 },
        visible: { opacity: 1, transition: { staggerChildren: stagger } },
      }}
      initial="hidden"
      animate="visible"
      className={className}
      {...props}
    >
      {React.Children.map(children, (child, index) =>
        React.isValidElement(child)
          ? React.cloneElement(child, {
              variants: { hidden: { opacity: 0, y: 10 }, visible: { opacity: 1, y: 0, transition: { duration: 0.3 } } },
            })
          : child
      )}
    </motion.div>
  );
}
