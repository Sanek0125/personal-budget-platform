import { cleanup, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";

import { App } from "./App";

afterEach(() => {
  cleanup();
  vi.restoreAllMocks();
  window.history.pushState({}, "", "/");
});

describe("App shell", () => {
  it("renders the dashboard layout with core personal-budget navigation", async () => {
    vi.spyOn(globalThis, "fetch").mockResolvedValueOnce(new Response("[]", { status: 200 }));

    render(<App />);

    expect(screen.getByRole("heading", { name: /personal budget/i })).toBeInTheDocument();
    expect(screen.getByRole("link", { name: /dashboard/i })).toHaveAttribute("href", "/");
    expect(screen.getByRole("link", { name: /transactions/i })).toHaveAttribute("href", "/transactions");
    expect(screen.getByRole("link", { name: /accounts/i })).toHaveAttribute("href", "/accounts");
    expect(screen.getByRole("link", { name: /imports/i })).toHaveAttribute("href", "/imports");
    expect(screen.getByRole("link", { name: /budgets/i })).toHaveAttribute("href", "/budgets");
    expect(screen.getByRole("link", { name: /debts/i })).toHaveAttribute("href", "/debts");
    expect(screen.getByRole("link", { name: /rewards/i })).toHaveAttribute("href", "/rewards");
    expect(await screen.findByText(/select a workspace/i)).toBeInTheDocument();
  });

  it("loads workspaces for the development user and shows the active workspace", async () => {
    const fetchMock = vi.spyOn(globalThis, "fetch").mockResolvedValueOnce(
      new Response(
        JSON.stringify([
          {
            id: "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa",
            name: "Family Budget",
            kind: "family",
            base_currency_code: "RUB",
            owner_user_id: "11111111-1111-1111-1111-111111111111",
          },
        ]),
        { status: 200, headers: { "Content-Type": "application/json" } },
      ),
    );

    render(<App />);

    expect(await screen.findByText("Family Budget")).toBeInTheDocument();
    expect(screen.getByText(/family · rub/i)).toBeInTheDocument();
    await waitFor(() =>
      expect(fetchMock).toHaveBeenCalledWith(
        "/workspaces",
        expect.objectContaining({
          headers: expect.objectContaining({ "X-User-Id": expect.any(String) }),
        }),
      ),
    );
  });

  it("routes to feature placeholders from sidebar links", async () => {
    vi.spyOn(globalThis, "fetch").mockResolvedValueOnce(new Response("[]", { status: 200 }));
    const user = userEvent.setup();
    render(<App />);

    await user.click(screen.getByRole("link", { name: /transactions/i }));

    expect(screen.getByRole("heading", { name: /transactions/i })).toBeInTheDocument();
    expect(screen.getByText(/manual entries, splits, transfers, and imported operations/i)).toBeInTheDocument();
  });

  it("renders a not-found page for unknown routes", () => {
    vi.spyOn(globalThis, "fetch").mockResolvedValueOnce(new Response("[]", { status: 200 }));
    window.history.pushState({}, "", "/missing-page");

    render(<App />);

    expect(screen.getByRole("heading", { name: /page not found/i })).toBeInTheDocument();
    expect(screen.getByRole("link", { name: /back to dashboard/i })).toHaveAttribute("href", "/");
  });
});
