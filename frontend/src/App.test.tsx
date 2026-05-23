import { cleanup, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { App } from "./App";

const TEST_TOKEN = "test-token";
const TEST_USER = {
  id: "00000000-0000-0000-0000-000000000001",
  email: "olga@example.com",
  display_name: "Olga",
  telegram_id: null,
  is_active: true,
};

function authMeResponse() {
  return new Response(JSON.stringify(TEST_USER), { status: 200, headers: { "Content-Type": "application/json" } });
}

beforeEach(() => {
  localStorage.setItem("personal-budget.auth-token", TEST_TOKEN);
});


afterEach(() => {
  cleanup();
  vi.restoreAllMocks();
  localStorage.clear();
  window.history.pushState({}, "", "/");
});

describe("App shell", () => {

  it("shows the login form before loading workspaces when no token is stored", async () => {
    localStorage.clear();
    const fetchMock = vi.spyOn(globalThis, "fetch");

    render(<App />);

    expect(screen.getByRole("heading", { name: /sign in/i })).toBeInTheDocument();
    expect(screen.getByLabelText(/email/i)).toBeInTheDocument();
    expect(screen.getByLabelText(/password/i)).toBeInTheDocument();
    expect(screen.queryByText(/select a workspace/i)).not.toBeInTheDocument();
    await waitFor(() => expect(fetchMock).not.toHaveBeenCalled());
  });

  it("logs in, stores the bearer token, then loads workspaces with Authorization", async () => {
    localStorage.clear();
    const fetchMock = vi
      .spyOn(globalThis, "fetch")
      .mockResolvedValueOnce(
        new Response(
          JSON.stringify({ access_token: TEST_TOKEN, token_type: "bearer", user: TEST_USER }),
          { status: 200, headers: { "Content-Type": "application/json" } },
        ),
      )
      .mockResolvedValueOnce(
        new Response(
          JSON.stringify([
            {
              id: "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa",
              name: "Family Budget",
              kind: "family",
              base_currency_code: "RUB",
              owner_user_id: TEST_USER.id,
            },
          ]),
          { status: 200, headers: { "Content-Type": "application/json" } },
        ),
      );
    const user = userEvent.setup();

    render(<App />);

    await user.type(screen.getByLabelText(/email/i), " olga@example.com ");
    await user.type(screen.getByLabelText(/password/i), "secret-password");
    await user.click(screen.getByRole("button", { name: /sign in/i }));

    expect(await screen.findByText("Family Budget")).toBeInTheDocument();
    expect(localStorage.getItem("personal-budget.auth-token")).toBe(TEST_TOKEN);
    expect(fetchMock).toHaveBeenNthCalledWith(
      1,
      "/auth/login",
      expect.objectContaining({
        method: "POST",
        body: JSON.stringify({ email: "olga@example.com", password: "secret-password" }),
      }),
    );
    expect(fetchMock).toHaveBeenNthCalledWith(
      2,
      "/workspaces",
      expect.objectContaining({ headers: expect.objectContaining({ Authorization: `Bearer ${TEST_TOKEN}` }) }),
    );
  });


  it("registers a new user, stores the bearer token, then loads workspaces", async () => {
    localStorage.clear();
    const fetchMock = vi
      .spyOn(globalThis, "fetch")
      .mockResolvedValueOnce(
        new Response(
          JSON.stringify({ access_token: TEST_TOKEN, token_type: "bearer", user: TEST_USER }),
          { status: 201, headers: { "Content-Type": "application/json" } },
        ),
      )
      .mockResolvedValueOnce(new Response("[]", { status: 200 }));
    const user = userEvent.setup();

    render(<App />);

    await user.click(screen.getByRole("button", { name: /create a new account/i }));
    await user.type(screen.getByLabelText(/email/i), " Olga@Example.com ");
    await user.type(screen.getByLabelText(/display name/i), " Olga ");
    await user.type(screen.getByLabelText(/password/i), "secret-password");
    await user.click(screen.getByRole("button", { name: /^create account$/i }));

    expect(await screen.findByText(/create your first workspace/i)).toBeInTheDocument();
    expect(localStorage.getItem("personal-budget.auth-token")).toBe(TEST_TOKEN);
    expect(fetchMock).toHaveBeenNthCalledWith(
      1,
      "/auth/register",
      expect.objectContaining({
        method: "POST",
        body: JSON.stringify({
          email: "olga@example.com",
          password: "secret-password",
          display_name: "Olga",
        }),
      }),
    );
    expect(fetchMock).toHaveBeenNthCalledWith(
      2,
      "/workspaces",
      expect.objectContaining({ headers: expect.objectContaining({ Authorization: `Bearer ${TEST_TOKEN}` }) }),
    );
  });

  it("creates the first workspace from the onboarding screen", async () => {
    const fetchMock = vi
      .spyOn(globalThis, "fetch")
      .mockResolvedValueOnce(authMeResponse())
      .mockResolvedValueOnce(new Response("[]", { status: 200 }))
      .mockResolvedValueOnce(
        new Response(
          JSON.stringify({
            id: "cccccccc-cccc-cccc-cccc-cccccccccccc",
            name: "Studio Budget",
            kind: "personal",
            base_currency_code: "USD",
            owner_user_id: TEST_USER.id,
          }),
          { status: 201, headers: { "Content-Type": "application/json" } },
        ),
      );
    const user = userEvent.setup();

    render(<App />);

    expect(await screen.findByRole("heading", { name: /create your first workspace/i })).toBeInTheDocument();
    expect(screen.queryByRole("link", { name: /transactions/i })).not.toBeInTheDocument();

    await user.clear(screen.getByLabelText(/workspace name/i));
    await user.type(screen.getByLabelText(/workspace name/i), " Studio Budget ");
    await user.selectOptions(screen.getByLabelText(/workspace type/i), "personal");
    await user.clear(screen.getByLabelText(/base currency/i));
    await user.type(screen.getByLabelText(/base currency/i), " usd ");
    await user.click(screen.getByRole("button", { name: /create workspace/i }));

    expect(await screen.findByText("Studio Budget")).toBeInTheDocument();
    expect(screen.getByText(/personal · usd/i)).toBeInTheDocument();
    expect(screen.getByRole("link", { name: /transactions/i })).toHaveAttribute("href", "/transactions");
    expect(localStorage.getItem("personal-budget.active-workspace-id")).toBe("cccccccc-cccc-cccc-cccc-cccccccccccc");
    expect(fetchMock).toHaveBeenNthCalledWith(
      3,
      "/workspaces",
      expect.objectContaining({
        method: "POST",
        headers: expect.objectContaining({ Authorization: `Bearer ${TEST_TOKEN}` }),
        body: JSON.stringify({
          name: "Studio Budget",
          kind: "personal",
          base_currency_code: "USD",
        }),
      }),
    );
  });

  it("renders the dashboard layout with core personal-budget navigation", async () => {
    vi.spyOn(globalThis, "fetch").mockResolvedValueOnce(authMeResponse()).mockResolvedValueOnce(
      new Response(
        JSON.stringify([
          {
            id: "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa",
            name: "Family Budget",
            kind: "family",
            base_currency_code: "RUB",
            owner_user_id: TEST_USER.id,
          },
        ]),
        { status: 200, headers: { "Content-Type": "application/json" } },
      ),
    );

    render(<App />);

    expect(screen.getByRole("heading", { name: /personal budget/i })).toBeInTheDocument();
    expect(await screen.findByRole("link", { name: /dashboard/i })).toHaveAttribute("href", "/");
    expect(await screen.findByRole("link", { name: /transactions/i })).toHaveAttribute("href", "/transactions");
    expect(await screen.findByRole("link", { name: /accounts/i })).toHaveAttribute("href", "/accounts");
    expect(await screen.findByRole("link", { name: /imports/i })).toHaveAttribute("href", "/imports");
    expect(await screen.findByRole("link", { name: /budgets/i })).toHaveAttribute("href", "/budgets");
    expect(await screen.findByRole("link", { name: /debts/i })).toHaveAttribute("href", "/debts");
    expect(await screen.findByRole("link", { name: /rewards/i })).toHaveAttribute("href", "/rewards");
    expect(await screen.findByText("Family Budget")).toBeInTheDocument();
  });

  it("loads workspaces for the development user and shows the active workspace", async () => {
    const fetchMock = vi.spyOn(globalThis, "fetch").mockResolvedValueOnce(authMeResponse()).mockResolvedValueOnce(
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
          headers: expect.objectContaining({ Authorization: `Bearer ${TEST_TOKEN}` }),
        }),
      ),
    );
  });

  it("lets users switch the active workspace and keeps pages scoped to that workspace", async () => {
    const fetchMock = vi
      .spyOn(globalThis, "fetch")
      .mockResolvedValueOnce(authMeResponse())
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
            {
              id: "bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb",
              name: "Personal Budget",
              kind: "personal",
              base_currency_code: "USD",
              owner_user_id: "11111111-1111-1111-1111-111111111111",
            },
          ]),
          { status: 200, headers: { "Content-Type": "application/json" } },
        ),
      )
      .mockResolvedValueOnce(new Response("[]", { status: 200 }));
    const user = userEvent.setup();

    render(<App />);

    await user.selectOptions(await screen.findByLabelText(/active workspace/i), "bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb");

    expect(screen.getByText(/personal · usd/i)).toBeInTheDocument();
    expect(localStorage.getItem("personal-budget.active-workspace-id")).toBe(
      "bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb",
    );

    await user.click(await screen.findByRole("link", { name: /accounts/i }));

    expect(await screen.findByRole("heading", { name: /accounts/i })).toBeInTheDocument();
    await waitFor(() =>
      expect(fetchMock).toHaveBeenLastCalledWith(
        "/workspaces/bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb/accounts",
        expect.objectContaining({
          headers: expect.objectContaining({ Authorization: `Bearer ${TEST_TOKEN}` }),
        }),
      ),
    );
  });

  it("loads a dashboard overview for the active workspace", async () => {
    const fetchMock = vi
      .spyOn(globalThis, "fetch")
      .mockResolvedValueOnce(authMeResponse())
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
      )
      .mockResolvedValueOnce(
        new Response(
          JSON.stringify([
            {
              id: "66666666-6666-6666-6666-666666666666",
              workspace_id: "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa",
              account_id: "44444444-4444-4444-4444-444444444444",
              user_id: "11111111-1111-1111-1111-111111111111",
              type: "expense",
              status: "posted",
              occurred_at: "2026-05-23T08:30:00Z",
              booked_at: null,
              amount: "-250.50",
              currency_code: "RUB",
              original_amount: null,
              original_currency_code: null,
              base_amount: null,
              base_currency_code: null,
              exchange_rate_id: null,
              exchange_rate: null,
              description: "Groceries",
              merchant_name: "Market",
              merchant_raw: null,
              category_id: null,
              category_confidence: null,
              categorized_by: null,
              notes: null,
              source: "manual",
              external_id: null,
              fingerprint: "tx-1",
              created_at: null,
              updated_at: null,
              deleted_at: null,
              splits: [],
            },
            {
              id: "77777777-7777-7777-7777-777777777777",
              workspace_id: "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa",
              account_id: "44444444-4444-4444-4444-444444444444",
              user_id: "11111111-1111-1111-1111-111111111111",
              type: "income",
              status: "posted",
              occurred_at: "2026-05-22T08:30:00Z",
              booked_at: null,
              amount: "1000.00",
              currency_code: "RUB",
              original_amount: null,
              original_currency_code: null,
              base_amount: null,
              base_currency_code: null,
              exchange_rate_id: null,
              exchange_rate: null,
              description: "Salary",
              merchant_name: null,
              merchant_raw: null,
              category_id: null,
              category_confidence: null,
              categorized_by: null,
              notes: null,
              source: "manual",
              external_id: null,
              fingerprint: "tx-2",
              created_at: null,
              updated_at: null,
              deleted_at: null,
              splits: [],
            },
          ]),
          { status: 200, headers: { "Content-Type": "application/json" } },
        ),
      )
      .mockResolvedValueOnce(new Response(JSON.stringify([]), { status: 200 }))
      .mockResolvedValueOnce(
        new Response(
          JSON.stringify({
            workspace_id: "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa",
            totals: [
              {
                direction: "they_owe_me",
                currency_code: "RUB",
                principal_amount: "300.00",
                paid_amount: "100.00",
                remaining_amount: "200.00",
              },
            ],
          }),
          { status: 200, headers: { "Content-Type": "application/json" } },
        ),
      )
      .mockResolvedValueOnce(new Response(JSON.stringify([]), { status: 200 }));

    render(<App />);

    expect(await screen.findByRole("heading", { name: /dashboard/i })).toBeInTheDocument();
    expect((await screen.findAllByText(/family budget/i)).length).toBeGreaterThan(0);
    expect(screen.getByRole("heading", { name: /accounts/i, level: 3 })).toBeInTheDocument();
    expect(await screen.findByText("749.50 RUB")).toBeInTheDocument();
    expect(screen.getByText("1 active")).toBeInTheDocument();
    expect(screen.getByText(/net cashflow/i)).toBeInTheDocument();
    expect(screen.getByText(/debt remaining/i)).toBeInTheDocument();
    expect(screen.getByText("200.00 RUB")).toBeInTheDocument();
    expect(screen.getByText(/recent transactions/i)).toBeInTheDocument();
    expect(screen.getByText("Groceries")).toBeInTheDocument();
    expect(screen.getByText("Salary")).toBeInTheDocument();
    expect(fetchMock).toHaveBeenCalledWith(
      "/workspaces/aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa/transactions",
      expect.objectContaining({
        headers: expect.objectContaining({ Authorization: `Bearer ${TEST_TOKEN}` }),
      }),
    );
  });

  it("lists accounts for the active workspace", async () => {
    const fetchMock = vi
      .spyOn(globalThis, "fetch")
      .mockResolvedValueOnce(authMeResponse())
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

    await user.click(await screen.findByRole("link", { name: /accounts/i }));

    expect(await screen.findByRole("heading", { name: /accounts/i })).toBeInTheDocument();
    expect(await screen.findByText("Tinkoff Black")).toBeInTheDocument();
    expect(screen.getByText(/bank_card · rub/i)).toBeInTheDocument();
    expect(screen.getByText(/T-Bank · \*1234/i)).toBeInTheDocument();
    expect(fetchMock).toHaveBeenLastCalledWith(
      "/workspaces/aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa/accounts",
      expect.objectContaining({
        headers: expect.objectContaining({ Authorization: `Bearer ${TEST_TOKEN}` }),
      }),
    );
  });

  it("creates an account in the active workspace", async () => {
    const fetchMock = vi
      .spyOn(globalThis, "fetch")
      .mockResolvedValueOnce(authMeResponse())
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

    await user.click(await screen.findByRole("link", { name: /accounts/i }));
    await user.type(await screen.findByLabelText(/account name/i), " Cash Wallet ");
    await user.selectOptions(screen.getByLabelText(/account type/i), "cash");
    await user.clear(screen.getByLabelText(/currency/i));
    await user.type(screen.getByLabelText(/currency/i), "usd");
    await user.type(screen.getByLabelText(/opening balance/i), "25.50");
    await user.click(screen.getByRole("button", { name: /create account/i }));

    expect(await screen.findByText(/created account Cash Wallet/i)).toBeInTheDocument();
    expect(fetchMock).toHaveBeenNthCalledWith(
      4,
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
      .mockResolvedValueOnce(authMeResponse())
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
      )
      .mockResolvedValueOnce(new Response("[]", { status: 200 }));
    const user = userEvent.setup();
    render(<App />);

    await user.click(await screen.findByRole("link", { name: /categories/i }));

    expect(await screen.findByRole("heading", { name: /categories/i })).toBeInTheDocument();
    expect((await screen.findAllByText("Groceries")).length).toBeGreaterThan(0);
    expect(screen.getByText(/expense · #22c55e · cart/i)).toBeInTheDocument();
    expect(fetchMock).toHaveBeenCalledWith(
      "/workspaces/aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa/categories",
      expect.objectContaining({
        headers: expect.objectContaining({ Authorization: `Bearer ${TEST_TOKEN}` }),
      }),
    );
  });

  it("creates a category in the active workspace", async () => {
    const fetchMock = vi
      .spyOn(globalThis, "fetch")
      .mockResolvedValueOnce(authMeResponse())
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

    await user.click(await screen.findByRole("link", { name: /categories/i }));
    await user.type(await screen.findByLabelText(/category name/i), " Salary ");
    await user.selectOptions(screen.getByLabelText(/category type/i), "income");
    await user.type(screen.getByLabelText(/color/i), "#0ea5e9");
    await user.type(screen.getByLabelText(/icon/i), " wallet ");
    await user.clear(screen.getByLabelText(/sort order/i));
    await user.type(screen.getByLabelText(/sort order/i), "25");
    await user.click(screen.getByRole("button", { name: /create category/i }));

    expect(await screen.findByText(/created category Salary/i)).toBeInTheDocument();
    expect(fetchMock).toHaveBeenCalledWith(
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

  it("lists category rules, creates a rule, and applies active rules", async () => {
    const fetchMock = vi
      .spyOn(globalThis, "fetch")
      .mockResolvedValueOnce(authMeResponse())
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
      )
      .mockResolvedValueOnce(
        new Response(
          JSON.stringify([
            {
              id: "12121212-1212-1212-1212-121212121212",
              workspace_id: "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa",
              category_id: "66666666-6666-6666-6666-666666666666",
              name: "Grocery merchants",
              operator: "contains",
              match_field: "merchant_name",
              pattern: "perekrestok",
              amount_min: null,
              amount_max: null,
              priority: 20,
              is_active: true,
              created_at: "2026-05-23T10:00:00Z",
              updated_at: "2026-05-23T10:00:00Z",
            },
          ]),
          { status: 200, headers: { "Content-Type": "application/json" } },
        ),
      )
      .mockResolvedValueOnce(
        new Response(
          JSON.stringify({
            id: "13131313-1313-1313-1313-131313131313",
            workspace_id: "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa",
            category_id: "66666666-6666-6666-6666-666666666666",
            name: "Coffee shops",
            operator: "starts_with",
            match_field: "description",
            pattern: "coffee",
            amount_min: null,
            amount_max: null,
            priority: 30,
            is_active: true,
            created_at: "2026-05-23T10:05:00Z",
            updated_at: "2026-05-23T10:05:00Z",
          }),
          { status: 201, headers: { "Content-Type": "application/json" } },
        ),
      )
      .mockResolvedValueOnce(
        new Response(
          JSON.stringify([
            {
              id: "12121212-1212-1212-1212-121212121212",
              workspace_id: "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa",
              category_id: "66666666-6666-6666-6666-666666666666",
              name: "Grocery merchants",
              operator: "contains",
              match_field: "merchant_name",
              pattern: "perekrestok",
              amount_min: null,
              amount_max: null,
              priority: 20,
              is_active: true,
              created_at: "2026-05-23T10:00:00Z",
              updated_at: "2026-05-23T10:00:00Z",
            },
            {
              id: "13131313-1313-1313-1313-131313131313",
              workspace_id: "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa",
              category_id: "66666666-6666-6666-6666-666666666666",
              name: "Coffee shops",
              operator: "starts_with",
              match_field: "description",
              pattern: "coffee",
              amount_min: null,
              amount_max: null,
              priority: 30,
              is_active: true,
              created_at: "2026-05-23T10:05:00Z",
              updated_at: "2026-05-23T10:05:00Z",
            },
          ]),
          { status: 200, headers: { "Content-Type": "application/json" } },
        ),
      )
      .mockResolvedValueOnce(
        new Response(
          JSON.stringify({
            evaluated_count: 5,
            categorized_count: 2,
            transaction_ids: ["88888888-8888-8888-8888-888888888888"],
          }),
          { status: 200, headers: { "Content-Type": "application/json" } },
        ),
      );
    const user = userEvent.setup();
    render(<App />);

    await user.click(await screen.findByRole("link", { name: /categories/i }));

    expect(await screen.findByText("Grocery merchants")).toBeInTheDocument();
    expect(screen.getByText(/merchant_name · contains · perekrestok/i)).toBeInTheDocument();
    await user.type(await screen.findByLabelText(/rule name/i), " Coffee shops ");
    await user.selectOptions(screen.getByLabelText(/rule category/i), "66666666-6666-6666-6666-666666666666");
    await user.selectOptions(screen.getByLabelText(/match field/i), "description");
    await user.selectOptions(screen.getByLabelText(/operator/i), "starts_with");
    await user.type(screen.getByLabelText(/pattern/i), " coffee ");
    await user.clear(screen.getByLabelText(/priority/i));
    await user.type(screen.getByLabelText(/priority/i), "30");
    await user.click(screen.getByRole("button", { name: /create rule/i }));

    expect(await screen.findByText(/created category rule Coffee shops/i)).toBeInTheDocument();
    expect(fetchMock).toHaveBeenCalledWith(
      "/workspaces/aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa/category-rules",
      expect.objectContaining({
        method: "POST",
        body: JSON.stringify({
          name: "Coffee shops",
          category_id: "66666666-6666-6666-6666-666666666666",
          operator: "starts_with",
          match_field: "description",
          pattern: "coffee",
          priority: 30,
          is_active: true,
        }),
      }),
    );
    expect(await screen.findByText("Coffee shops")).toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: /apply active rules/i }));

    expect(await screen.findByText(/categorized 2 of 5 transactions/i)).toBeInTheDocument();
    expect(fetchMock).toHaveBeenCalledWith(
      "/workspaces/aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa/category-rules/apply",
      expect.objectContaining({ method: "POST" }),
    );
  });

  it("lists transactions with account and category context for the active workspace", async () => {
    const fetchMock = vi
      .spyOn(globalThis, "fetch")
      .mockResolvedValueOnce(authMeResponse())
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
      )
      .mockResolvedValueOnce(
        new Response(
          JSON.stringify([
            {
              id: "88888888-8888-8888-8888-888888888888",
              workspace_id: "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa",
              account_id: "44444444-4444-4444-4444-444444444444",
              user_id: null,
              type: "expense",
              status: "posted",
              occurred_at: "2026-05-22T12:34:00Z",
              booked_at: null,
              amount: "-1250.50",
              currency_code: "RUB",
              original_amount: null,
              original_currency_code: null,
              base_amount: null,
              base_currency_code: null,
              exchange_rate_id: null,
              exchange_rate: null,
              description: "Grocery run",
              merchant_name: "Perekrestok",
              merchant_raw: null,
              category_id: "66666666-6666-6666-6666-666666666666",
              category_confidence: null,
              categorized_by: null,
              notes: null,
              source: "manual",
              external_id: null,
              fingerprint: "fingerprint-1",
              created_at: null,
              updated_at: null,
              deleted_at: null,
              splits: [],
            },
          ]),
          { status: 200, headers: { "Content-Type": "application/json" } },
        ),
      );
    const user = userEvent.setup();
    render(<App />);

    await user.click(await screen.findByRole("link", { name: /transactions/i }));

    expect(await screen.findByRole("heading", { name: /transactions/i })).toBeInTheDocument();
    expect(await screen.findByText("Grocery run")).toBeInTheDocument();
    expect(screen.getByText(/expense · -1250.50 RUB/i)).toBeInTheDocument();
    expect(screen.getByText(/Tinkoff Black · Groceries/i)).toBeInTheDocument();
    expect(fetchMock).toHaveBeenCalledWith(
      "/workspaces/aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa/transactions",
      expect.objectContaining({
        headers: expect.objectContaining({ Authorization: `Bearer ${TEST_TOKEN}` }),
      }),
    );
  });

  it("creates an expense transaction in the active workspace", async () => {
    const fetchMock = vi
      .spyOn(globalThis, "fetch")
      .mockResolvedValueOnce(authMeResponse())
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
      )
      .mockResolvedValueOnce(new Response("[]", { status: 200 }))
      .mockResolvedValueOnce(
        new Response(
          JSON.stringify({
            id: "88888888-8888-8888-8888-888888888888",
            workspace_id: "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa",
            account_id: "44444444-4444-4444-4444-444444444444",
            user_id: null,
            type: "expense",
            status: "posted",
            occurred_at: "2026-05-22T12:34:00Z",
            booked_at: null,
            amount: "-1250.50",
            currency_code: "RUB",
            original_amount: null,
            original_currency_code: null,
            base_amount: null,
            base_currency_code: null,
            exchange_rate_id: null,
            exchange_rate: null,
            description: "Grocery run",
            merchant_name: "Perekrestok",
            merchant_raw: null,
            category_id: "66666666-6666-6666-6666-666666666666",
            category_confidence: null,
            categorized_by: null,
            notes: null,
            source: "manual",
            external_id: null,
            fingerprint: "fingerprint-1",
            created_at: null,
            updated_at: null,
            deleted_at: null,
            splits: [],
          }),
          { status: 201, headers: { "Content-Type": "application/json" } },
        ),
      )
      .mockResolvedValueOnce(new Response("[]", { status: 200 }));
    const user = userEvent.setup();
    render(<App />);

    await user.click(await screen.findByRole("link", { name: /transactions/i }));
    await user.selectOptions(await screen.findByLabelText(/^account$/i), "44444444-4444-4444-4444-444444444444");
    await user.selectOptions(screen.getByLabelText(/transaction type/i), "expense");
    await user.type(screen.getByLabelText(/^description$/i), " Grocery run ");
    await user.type(screen.getByLabelText(/^amount$/i), "1250.50");
    await user.type(screen.getByLabelText(/^occurred at$/i), "2026-05-22T12:34");
    await user.selectOptions(screen.getByLabelText(/category/i), "66666666-6666-6666-6666-666666666666");
    await user.type(screen.getByLabelText(/merchant/i), " Perekrestok ");
    await user.click(screen.getByRole("button", { name: /create transaction/i }));

    expect(await screen.findByText(/created transaction Grocery run/i)).toBeInTheDocument();
    expect(fetchMock).toHaveBeenNthCalledWith(
      6,
      "/workspaces/aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa/transactions",
      expect.objectContaining({
        method: "POST",
        body: JSON.stringify({
          account_id: "44444444-4444-4444-4444-444444444444",
          type: "expense",
          occurred_at: "2026-05-22T12:34:00.000Z",
          amount: "-1250.50",
          currency_code: "RUB",
          description: "Grocery run",
          category_id: "66666666-6666-6666-6666-666666666666",
          merchant_name: "Perekrestok",
        }),
      }),
    );
  });

  it("creates a transfer between two accounts", async () => {
    const fetchMock = vi
      .spyOn(globalThis, "fetch")
      .mockResolvedValueOnce(authMeResponse())
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
            {
              id: "55555555-5555-5555-5555-555555555555",
              workspace_id: "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa",
              owner_user_id: null,
              name: "Savings",
              type: "bank_account",
              currency_code: "RUB",
              institution_name: "T-Bank",
              masked_number: null,
              opening_balance: "10000.00",
              is_active: true,
            },
          ]),
          { status: 200, headers: { "Content-Type": "application/json" } },
        ),
      )
      .mockResolvedValueOnce(new Response("[]", { status: 200 }))
      .mockResolvedValueOnce(new Response("[]", { status: 200 }))
      .mockResolvedValueOnce(
        new Response(
          JSON.stringify({
            outflow: {
              id: "88888888-8888-8888-8888-888888888888",
              workspace_id: "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa",
              account_id: "44444444-4444-4444-4444-444444444444",
              user_id: null,
              type: "transfer",
              status: "posted",
              occurred_at: "2026-05-22T12:34:00Z",
              booked_at: null,
              amount: "-5000.000000",
              currency_code: "RUB",
              original_amount: null,
              original_currency_code: null,
              base_amount: null,
              base_currency_code: null,
              exchange_rate_id: null,
              exchange_rate: null,
              description: "Move to savings",
              merchant_name: null,
              merchant_raw: null,
              category_id: null,
              category_confidence: null,
              categorized_by: null,
              notes: "monthly saving",
              source: "manual",
              external_id: null,
              fingerprint: "transfer-out",
              created_at: null,
              updated_at: null,
              deleted_at: null,
              splits: [],
            },
            inflow: {
              id: "99999999-9999-9999-9999-999999999999",
              workspace_id: "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa",
              account_id: "55555555-5555-5555-5555-555555555555",
              user_id: null,
              type: "transfer",
              status: "posted",
              occurred_at: "2026-05-22T12:34:00Z",
              booked_at: null,
              amount: "5000.000000",
              currency_code: "RUB",
              original_amount: null,
              original_currency_code: null,
              base_amount: null,
              base_currency_code: null,
              exchange_rate_id: null,
              exchange_rate: null,
              description: "Move to savings",
              merchant_name: null,
              merchant_raw: null,
              category_id: null,
              category_confidence: null,
              categorized_by: null,
              notes: "monthly saving",
              source: "manual",
              external_id: null,
              fingerprint: "transfer-in",
              created_at: null,
              updated_at: null,
              deleted_at: null,
              splits: [],
            },
            link_id: "77777777-7777-7777-7777-777777777777",
          }),
          { status: 201, headers: { "Content-Type": "application/json" } },
        ),
      )
      .mockResolvedValueOnce(
        new Response(
          JSON.stringify([
            {
              id: "88888888-8888-8888-8888-888888888888",
              workspace_id: "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa",
              account_id: "44444444-4444-4444-4444-444444444444",
              user_id: null,
              type: "transfer",
              status: "posted",
              occurred_at: "2026-05-22T12:34:00Z",
              booked_at: null,
              amount: "-5000.000000",
              currency_code: "RUB",
              original_amount: null,
              original_currency_code: null,
              base_amount: null,
              base_currency_code: null,
              exchange_rate_id: null,
              exchange_rate: null,
              description: "Move to savings",
              merchant_name: null,
              merchant_raw: null,
              category_id: null,
              category_confidence: null,
              categorized_by: null,
              notes: "monthly saving",
              source: "manual",
              external_id: null,
              fingerprint: "transfer-out",
              created_at: null,
              updated_at: null,
              deleted_at: null,
              splits: [],
            },
          ]),
          { status: 200, headers: { "Content-Type": "application/json" } },
        ),
      );
    const user = userEvent.setup();
    render(<App />);

    await user.click(await screen.findByRole("link", { name: /transactions/i }));
    await user.selectOptions(await screen.findByLabelText(/source account/i), "44444444-4444-4444-4444-444444444444");
    await user.selectOptions(screen.getByLabelText(/destination account/i), "55555555-5555-5555-5555-555555555555");
    await user.type(screen.getByLabelText(/transfer description/i), " Move to savings ");
    await user.type(screen.getByLabelText(/transfer amount/i), "5000");
    await user.type(screen.getByLabelText(/transfer occurred at/i), "2026-05-22T12:34");
    await user.type(screen.getByLabelText(/transfer notes/i), " monthly saving ");
    await user.click(screen.getByRole("button", { name: /create transfer/i }));

    expect(await screen.findByText(/created transfer Move to savings/i)).toBeInTheDocument();
    expect(fetchMock).toHaveBeenCalledWith(
      "/workspaces/aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa/transactions/transfers",
      expect.objectContaining({
        method: "POST",
        body: JSON.stringify({
          from_account_id: "44444444-4444-4444-4444-444444444444",
          to_account_id: "55555555-5555-5555-5555-555555555555",
          occurred_at: "2026-05-22T12:34:00.000Z",
          from_amount: "5000",
          from_currency_code: "RUB",
          description: "Move to savings",
          notes: "monthly saving",
        }),
      }),
    );
  });

  it("lists budgets for the active workspace", async () => {
    const fetchMock = vi
      .spyOn(globalThis, "fetch")
      .mockResolvedValueOnce(authMeResponse())
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
              id: "99999999-9999-9999-9999-999999999999",
              workspace_id: "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa",
              name: "May 2026 Budget",
              period_type: "monthly",
              period_start: "2026-05-01",
              period_end: "2026-05-31",
              currency_code: "RUB",
              is_active: true,
              created_at: null,
              updated_at: null,
            },
          ]),
          { status: 200, headers: { "Content-Type": "application/json" } },
        ),
      )
      .mockResolvedValueOnce(new Response("[]", { status: 200 }));
    const user = userEvent.setup();
    render(<App />);

    await user.click(await screen.findByRole("link", { name: /budgets/i }));

    expect(await screen.findByRole("heading", { name: /budgets/i })).toBeInTheDocument();
    expect(await screen.findByText("May 2026 Budget")).toBeInTheDocument();
    expect(screen.getByText(/monthly · 2026-05-01 → 2026-05-31/i)).toBeInTheDocument();
    expect(screen.getByText(/RUB · active/i)).toBeInTheDocument();
    expect(fetchMock).toHaveBeenCalledWith(
      "/workspaces/aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa/budgets",
      expect.objectContaining({
        headers: expect.objectContaining({ Authorization: `Bearer ${TEST_TOKEN}` }),
      }),
    );
  });

  it("creates a budget in the active workspace", async () => {
    const fetchMock = vi
      .spyOn(globalThis, "fetch")
      .mockResolvedValueOnce(authMeResponse())
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
      .mockResolvedValueOnce(new Response("[]", { status: 200 }))
      .mockResolvedValueOnce(
        new Response(
          JSON.stringify({
            id: "99999999-9999-9999-9999-999999999999",
            workspace_id: "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa",
            name: "June 2026 Budget",
            period_type: "monthly",
            period_start: "2026-06-01",
            period_end: "2026-06-30",
            currency_code: "USD",
            is_active: true,
            created_at: null,
            updated_at: null,
          }),
          { status: 201, headers: { "Content-Type": "application/json" } },
        ),
      )
      .mockResolvedValueOnce(new Response("[]", { status: 200 }));
    const user = userEvent.setup();
    render(<App />);

    await user.click(await screen.findByRole("link", { name: /budgets/i }));
    await user.type(await screen.findByLabelText(/budget name/i), " June 2026 Budget ");
    await user.type(screen.getByLabelText(/period start/i), "2026-06-01");
    await user.type(screen.getByLabelText(/period end/i), "2026-06-30");
    await user.clear(screen.getByLabelText(/budget currency/i));
    await user.type(screen.getByLabelText(/budget currency/i), "usd");
    await user.click(screen.getByRole("button", { name: /create budget/i }));

    expect(await screen.findByText(/created budget June 2026 Budget/i)).toBeInTheDocument();
    expect(fetchMock).toHaveBeenNthCalledWith(
      5,
      "/workspaces/aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa/budgets",
      expect.objectContaining({
        method: "POST",
        body: JSON.stringify({
          name: "June 2026 Budget",
          period_type: "monthly",
          period_start: "2026-06-01",
          period_end: "2026-06-30",
          currency_code: "USD",
          is_active: true,
        }),
      }),
    );
  });

  it("shows budget progress and creates a category limit", async () => {
    const fetchMock = vi
      .spyOn(globalThis, "fetch")
      .mockResolvedValueOnce(authMeResponse())
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
              id: "99999999-9999-9999-9999-999999999999",
              workspace_id: "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa",
              name: "May 2026 Budget",
              period_type: "monthly",
              period_start: "2026-05-01",
              period_end: "2026-05-31",
              currency_code: "RUB",
              is_active: true,
              created_at: null,
              updated_at: null,
            },
          ]),
          { status: 200, headers: { "Content-Type": "application/json" } },
        ),
      )
      .mockResolvedValueOnce(
        new Response(
          JSON.stringify([
            {
              id: "77777777-7777-7777-7777-777777777777",
              workspace_id: "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa",
              parent_id: null,
              name: "Groceries",
              type: "expense",
              color: null,
              icon: null,
              sort_order: 0,
              is_system: false,
            },
          ]),
          { status: 200, headers: { "Content-Type": "application/json" } },
        ),
      )
      .mockResolvedValueOnce(
        new Response(
          JSON.stringify({
            budget_id: "99999999-9999-9999-9999-999999999999",
            period_start: "2026-05-01",
            period_end: "2026-05-31",
            currency_code: "RUB",
            total_limit: "10000.000000",
            total_spent: "2500.000000",
            total_remaining: "7500.000000",
            limits: [
              {
                category_id: "77777777-7777-7777-7777-777777777777",
                limit_amount: "10000.000000",
                spent_amount: "2500.000000",
                remaining_amount: "7500.000000",
                percent_used: "25.00",
                currency_code: "RUB",
              },
            ],
          }),
          { status: 200, headers: { "Content-Type": "application/json" } },
        ),
      )
      .mockResolvedValueOnce(
        new Response(
          JSON.stringify({
            id: "88888888-8888-8888-8888-888888888888",
            budget_id: "99999999-9999-9999-9999-999999999999",
            category_id: "77777777-7777-7777-7777-777777777777",
            amount: "12000.000000",
            currency_code: "RUB",
            rollover: false,
            created_at: null,
            updated_at: null,
          }),
          { status: 201, headers: { "Content-Type": "application/json" } },
        ),
      )
      .mockResolvedValueOnce(
        new Response(
          JSON.stringify({
            budget_id: "99999999-9999-9999-9999-999999999999",
            period_start: "2026-05-01",
            period_end: "2026-05-31",
            currency_code: "RUB",
            total_limit: "12000.000000",
            total_spent: "2500.000000",
            total_remaining: "9500.000000",
            limits: [
              {
                category_id: "77777777-7777-7777-7777-777777777777",
                limit_amount: "12000.000000",
                spent_amount: "2500.000000",
                remaining_amount: "9500.000000",
                percent_used: "20.83",
                currency_code: "RUB",
              },
            ],
          }),
          { status: 200, headers: { "Content-Type": "application/json" } },
        ),
      );
    const user = userEvent.setup();
    render(<App />);

    await user.click(await screen.findByRole("link", { name: /budgets/i }));

    expect(await screen.findByText(/Total limit: 10000.000000 RUB/i)).toBeInTheDocument();
    expect(screen.getByText(/Groceries: 2500.000000 spent of 10000.000000 RUB/i)).toBeInTheDocument();

    await user.selectOptions(screen.getByLabelText(/limit category/i), "77777777-7777-7777-7777-777777777777");
    await user.clear(screen.getByLabelText(/limit amount/i));
    await user.type(screen.getByLabelText(/limit amount/i), "12000");
    await user.clear(screen.getByLabelText(/limit currency/i));
    await user.type(screen.getByLabelText(/limit currency/i), "rub");
    await user.click(screen.getByRole("button", { name: /add budget limit/i }));

    expect(await screen.findByText(/created budget limit for Groceries/i)).toBeInTheDocument();
    expect(await screen.findByText(/Total limit: 12000.000000 RUB/i)).toBeInTheDocument();
    expect(fetchMock).toHaveBeenCalledWith(
      "/budgets/99999999-9999-9999-9999-999999999999/limits",
      expect.objectContaining({
        method: "POST",
        headers: expect.objectContaining({ Authorization: `Bearer ${TEST_TOKEN}` }),
        body: JSON.stringify({
          category_id: "77777777-7777-7777-7777-777777777777",
          amount: "12000",
          currency_code: "RUB",
          rollover: false,
        }),
      }),
    );
  });

  it("uploads a CSV import and previews normalized rows", async () => {
    const fetchMock = vi
      .spyOn(globalThis, "fetch")
      .mockResolvedValueOnce(authMeResponse())
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
      )
      .mockResolvedValueOnce(
        new Response(
          JSON.stringify({
            id: "bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb",
            workspace_id: "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa",
            user_id: "00000000-0000-0000-0000-000000000001",
            account_id: "44444444-4444-4444-4444-444444444444",
            file_id: "cccccccc-cccc-cccc-cccc-cccccccccccc",
            source_type: "csv",
            source_name: "T-Bank",
            original_filename: "statement.csv",
            file_hash: "hash-1",
            file_size: 72,
            status: "parsed",
            total_rows: 1,
            imported_count: 0,
            duplicate_count: 0,
            error_count: 0,
            parser_version: "csv-v1",
            uploaded_at: null,
            processed_at: null,
          }),
          { status: 201, headers: { "Content-Type": "application/json" } },
        ),
      )
      .mockResolvedValueOnce(
        new Response(
          JSON.stringify([
            {
              id: "dddddddd-dddd-dddd-dddd-dddddddddddd",
              import_batch_id: "bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb",
              workspace_id: "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa",
              row_number: 1,
              raw_data: { Date: "2026-05-21", Amount: "-12.34", Currency: "rub", Description: "Lunch" },
              normalized_data: {
                type: "expense",
                occurred_at: "2026-05-21T00:00:00+00:00",
                amount: "-12.34",
                currency_code: "RUB",
                description: "Lunch",
              },
              raw_hash: "raw-hash",
              normalized_hash: "normalized-hash",
              status: "pending",
              error_message: null,
              transaction_id: null,
              created_at: null,
            },
          ]),
          { status: 200, headers: { "Content-Type": "application/json" } },
        ),
      );
    const user = userEvent.setup();
    render(<App />);

    await user.click(await screen.findByRole("link", { name: /imports/i }));
    await user.selectOptions(await screen.findByLabelText(/target account/i), "44444444-4444-4444-4444-444444444444");
    await user.type(screen.getByLabelText(/source name/i), " T-Bank ");
    await user.type(screen.getByLabelText(/original filename/i), "statement.csv");
    await user.type(
      screen.getByLabelText(/csv content/i),
      "Date,Amount,Currency,Description{enter}2026-05-21,-12.34,rub,Lunch",
    );
    await user.click(screen.getByRole("button", { name: /upload import/i }));

    expect(await screen.findByText(/uploaded import statement.csv/i)).toBeInTheDocument();
    expect(await screen.findByText("Lunch")).toBeInTheDocument();
    expect(screen.getByText(/expense · -12.34 RUB · pending/i)).toBeInTheDocument();
    expect(fetchMock).toHaveBeenNthCalledWith(
      4,
      "/workspaces/aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa/imports/upload",
      expect.objectContaining({
        method: "POST",
        body: JSON.stringify({
          user_id: "00000000-0000-0000-0000-000000000001",
          account_id: "44444444-4444-4444-4444-444444444444",
          original_filename: "statement.csv",
          content: "Date,Amount,Currency,Description\n2026-05-21,-12.34,rub,Lunch",
          source_name: "T-Bank",
          column_mapping: {
            occurred_at: "Date",
            amount: "Amount",
            currency_code: "Currency",
            description: "Description",
          },
        }),
      }),
    );
  });

  it("confirms an uploaded import batch", async () => {
    const fetchMock = vi
      .spyOn(globalThis, "fetch")
      .mockResolvedValueOnce(authMeResponse())
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
      )
      .mockResolvedValueOnce(
        new Response(
          JSON.stringify({
            id: "bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb",
            workspace_id: "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa",
            user_id: "00000000-0000-0000-0000-000000000001",
            account_id: "44444444-4444-4444-4444-444444444444",
            file_id: null,
            source_type: "csv",
            source_name: null,
            original_filename: "statement.csv",
            file_hash: "hash-1",
            file_size: 72,
            status: "parsed",
            total_rows: 1,
            imported_count: 0,
            duplicate_count: 0,
            error_count: 0,
            parser_version: "csv-v1",
            uploaded_at: null,
            processed_at: null,
          }),
          { status: 201, headers: { "Content-Type": "application/json" } },
        ),
      )
      .mockResolvedValueOnce(new Response("[]", { status: 200 }))
      .mockResolvedValueOnce(
        new Response(
          JSON.stringify({
            import_batch_id: "bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb",
            imported_count: 1,
            duplicate_count: 0,
            error_count: 0,
            transaction_ids: ["88888888-8888-8888-8888-888888888888"],
          }),
          { status: 200, headers: { "Content-Type": "application/json" } },
        ),
      );
    const user = userEvent.setup();
    render(<App />);

    await user.click(await screen.findByRole("link", { name: /imports/i }));
    await user.selectOptions(await screen.findByLabelText(/target account/i), "44444444-4444-4444-4444-444444444444");
    await user.type(screen.getByLabelText(/original filename/i), "statement.csv");
    await user.type(screen.getByLabelText(/csv content/i), "Date,Amount,Currency,Description{enter}2026-05-21,-12.34,rub,Lunch");
    await user.click(screen.getByRole("button", { name: /upload import/i }));
    await user.click(await screen.findByRole("button", { name: /confirm import/i }));

    expect(await screen.findByText(/confirmed import: 1 imported, 0 duplicates, 0 errors/i)).toBeInTheDocument();
    expect(fetchMock).toHaveBeenNthCalledWith(
      6,
      "/workspaces/aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa/imports/bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb/confirm",
      expect.objectContaining({ method: "POST", body: JSON.stringify({}) }),
    );
  });

  it("lists debts and the workspace debt summary", async () => {
    const fetchMock = vi
      .spyOn(globalThis, "fetch")
      .mockResolvedValueOnce(authMeResponse())
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
              id: "eeeeeeee-eeee-eeee-eeee-eeeeeeeeeeee",
              workspace_id: "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa",
              contact_id: "cccccccc-cccc-cccc-cccc-cccccccccccc",
              direction: "they_owe_me",
              status: "open",
              principal_amount: "5000.00",
              currency_code: "RUB",
              description: "Loan to Ivan",
              due_date: "2026-06-15",
              source_transaction_id: null,
              opened_at: "2026-05-20T10:00:00Z",
              closed_at: null,
              created_at: null,
              updated_at: null,
              payments: [],
            },
          ]),
          { status: 200, headers: { "Content-Type": "application/json" } },
        ),
      )
      .mockResolvedValueOnce(
        new Response(
          JSON.stringify({
            workspace_id: "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa",
            totals: [
              {
                direction: "they_owe_me",
                currency_code: "RUB",
                principal_amount: "5000.00",
                paid_amount: "0.00",
                remaining_amount: "5000.00",
              },
            ],
          }),
          { status: 200, headers: { "Content-Type": "application/json" } },
        ),
      );
    const user = userEvent.setup();
    render(<App />);

    await user.click(await screen.findByRole("link", { name: /debts/i }));

    expect(await screen.findByRole("heading", { name: /debts/i })).toBeInTheDocument();
    expect(await screen.findByText("Loan to Ivan")).toBeInTheDocument();
    expect(screen.getByText(/they_owe_me · 5000.00 RUB · open/i)).toBeInTheDocument();
    expect(screen.getByText(/remaining: 5000.00 RUB/i)).toBeInTheDocument();
    expect(fetchMock).toHaveBeenCalledWith(
      "/workspaces/aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa/debts",
      expect.objectContaining({
        headers: expect.objectContaining({ Authorization: `Bearer ${TEST_TOKEN}` }),
      }),
    );
    expect(fetchMock).toHaveBeenCalledWith(
      "/workspaces/aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa/debts/summary",
      expect.objectContaining({
        headers: expect.objectContaining({ Authorization: `Bearer ${TEST_TOKEN}` }),
      }),
    );
  });

  it("creates a debt with a new contact in the active workspace", async () => {
    const fetchMock = vi
      .spyOn(globalThis, "fetch")
      .mockResolvedValueOnce(authMeResponse())
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
          JSON.stringify({ workspace_id: "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa", totals: [] }),
          { status: 200, headers: { "Content-Type": "application/json" } },
        ),
      )
      .mockResolvedValueOnce(
        new Response(
          JSON.stringify({
            id: "eeeeeeee-eeee-eeee-eeee-eeeeeeeeeeee",
            workspace_id: "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa",
            contact_id: "cccccccc-cccc-cccc-cccc-cccccccccccc",
            direction: "i_owe_them",
            status: "open",
            principal_amount: "1200.00",
            currency_code: "USD",
            description: "Borrowed for dinner",
            due_date: "2026-06-30",
            source_transaction_id: null,
            opened_at: "2026-05-20T10:00:00Z",
            closed_at: null,
            created_at: null,
            updated_at: null,
            payments: [],
          }),
          { status: 201, headers: { "Content-Type": "application/json" } },
        ),
      )
      .mockResolvedValueOnce(
        new Response(
          JSON.stringify([
            {
              id: "eeeeeeee-eeee-eeee-eeee-eeeeeeeeeeee",
              workspace_id: "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa",
              contact_id: "cccccccc-cccc-cccc-cccc-cccccccccccc",
              direction: "i_owe_them",
              status: "open",
              principal_amount: "1200.00",
              currency_code: "USD",
              description: "Borrowed for dinner",
              due_date: "2026-06-30",
              source_transaction_id: null,
              opened_at: "2026-05-20T10:00:00Z",
              closed_at: null,
              created_at: null,
              updated_at: null,
              payments: [],
            },
          ]),
          { status: 200, headers: { "Content-Type": "application/json" } },
        ),
      )
      .mockResolvedValueOnce(
        new Response(
          JSON.stringify({
            workspace_id: "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa",
            totals: [
              {
                direction: "i_owe_them",
                currency_code: "USD",
                principal_amount: "1200.00",
                paid_amount: "0.00",
                remaining_amount: "1200.00",
              },
            ],
          }),
          { status: 200, headers: { "Content-Type": "application/json" } },
        ),
      );
    const user = userEvent.setup();
    render(<App />);

    await user.click(await screen.findByRole("link", { name: /debts/i }));
    await user.type(await screen.findByLabelText(/contact name/i), " Ivan ");
    await user.selectOptions(screen.getByLabelText(/debt direction/i), "i_owe_them");
    await user.type(screen.getByLabelText(/principal amount/i), "1200.00");
    await user.clear(screen.getByLabelText(/debt currency/i));
    await user.type(screen.getByLabelText(/debt currency/i), "usd");
    await user.type(screen.getByLabelText(/debt description/i), " Borrowed for dinner ");
    await user.type(screen.getByLabelText(/due date/i), "2026-06-30");
    await user.click(screen.getByRole("button", { name: /create debt/i }));

    expect(await screen.findByText(/created debt Borrowed for dinner/i)).toBeInTheDocument();
    expect(fetchMock).toHaveBeenNthCalledWith(
      5,
      "/workspaces/aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa/debts",
      expect.objectContaining({
        method: "POST",
        body: JSON.stringify({
          contact_name: "Ivan",
          direction: "i_owe_them",
          principal_amount: "1200.00",
          currency_code: "USD",
          description: "Borrowed for dinner",
          due_date: "2026-06-30",
        }),
      }),
    );
  });

  it("lists reward programs and events for the active workspace", async () => {
    const fetchMock = vi
      .spyOn(globalThis, "fetch")
      .mockResolvedValueOnce(authMeResponse())
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
              id: "99999999-9999-9999-9999-999999999999",
              workspace_id: "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa",
              name: "T-Bank Cashback",
              program_type: "cashback",
              currency_code: "RUB",
              issuer_name: "T-Bank",
              is_active: true,
              notes: "Black card",
              created_at: null,
              updated_at: null,
            },
          ]),
          { status: 200, headers: { "Content-Type": "application/json" } },
        ),
      )
      .mockResolvedValueOnce(
        new Response(
          JSON.stringify([
            {
              id: "88888888-8888-8888-8888-888888888888",
              workspace_id: "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa",
              program_id: "99999999-9999-9999-9999-999999999999",
              cashback_rule_id: null,
              source_transaction_id: null,
              reward_transaction_id: null,
              event_type: "earned",
              status: "posted",
              reward_kind: "cashback",
              amount: "125.50",
              currency_code: "RUB",
              occurred_at: "2026-05-20T10:00:00Z",
              description: "May cashback",
              notes: "posted",
              created_at: null,
              updated_at: null,
            },
          ]),
          { status: 200, headers: { "Content-Type": "application/json" } },
        ),
      );
    const user = userEvent.setup();
    render(<App />);

    await user.click(await screen.findByRole("link", { name: /rewards/i }));

    expect(await screen.findByRole("heading", { name: /rewards/i })).toBeInTheDocument();
    expect((await screen.findAllByText("T-Bank Cashback")).length).toBeGreaterThan(0);
    expect(screen.getByText(/cashback · RUB · active/i)).toBeInTheDocument();
    expect(screen.getByText("May cashback")).toBeInTheDocument();
    expect(screen.getByText(/earned · posted · 125.50 RUB/i)).toBeInTheDocument();
    expect(fetchMock).toHaveBeenCalledWith(
      "/workspaces/aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa/rewards/programs",
      expect.objectContaining({
        headers: expect.objectContaining({ Authorization: `Bearer ${TEST_TOKEN}` }),
      }),
    );
    expect(fetchMock).toHaveBeenCalledWith(
      "/workspaces/aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa/rewards/events",
      expect.objectContaining({
        headers: expect.objectContaining({ Authorization: `Bearer ${TEST_TOKEN}` }),
      }),
    );
  });

  it("creates a cashback reward program in the active workspace", async () => {
    const fetchMock = vi
      .spyOn(globalThis, "fetch")
      .mockResolvedValueOnce(authMeResponse())
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
      .mockResolvedValueOnce(new Response("[]", { status: 200 }))
      .mockResolvedValueOnce(
        new Response(
          JSON.stringify({
            id: "99999999-9999-9999-9999-999999999999",
            workspace_id: "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa",
            name: "T-Bank Cashback",
            program_type: "cashback",
            currency_code: "USD",
            issuer_name: "T-Bank",
            is_active: true,
            notes: "Black card",
            created_at: null,
            updated_at: null,
          }),
          { status: 201, headers: { "Content-Type": "application/json" } },
        ),
      )
      .mockResolvedValueOnce(
        new Response(
          JSON.stringify([
            {
              id: "99999999-9999-9999-9999-999999999999",
              workspace_id: "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa",
              name: "T-Bank Cashback",
              program_type: "cashback",
              currency_code: "USD",
              issuer_name: "T-Bank",
              is_active: true,
              notes: "Black card",
              created_at: null,
              updated_at: null,
            },
          ]),
          { status: 200, headers: { "Content-Type": "application/json" } },
        ),
      );
    const user = userEvent.setup();
    render(<App />);

    await user.click(await screen.findByRole("link", { name: /rewards/i }));
    await user.type(await screen.findByLabelText(/program name/i), " T-Bank Cashback ");
    await user.selectOptions(screen.getByLabelText(/program type/i), "cashback");
    await user.clear(screen.getByLabelText(/reward currency/i));
    await user.type(screen.getByLabelText(/reward currency/i), "usd");
    await user.type(screen.getByLabelText(/issuer name/i), " T-Bank ");
    await user.type(screen.getByLabelText(/program notes/i), " Black card ");
    await user.click(screen.getByRole("button", { name: /create reward program/i }));

    expect(await screen.findByText(/created reward program T-Bank Cashback/i)).toBeInTheDocument();
    expect(fetchMock).toHaveBeenNthCalledWith(
      5,
      "/workspaces/aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa/rewards/programs",
      expect.objectContaining({
        method: "POST",
        body: JSON.stringify({
          name: "T-Bank Cashback",
          program_type: "cashback",
          currency_code: "USD",
          issuer_name: "T-Bank",
          is_active: true,
          notes: "Black card",
        }),
      }),
    );
  });

  it("creates a manual reward event for an existing program", async () => {
    const fetchMock = vi
      .spyOn(globalThis, "fetch")
      .mockResolvedValueOnce(authMeResponse())
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
              id: "99999999-9999-9999-9999-999999999999",
              workspace_id: "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa",
              name: "T-Bank Cashback",
              program_type: "cashback",
              currency_code: "RUB",
              issuer_name: "T-Bank",
              is_active: true,
              notes: null,
              created_at: null,
              updated_at: null,
            },
          ]),
          { status: 200, headers: { "Content-Type": "application/json" } },
        ),
      )
      .mockResolvedValueOnce(new Response("[]", { status: 200 }))
      .mockResolvedValueOnce(
        new Response(
          JSON.stringify({
            id: "88888888-8888-8888-8888-888888888888",
            workspace_id: "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa",
            program_id: "99999999-9999-9999-9999-999999999999",
            cashback_rule_id: null,
            source_transaction_id: null,
            reward_transaction_id: null,
            event_type: "earned",
            status: "posted",
            reward_kind: "cashback",
            amount: "125.50",
            currency_code: "RUB",
            occurred_at: "2026-05-20T10:30:00Z",
            description: "May cashback",
            notes: "posted",
            created_at: null,
            updated_at: null,
          }),
          { status: 201, headers: { "Content-Type": "application/json" } },
        ),
      )
      .mockResolvedValueOnce(
        new Response(
          JSON.stringify([
            {
              id: "88888888-8888-8888-8888-888888888888",
              workspace_id: "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa",
              program_id: "99999999-9999-9999-9999-999999999999",
              cashback_rule_id: null,
              source_transaction_id: null,
              reward_transaction_id: null,
              event_type: "earned",
              status: "posted",
              reward_kind: "cashback",
              amount: "125.50",
              currency_code: "RUB",
              occurred_at: "2026-05-20T10:30:00Z",
              description: "May cashback",
              notes: "posted",
              created_at: null,
              updated_at: null,
            },
          ]),
          { status: 200, headers: { "Content-Type": "application/json" } },
        ),
      );
    const user = userEvent.setup();
    render(<App />);

    await user.click(await screen.findByRole("link", { name: /rewards/i }));
    await user.selectOptions(await screen.findByLabelText(/event program/i), "99999999-9999-9999-9999-999999999999");
    await user.selectOptions(screen.getByLabelText(/event type/i), "earned");
    await user.selectOptions(screen.getByLabelText(/event status/i), "posted");
    await user.type(screen.getByLabelText(/reward amount/i), "125.50");
    await user.type(screen.getByLabelText(/occurred at/i), "2026-05-20T10:30");
    await user.type(screen.getByLabelText(/reward description/i), " May cashback ");
    await user.type(screen.getByLabelText(/reward notes/i), " posted ");
    await user.click(screen.getByRole("button", { name: /create reward event/i }));

    expect(await screen.findByText(/created reward event May cashback/i)).toBeInTheDocument();
    expect(fetchMock).toHaveBeenNthCalledWith(
      5,
      "/workspaces/aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa/rewards/events",
      expect.objectContaining({
        method: "POST",
        body: JSON.stringify({
          program_id: "99999999-9999-9999-9999-999999999999",
          event_type: "earned",
          status: "posted",
          reward_kind: "cashback",
          amount: "125.50",
          currency_code: "RUB",
          occurred_at: "2026-05-20T10:30:00.000Z",
          description: "May cashback",
          notes: "posted",
        }),
      }),
    );
  });

  it("creates a development user from settings", async () => {
    const fetchMock = vi
      .spyOn(globalThis, "fetch")
      .mockResolvedValueOnce(authMeResponse())
      .mockResolvedValueOnce(
        new Response(
          JSON.stringify([
            {
              id: "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa",
              name: "Family Budget",
              kind: "family",
              base_currency_code: "RUB",
              owner_user_id: TEST_USER.id,
            },
          ]),
          { status: 200, headers: { "Content-Type": "application/json" } },
        ),
      )
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

    await user.click(await screen.findByRole("link", { name: /settings/i }));
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
      .mockResolvedValueOnce(authMeResponse())
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

    await user.click(await screen.findByRole("link", { name: /settings/i }));
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

  it("renders a not-found page for unknown routes", async () => {
    vi.spyOn(globalThis, "fetch").mockResolvedValueOnce(authMeResponse()).mockResolvedValueOnce(new Response("[]", { status: 200 }));
    window.history.pushState({}, "", "/missing-page");

    render(<App />);

    expect(await screen.findByRole("heading", { name: /page not found/i })).toBeInTheDocument();
    expect(await screen.findByRole("link", { name: /back to dashboard/i })).toHaveAttribute("href", "/");
  });
});
