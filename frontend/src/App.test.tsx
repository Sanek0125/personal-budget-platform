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

  it("lists accounts for the active workspace", async () => {
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
              id: "44444444-4444-4444-4444-444444444444",
              workspace_id: "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa",
              owner_user_id: null,
              name: "Tinkoff Black",
              type: "bank_card",
              currency_code: "RUB",
              institution_name: "T-Bank",
              masked_number: "*1234",
              opening_balance: "1500.00",
              is_active: true,
            },
          ]),
          { status: 200, headers: { "Content-Type": "application/json" } },
        ),
      );
    const user = userEvent.setup();
    render(<App />);

    await user.click(screen.getByRole("link", { name: /accounts/i }));

    expect(await screen.findByRole("heading", { name: /accounts/i })).toBeInTheDocument();
    expect(await screen.findByText("Tinkoff Black")).toBeInTheDocument();
    expect(screen.getByText(/bank_card · rub/i)).toBeInTheDocument();
    expect(screen.getByText(/T-Bank · \*1234/i)).toBeInTheDocument();
    expect(fetchMock).toHaveBeenLastCalledWith(
      "/workspaces/aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa/accounts",
      expect.objectContaining({
        headers: expect.objectContaining({ "X-User-Id": expect.any(String) }),
      }),
    );
  });

  it("creates an account in the active workspace", async () => {
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
      .mockResolvedValueOnce(new Response("[]", { status: 200 }))
      .mockResolvedValueOnce(
        new Response(
          JSON.stringify({
            id: "55555555-5555-5555-5555-555555555555",
            workspace_id: "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa",
            owner_user_id: null,
            name: "Cash Wallet",
            type: "cash",
            currency_code: "USD",
            institution_name: null,
            masked_number: null,
            opening_balance: "25.50",
            is_active: true,
          }),
          { status: 201, headers: { "Content-Type": "application/json" } },
        ),
      )
      .mockResolvedValueOnce(
        new Response(
          JSON.stringify([
            {
              id: "55555555-5555-5555-5555-555555555555",
              workspace_id: "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa",
              owner_user_id: null,
              name: "Cash Wallet",
              type: "cash",
              currency_code: "USD",
              institution_name: null,
              masked_number: null,
              opening_balance: "25.50",
              is_active: true,
            },
          ]),
          { status: 200, headers: { "Content-Type": "application/json" } },
        ),
      );
    const user = userEvent.setup();
    render(<App />);

    await user.click(screen.getByRole("link", { name: /accounts/i }));
    await user.type(await screen.findByLabelText(/account name/i), " Cash Wallet ");
    await user.selectOptions(screen.getByLabelText(/account type/i), "cash");
    await user.clear(screen.getByLabelText(/currency/i));
    await user.type(screen.getByLabelText(/currency/i), "usd");
    await user.type(screen.getByLabelText(/opening balance/i), "25.50");
    await user.click(screen.getByRole("button", { name: /create account/i }));

    expect(await screen.findByText(/created account Cash Wallet/i)).toBeInTheDocument();
    expect(fetchMock).toHaveBeenNthCalledWith(
      3,
      "/workspaces/aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa/accounts",
      expect.objectContaining({
        method: "POST",
        body: JSON.stringify({
          name: "Cash Wallet",
          type: "cash",
          currency_code: "USD",
          opening_balance: "25.50",
        }),
      }),
    );
  });

  it("lists categories for the active workspace", async () => {
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
              id: "66666666-6666-6666-6666-666666666666",
              workspace_id: "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa",
              parent_id: null,
              name: "Groceries",
              type: "expense",
              color: "#22c55e",
              icon: "cart",
              sort_order: 10,
              is_system: false,
            },
          ]),
          { status: 200, headers: { "Content-Type": "application/json" } },
        ),
      );
    const user = userEvent.setup();
    render(<App />);

    await user.click(screen.getByRole("link", { name: /categories/i }));

    expect(await screen.findByRole("heading", { name: /categories/i })).toBeInTheDocument();
    expect(await screen.findByText("Groceries")).toBeInTheDocument();
    expect(screen.getByText(/expense · #22c55e · cart/i)).toBeInTheDocument();
    expect(fetchMock).toHaveBeenLastCalledWith(
      "/workspaces/aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa/categories",
      expect.objectContaining({
        headers: expect.objectContaining({ "X-User-Id": expect.any(String) }),
      }),
    );
  });

  it("creates a category in the active workspace", async () => {
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
      .mockResolvedValueOnce(new Response("[]", { status: 200 }))
      .mockResolvedValueOnce(
        new Response(
          JSON.stringify({
            id: "77777777-7777-7777-7777-777777777777",
            workspace_id: "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa",
            parent_id: null,
            name: "Salary",
            type: "income",
            color: "#0ea5e9",
            icon: "wallet",
            sort_order: 25,
            is_system: false,
          }),
          { status: 201, headers: { "Content-Type": "application/json" } },
        ),
      )
      .mockResolvedValueOnce(
        new Response(
          JSON.stringify([
            {
              id: "77777777-7777-7777-7777-777777777777",
              workspace_id: "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa",
              parent_id: null,
              name: "Salary",
              type: "income",
              color: "#0ea5e9",
              icon: "wallet",
              sort_order: 25,
              is_system: false,
            },
          ]),
          { status: 200, headers: { "Content-Type": "application/json" } },
        ),
      );
    const user = userEvent.setup();
    render(<App />);

    await user.click(screen.getByRole("link", { name: /categories/i }));
    await user.type(await screen.findByLabelText(/category name/i), " Salary ");
    await user.selectOptions(screen.getByLabelText(/category type/i), "income");
    await user.type(screen.getByLabelText(/color/i), "#0ea5e9");
    await user.type(screen.getByLabelText(/icon/i), " wallet ");
    await user.clear(screen.getByLabelText(/sort order/i));
    await user.type(screen.getByLabelText(/sort order/i), "25");
    await user.click(screen.getByRole("button", { name: /create category/i }));

    expect(await screen.findByText(/created category Salary/i)).toBeInTheDocument();
    expect(fetchMock).toHaveBeenNthCalledWith(
      3,
      "/workspaces/aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa/categories",
      expect.objectContaining({
        method: "POST",
        body: JSON.stringify({
          name: "Salary",
          type: "income",
          color: "#0ea5e9",
          icon: "wallet",
          sort_order: 25,
        }),
      }),
    );
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
