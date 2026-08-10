import { lazy, Suspense } from "react";
import { Navigate, Route, Routes } from "react-router-dom";

import { AppShell } from "../components/AppShell";
import { GraphAssetsPage } from "../features/assets/GraphAssetsPage";
import { BuildPage } from "../features/build/BuildPage";

const GraphExplorerPage = lazy(() => import("../features/graph/GraphExplorerPage").then((module) => ({ default: module.GraphExplorerPage })));

export function App() {
  return (
    <Routes>
      <Route element={<AppShell />}>
        <Route index element={<BuildPage />} />
        <Route path="assets" element={<GraphAssetsPage />} />
        <Route path="graph" element={<Suspense fallback={<div className="route-loading">Loading Graph Explorer…</div>}><GraphExplorerPage /></Suspense>} />
      </Route>
      <Route path="*" element={<Navigate replace to="/" />} />
    </Routes>
  );
}
