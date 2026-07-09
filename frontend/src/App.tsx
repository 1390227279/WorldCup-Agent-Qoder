import { BrowserRouter, Routes, Route } from "react-router-dom";
import { QueryClientProvider } from "@tanstack/react-query";
import { queryClient } from "./queryClient";
import HomePage from "./pages/HomePage";
import BracketSandboxPage from "./pages/BracketSandboxPage";
import TeamPage from "./pages/TeamPage";
import AdminEventsPage from "./pages/AdminEventsPage";

function App() {
  return (
    <QueryClientProvider client={queryClient}>
      <BrowserRouter>
        <div className="min-h-screen bg-[var(--color-bg)] text-[var(--color-text)]">
          <Routes>
            <Route path="/" element={<HomePage />} />
            <Route path="/bracket" element={<BracketSandboxPage />} />
            <Route path="/team/:id" element={<TeamPage />} />
            <Route path="/admin/events" element={<AdminEventsPage />} />
          </Routes>
        </div>
      </BrowserRouter>
    </QueryClientProvider>
  );
}

export default App;
