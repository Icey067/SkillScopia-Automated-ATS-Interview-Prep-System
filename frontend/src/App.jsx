import { Navigate, Route, Routes } from "react-router-dom";
import { useAuth } from "./auth.jsx";
import Dashboard from "./pages/Dashboard.jsx";
import Interview from "./pages/Interview.jsx";
import Login from "./pages/Login.jsx";
import Register from "./pages/Register.jsx";
import { LoadingSpinner } from "./components";

function Protected({ children }) {
  const { access, loading } = useAuth();
  if (loading) {
    return (
      <div className="min-h-screen grid place-items-center bg-slate-950">
        <LoadingSpinner size="lg" label="Loading…" />
      </div>
    );
  }
  if (!access) return <Navigate to="/login" replace />;
  return children;
}

export default function App() {
  return (
    <Routes>
      <Route path="/login" element={<Login />} />
      <Route path="/register" element={<Register />} />
      <Route
        path="/"
        element={
          <Protected>
            <Dashboard />
          </Protected>
        }
      />
      <Route
        path="/interview/:sessionId"
        element={
          <Protected>
            <Interview />
          </Protected>
        }
      />
    </Routes>
  );
}