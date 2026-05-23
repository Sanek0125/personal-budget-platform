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

  it("creates a development user from settings", async () => {
    const fetchMock = vi
      .spyOn(globalThis, "fetch")
      .mockResolvedValueOnce(new Response("[]", { status: 200 }))
      .mockResolvedValueOnce(
        new Response(
          JSON.stringify({
            id: "22222222-2222-2222-2222-222222222222",
            email: "olga@example.com",
            display_name: "Olga",
            telegram_id: null,
            is_active: true,
          }),
          { status: 201, headers: { "Content-Type": "application/json" } },
        ),
      );
    const user = userEvent.setup();
    render(<App />);

    await user.click(screen.getByRole("link", { name: /settings/i }));
    await user.type(screen.getByLabelText(/display name/i), " Olga ");
    await user.type(screen.getByLabelText(/^email$/i), "OLGA@example.com");
    await user.click(screen.getByRole("button", { name: /create user/i }));

    expect(await screen.findByText(/created user Olga/i)).toBeInTheDocument();
    expect(fetchMock).toHaveBeenLastCalledWith(
      "/users",
      expect.objectContaining({
        method: "POST",
        body: JSON.stringify({ display_name: "Olga", email: "olga@example.com" }),
      }),
    );
  });

  it("adds an existing user to the active workspace from settings", async () => {
    const fetchMock = vi
      .spyOn(globalThis, "fetch")
      .mockResolvedValueOnce(
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
      )
      .mockResolvedValueOnce(
        new Response(
          JSON.stringify([
            {
              id: "22222222-2222-2222-2222-222222222222",
              email: "olga@example.com",
              display_name: "Olga",
              telegram_id: null,
              is_active: true,
            },
          ]),
          { status: 200, headers: { "Content-Type": "application/json" } },
        ),
      )
      .mockResolvedValueOnce(
        new Response(
          JSON.stringify({
            id: "33333333-3333-3333-3333-333333333333",
            workspace_id: "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa",
            user_id: "22222222-2222-2222-2222-222222222222",
            role: "member",
          }),
          { status: 201, headers: { "Content-Type": "application/json" } },
        ),
      );
    const user = userEvent.setup();
    render(<App />);

    await user.click(screen.getByRole("link", { name: /settings/i }));
    await user.type(screen.getByLabelText(/find user by email/i), "OLGA@example.com");
    await user.click(screen.getByRole("button", { name: /find user/i }));
    await user.click(await screen.findByRole("button", { name: /add Olga as member/i }));

    expect(await screen.findByText(/added Olga to Family Budget as member/i)).toBeInTheDocument();
    expect(fetchMock).toHaveBeenLastCalledWith(
      "/workspaces/aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa/members",
      expect.objectContaining({
        method: "POST",
        body: JSON.stringify({ user_id: "22222222-2222-2222-2222-222222222222", role: "member" }),
      }),
    );
  });

  it("renders a not-found page for unknown routes", () => {
    vi.spyOn(globalThis, "fetch").mockResolvedValueOnce(new Response("[]", { status: 200 }));
    window.history.pushState({}, "", "/missing-page");

    render(<App />);

    expect(screen.getByRole("heading", { name: /page not found/i })).toBeInTheDocument();
    expect(screen.getByRole("link", { name: /back to dashboard/i })).toHaveAttribute("href", "/");
  });
});
