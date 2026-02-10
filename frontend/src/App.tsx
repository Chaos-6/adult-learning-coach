/**
 * App root — sets up routing and global providers.
 *
 * Route structure:
 *   /                         → Dashboard (instructor home)
 *   /upload                   → Upload a new video
 *   /evaluations/:evaluationId → View evaluation report
 *
 * Providers:
 *   - ThemeProvider: MUI theme (colors, typography, component overrides)
 *   - QueryClientProvider: React Query for data fetching & caching
 *   - BrowserRouter: Client-side routing via React Router
 *
 * Layout wraps all routes with the sidebar navigation shell.
 */

import React from "react";
import { BrowserRouter, Routes, Route } from "react-router-dom";
import { ThemeProvider, CssBaseline } from "@mui/material";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";

import theme from "./theme";
import Layout from "./components/Layout";
import Dashboard from "./pages/Dashboard";
import Upload from "./pages/Upload";
import EvaluationDetail from "./pages/EvaluationDetail";

// React Query client — manages server state caching and refetching.
// staleTime: 30s means data is considered "fresh" for 30s after fetch.
// During that window, navigating back to a page shows cached data instantly
// instead of showing a loading spinner. After 30s, it refetches in background.
const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      staleTime: 30 * 1000,
      retry: 1,
    },
  },
});

function App() {
  return (
    <ThemeProvider theme={theme}>
      <CssBaseline />
      <QueryClientProvider client={queryClient}>
        <BrowserRouter>
          <Routes>
            <Route element={<Layout />}>
              <Route path="/" element={<Dashboard />} />
              <Route path="/upload" element={<Upload />} />
              <Route
                path="/evaluations/:evaluationId"
                element={<EvaluationDetail />}
              />
            </Route>
          </Routes>
        </BrowserRouter>
      </QueryClientProvider>
    </ThemeProvider>
  );
}

export default App;
