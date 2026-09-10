import { useEffect, useState, createContext, useContext } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { toastEnter, fadeIn } from "../animations/variants";

const ToastContext = createContext(null);

export function ToastProvider({ children }) {
  const [toasts, setToasts] = useState([]);

  const addToast = (toast) => {
    const id = Math.random().toString(36).substring(7);
    const duration = toast.duration ?? 4000;
    setToasts((prev) => [...prev, { ...toast, id }]);
    if (duration > 0) {
      setTimeout(() => removeToast(id), duration);
    }
  };

  const removeToast = (id) => {
    setToasts((prev) => prev.filter((t) => t.id !== id));
  };

  return (
    <ToastContext.Provider value={{ toasts, addToast, removeToast }}>
      {children}
      <ToastContainer toasts={toasts} onRemove={removeToast} />
    </ToastContext.Provider>
  );
}

export function useToast() {
  const context = useContext(ToastContext);
  if (!context) {
    throw new Error("useToast must be used within a ToastProvider");
  }
  return context;
}

function ToastContainer({ toasts, onRemove }) {
  const styleMap = {
    success: "bg-emerald-950/90 border-emerald-700 text-emerald-300",
    error: "bg-rose-950/90 border-rose-700 text-rose-300",
    info: "bg-cyan-950/90 border-cyan-700 text-cyan-300",
    warning: "bg-amber-950/90 border-amber-700 text-amber-300",
  };

  const iconMap = {
    success: (
      <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 13l4 4L19 7" />
      </svg>
    ),
    error: (
      <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
      </svg>
    ),
    info: (
      <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13 16h-1v-4h-1m1-4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
      </svg>
    ),
    warning: (
      <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z" />
      </svg>
    ),
  };

  return (
    <AnimatePresence>
      <div className="fixed bottom-6 right-6 z-50 flex flex-col gap-2 w-80 max-w-full">
        {toasts.map((toast) => (
          <motion.div
            key={toast.id}
            variants={toastEnter}
            initial="hidden"
            animate="visible"
            exit="exit"
            className={`rounded-xl border px-4 py-3 shadow-xl flex items-start gap-3 ${styleMap[toast.type]}`}
            onClick={() => onRemove(toast.id)}
          >
            <div className="flex-shrink-0 mt-0.5">{iconMap[toast.type]}</div>
            <p className="text-sm flex-1">{toast.message}</p>
            <button
              onClick={(e) => {
                e.stopPropagation();
                onRemove(toast.id);
              }}
              className="flex-shrink-0 opacity-50 hover:opacity-100 transition-opacity"
            >
              <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
              </svg>
            </button>
          </motion.div>
        ))}
      </div>
    </AnimatePresence>
  );
}