import React from "react";
import ReactDOM from "react-dom/client";
import { BrowserRouter } from "react-router-dom";
import { AnimatePresence } from "framer-motion";
import App from "./App.jsx";
import { AuthProvider } from "./auth.jsx";
import { ToastProvider } from "./components/Toast";
import { PageTransition } from "./components/PageTransition";
import "./index.css";

ReactDOM.createRoot(document.getElementById("root")).render(
  <React.StrictMode>
    <BrowserRouter>
      <AuthProvider>
        <ToastProvider>
          <AnimatePresence mode="wait">
            <PageTransition>
              <App />
            </PageTransition>
          </AnimatePresence>
        </ToastProvider>
      </AuthProvider>
    </BrowserRouter>
  </React.StrictMode>
);