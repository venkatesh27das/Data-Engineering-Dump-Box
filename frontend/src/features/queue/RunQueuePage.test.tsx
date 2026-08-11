import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";

import type { RunDetail, RunQueueItem } from "../../types/runs";
import { RunQueuePage } from "./RunQueuePage";

const { listRuns, getRunDetail, cancelRun, deleteRun } = vi.hoisted(() => ({
  listRuns: vi.fn(),
  getRunDetail: vi.fn(),
  cancelRun: vi.fn(),
  deleteRun: vi.fn(),
}));

vi.mock("../../services/runs", () => ({ listRuns, getRunDetail, cancelRun, deleteRun }));

const queueItem: RunQueueItem = {
  run: {
    id: "run-12345678",
    project_id: "project-1",
    status: "running",
    current_stage: "knowledge_engineering",
    plan: null,
    package_id: null,
    error_message: null,
    created_at: "2026-08-11T08:00:00Z",
    started_at: "2026-08-11T08:00:01Z",
    completed_at: null,
  },
  project_name: "Supplier Knowledge Graph",
  source_count: 1,
  event_count: 2,
  artifact_count: 2,
  package: null,
};

const detail: RunDetail = {
  item: queueItem,
  sources: [{
    id: "source-1",
    project_id: "project-1",
    filename: "contract.pdf",
    original_filename: "contract.pdf",
    category: "unstructured",
    extension: ".pdf",
    mime_type: "application/pdf",
    size_bytes: 1024,
    storage_path: "/tmp/contract.pdf",
    status: "ready",
    summary: "Ready for analysis",
    created_at: "2026-08-11T08:00:00Z",
  }],
  events: [{
    id: "event-1",
    run_id: "run-12345678",
    sequence: 1,
    timestamp: "2026-08-11T08:00:01Z",
    stage: "source_analysis",
    status: "completed",
    title: "Source analysis completed",
    message: "Normalized one source",
    event_type: "stage",
  }],
  temporary_assets: [{
    id: "artifact-1",
    run_id: "run-12345678",
    stage: "source_analysis",
    artifact_type: "normalized_source",
    name: "Normalized contract.pdf",
    status: "completed",
    record_count: 3,
    parent_ids: ["source-1"],
    metadata: {},
    created_at: "2026-08-11T08:00:02Z",
  }],
  lineage: [{ parent_id: "source-1", child_id: "artifact-1", relationship: "normalized_from" }],
};

function renderPage() {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false }, mutations: { retry: false } } });
  return render(
    <QueryClientProvider client={queryClient}>
      <MemoryRouter initialEntries={["/queue/run-12345678"]}>
        <Routes><Route path="/queue/:runId" element={<RunQueuePage />} /></Routes>
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

describe("RunQueuePage", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    listRuns.mockResolvedValue([queueItem]);
    getRunDetail.mockResolvedValue(detail);
    cancelRun.mockResolvedValue({ ...queueItem, run: { ...queueItem.run, status: "canceled" } });
    deleteRun.mockResolvedValue(undefined);
  });

  it("shows progress, intermediate assets, lineage, and can stop an active process", async () => {
    const user = userEvent.setup();
    renderPage();

    expect((await screen.findAllByText("Supplier Knowledge Graph")).length).toBeGreaterThan(0);
    expect(screen.getByText("Source analysis completed")).toBeInTheDocument();

    await user.click(screen.getByRole("tab", { name: /Temporary assets/i }));
    expect(screen.getByText("Normalized contract.pdf")).toBeInTheDocument();

    await user.click(screen.getByRole("tab", { name: /Lineage/i }));
    expect(screen.getByText("contract.pdf")).toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: /Stop process/i }));
    expect(cancelRun).toHaveBeenCalled();
    expect(cancelRun.mock.calls[0][0]).toBe("run-12345678");
  });
});
