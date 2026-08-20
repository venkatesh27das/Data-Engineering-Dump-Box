import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";

import type { Project, SourceAsset } from "../../types/build";
import type { Run } from "../../types/runs";
import { ApiError } from "../../services/projects";
import { BuildPage } from "./BuildPage";

const project: Project = {
  id: "project-1",
  name: "Supplier Knowledge Graph",
  knowledge_objective: "Understand suppliers, contracts, products and contractual obligations.",
  processing_mode: "auto",
  graph_depth: "entity_relationships",
  review_low_confidence: true,
  max_tokens: 4096,
  created_at: "2026-08-10T00:00:00Z",
  updated_at: "2026-08-10T00:00:00Z",
};

const uploadedSource: SourceAsset = {
  id: "source-1",
  project_id: project.id,
  filename: "supplier_schema.sql",
  original_filename: "supplier_schema.sql",
  category: "structured",
  extension: ".sql",
  mime_type: "text/plain",
  size_bytes: 34,
  storage_path: "/tmp/supplier_schema.sql",
  status: "uploaded",
  summary: "Ready for analysis",
  created_at: "2026-08-10T00:00:00Z",
};

const serviceMocks = vi.hoisted(() => ({
  createProject: vi.fn(),
  deleteSource: vi.fn(),
  getProject: vi.fn(),
  listSources: vi.fn(),
  updateProject: vi.fn(),
  uploadSource: vi.fn(),
}));

const runServiceMocks = vi.hoisted(() => ({
  getRun: vi.fn(),
  listRuns: vi.fn(),
  startRun: vi.fn(),
}));

vi.mock("../../services/projects", async (importOriginal) => {
  const original = await importOriginal<typeof import("../../services/projects")>();
  return { ...original, ...serviceMocks };
});

vi.mock("../../services/runs", async (importOriginal) => {
  const original = await importOriginal<typeof import("../../services/runs")>();
  return { ...original, ...runServiceMocks };
});

const queuedRun: Run = {
  id: "run-1",
  project_id: project.id,
  status: "queued",
  current_stage: "queued",
  plan: null,
  package_id: null,
  error_message: null,
  created_at: "2026-08-10T00:01:00Z",
  started_at: null,
  completed_at: null,
};

describe("BuildPage", () => {
  beforeEach(() => {
    localStorage.clear();
    Object.values(serviceMocks).forEach((mock) => mock.mockReset());
    Object.values(runServiceMocks).forEach((mock) => mock.mockReset());
    serviceMocks.createProject.mockResolvedValue(project);
    serviceMocks.getProject.mockResolvedValue(project);
    serviceMocks.listSources.mockResolvedValue([uploadedSource]);
    serviceMocks.updateProject.mockResolvedValue(project);
    serviceMocks.uploadSource.mockResolvedValue(uploadedSource);
    serviceMocks.deleteSource.mockResolvedValue(undefined);
    runServiceMocks.listRuns.mockResolvedValue([]);
    runServiceMocks.getRun.mockResolvedValue(queuedRun);
    runServiceMocks.startRun.mockResolvedValue(queuedRun);
  });

  it("uploads and renders a structured source", async () => {
    const user = userEvent.setup();
    const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
    const { container } = render(
      <QueryClientProvider client={queryClient}>
        <MemoryRouter><BuildPage /></MemoryRouter>
      </QueryClientProvider>,
    );
    const input = container.querySelector<HTMLInputElement>('input[accept=".sql,.json,.csv"]');
    expect(input).not.toBeNull();

    await user.upload(input!, new File(["CREATE TABLE suppliers (id INT);"], "supplier_schema.sql", { type: "text/plain" }));

    expect(await screen.findByText("supplier_schema.sql")).toBeInTheDocument();
    expect(serviceMocks.createProject).toHaveBeenCalledOnce();
    expect(serviceMocks.uploadSource).toHaveBeenCalledWith("project-1", expect.any(File));
  });

  it("clears stale project and run identifiers after a reset", async () => {
    localStorage.setItem("knowledge-graph-builder.project-id", "removed-project");
    localStorage.setItem("knowledge-graph-builder.run-id", "removed-run");
    serviceMocks.getProject.mockRejectedValue(new ApiError("Project not found", 404));
    const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });

    render(
      <QueryClientProvider client={queryClient}>
        <MemoryRouter><BuildPage /></MemoryRouter>
      </QueryClientProvider>,
    );

    await waitFor(() => {
      expect(localStorage.getItem("knowledge-graph-builder.project-id")).toBeNull();
      expect(localStorage.getItem("knowledge-graph-builder.run-id")).toBeNull();
    });
    expect(screen.getByText("No sources uploaded yet.")).toBeInTheDocument();
  });

  it("resets unsaved configuration without removing sources and launches in the background", async () => {
    localStorage.setItem("knowledge-graph-builder.project-id", project.id);
    const user = userEvent.setup();
    const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
    const { container } = render(
      <QueryClientProvider client={queryClient}>
        <MemoryRouter><BuildPage /></MemoryRouter>
      </QueryClientProvider>,
    );

    const view = within(container);
    const objective = await view.findByRole("textbox", { name: "Knowledge objective" });
    await user.clear(objective);
    await user.type(objective, "An unsaved objective");
    await user.click(view.getByRole("button", { name: "Reset" }));

    expect(objective).toHaveValue(project.knowledge_objective);
    expect(view.getByText("supplier_schema.sql")).toBeInTheDocument();
    expect(view.getByText(/Uploaded sources were preserved/)).toBeInTheDocument();

    await user.click(view.getByRole("button", { name: "Save Draft" }));
    await waitFor(() => expect(serviceMocks.updateProject).toHaveBeenCalled());
    expect(view.getByText("Draft configuration saved.")).toBeInTheDocument();

    await user.click(view.getByRole("button", { name: "Start Run" }));
    await waitFor(() => expect(runServiceMocks.startRun).toHaveBeenCalledWith(project.id));
    expect(view.getByRole("heading", { name: "Build", level: 1 })).toBeInTheDocument();
    expect(await view.findAllByText(/Your run is queued/)).not.toHaveLength(0);
  });
});
