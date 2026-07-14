import { BrowserRouter, Routes, Route } from "react-router-dom";
import { QueryClientProvider } from "@tanstack/react-query";
import { queryClient } from "./queryClient";
import HomePage from "./pages/HomePage";
import BracketSandboxPage from "./pages/BracketSandboxPage";
import TeamPage from "./pages/TeamPage";
import AdminEventsPage from "./pages/AdminEventsPage";
import DataSourcesPage from "./pages/DataSourcesPage";
import DashboardShell from "./components/DashboardShell";

function App() {
  return (
    <QueryClientProvider client={queryClient}>
      <BrowserRouter>
        <DashboardShell>
          <Routes>
            <Route path="/" element={<HomePage />} />
            <Route path="/bracket" element={<BracketSandboxPage />} />
            <Route path="/team/:id" element={<TeamPage />} />
            <Route path="/admin/events" element={<AdminEventsPage />} />
            <Route path="/data-sources" element={<DataSourcesPage />} />
          </Routes>
        </DashboardShell>
      </BrowserRouter>
    </QueryClientProvider>
  );
}

export default App;
