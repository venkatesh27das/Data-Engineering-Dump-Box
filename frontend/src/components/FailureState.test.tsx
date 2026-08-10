import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

import { FailureState } from "./FailureState";

describe("FailureState", () => {
  it("announces the failure and offers a retry", async () => {
    const retry = vi.fn();
    const user = userEvent.setup();
    render(<FailureState description="The request failed." onRetry={retry} title="Service unavailable" />);

    expect(screen.getByRole("alert")).toHaveTextContent("The request failed.");
    await user.click(screen.getByRole("button", { name: "Try again" }));
    expect(retry).toHaveBeenCalledOnce();
  });
});
