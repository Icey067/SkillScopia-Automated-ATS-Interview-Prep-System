import React from "react";

export function PageTransition({ children, className = "" }) {
  return <div className={`min-h-screen ${className}`}>{children}</div>;
}

export function AnimatedRoutes({ children }) {
  return <div className="min-h-screen">{children}</div>;
}

export function FadeInSection({ children, className = "", ...props }) {
  return (
    <section className={className} {...props}>
      {children}
    </section>
  );
}

export function StaggeredList({ children, className = "", ...props }) {
  return (
    <div className={className} {...props}>
      {children}
    </div>
  );
}
