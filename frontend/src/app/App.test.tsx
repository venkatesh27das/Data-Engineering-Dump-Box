import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import { describe, expect, it, vi } from "vitest";

import { App } from "./App";

vi.stubGlobal("fetch", vi.fn().mockResolvedValue({
  ok: true,
  json: async () => ({ api: "ok", lmstudio: "not_configured", neo4j: "not_configured" }),
}));

function renderApp() {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={queryClient}>
      <MemoryRouter initialEntries={["/"]}>
        <App />
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

describe("application navigation", () => {
  it("moves between all three primary routes", async () => {
    const user = userEvent.setup();
    renderApp();

    expect(screen.getByRole("heading", { name: "Build", level: 1 })).toBeInTheDocument();

    await user.click(screen.getByRole("link", { name: /Graph Assets/i }));
    expect(screen.getByRole("heading", { name: "Graph Assets", level: 1 })).toBeInTheDocument();

    await user.click(screen.getByRole("link", { name: /Graph Explorer/i }));
    expect(await screen.findByRole("heading", { name: "Graph Explorer", level: 1 })).toBeInTheDocument();
  });
});
