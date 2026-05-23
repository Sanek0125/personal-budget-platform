import { FormEvent, useState } from "react";
import { QueryClient, QueryClientProvider, useQuery, useQueryClient } from "@tanstack/react-query";
import { BrowserRouter, Link, Route, Routes } from "react-router-dom";

import { apiGet, apiPost } from "./api/client";
import "./styles.css";

type NavigationItem = {
  label: string;
  path: string;
};

const navigationItems: NavigationItem[] = [
  { label: "Dashboard", path: "/" },
  { label: "Transactions", path: "/transactions" },
  { label: "Accounts", path: "/accounts" },
  { label: "Categories", path: "/categories" },
  { label: "Imports", path: "/imports" },
  { label: "Budgets", path: "/budgets" },
  { label: "Debts", path: "/debts" },
  { label: "Rewards", path: "/rewards" },
  { label: "Settings", path: "/settings" },
];

type Workspace = {
  id: string;
  name: string;
  kind: "personal" | "family" | "trip" | "other";
  base_currency_code: string;
  owner_user_id: string;
};

type User = {
  id: string;
  email: string | null;
  display_name: string;
  telegram_id: number | null;
  is_active: boolean;
};

type WorkspaceMember = {
  id: string;
  workspace_id: string;
  user_id: string;
  role: "owner" | "admin" | "member" | "viewer";
};

type AccountType = "bank_card" | "cash" | "bank_account" | "bonus" | "investment" | "crypto" | "other";

type Account = {
  id: string;
  workspace_id: string;
  owner_user_id: string | null;
  name: string;
  type: AccountType;
  currency_code: string;
  institution_name: string | null;
  masked_number: string | null;
  opening_balance: string;
  is_active: boolean;
};

type AccountCreatePayload = {
  name: string;
  type: AccountType;
  currency_code: string;
  opening_balance: string;
  institution_name?: string;
  masked_number?: string;
};

type CategoryType = "expense" | "income" | "transfer" | "mixed";

type Category = {
  id: string;
  workspace_id: string;
  parent_id: string | null;
  name: string;
  type: CategoryType;
  color: string | null;
  icon: string | null;
  sort_order: number;
  is_system: boolean;
};

type CategoryCreatePayload = {
  name: string;
  type: CategoryType;
  color?: string;
  icon?: string;
  sort_order: number;
};

type TransactionType = "expense" | "income" | "adjustment" | "transfer";
type ManualTransactionType = "expense" | "income" | "adjustment";

type Transaction = {
  id: string;
  workspace_id: string;
  account_id: string;
  user_id: string | null;
  type: TransactionType;
  status: "posted" | "pending" | "deleted" | "duplicate" | "ignored";
  occurred_at: string;
  booked_at: string | null;
  amount: string;
  currency_code: string;
  original_amount: string | null;
  original_currency_code: string | null;
  base_amount: string | null;
  base_currency_code: string | null;
  exchange_rate_id: string | null;
  exchange_rate: string | null;
  description: string;
  merchant_name: string | null;
  merchant_raw: string | null;
  category_id: string | null;
  category_confidence: string | null;
  categorized_by: string | null;
  notes: string | null;
  source: string;
  external_id: string | null;
  fingerprint: string;
  created_at: string | null;
  updated_at: string | null;
  deleted_at: string | null;
  splits: unknown[];
};

type TransactionCreatePayload = {
  account_id: string;
  type: ManualTransactionType;
  occurred_at: string;
  amount: string;
  currency_code: string;
  description: string;
  category_id?: string;
  merchant_name?: string;
  notes?: string;
};

type WorkspaceQuery = ReturnType<typeof useWorkspaces>;
type AssignableRole = "admin" | "member" | "viewer";

function useWorkspaces() {
  return useQuery({
    queryKey: ["workspaces"],
    queryFn: () => apiGet<Workspace[]>("/workspaces"),
  });
}

function WorkspaceCard({ workspacesQuery }: { workspacesQuery: WorkspaceQuery }) {
  const activeWorkspace = workspacesQuery.data?.[0];

  return (
    <div className="workspace-card">
      <span className="workspace-label">Workspace</span>
      {workspacesQuery.isLoading ? (
        <>
          <strong>Loading workspaces…</strong>
          <p>Using temporary development authentication.</p>
        </>
      ) : activeWorkspace ? (
        <>
          <strong>{activeWorkspace.name}</strong>
          <p>
            {activeWorkspace.kind} · {activeWorkspace.base_currency_code}
          </p>
        </>
      ) : workspacesQuery.isError ? (
        <>
          <strong>Unable to load workspaces</strong>
          <p>Check the backend and development user configuration.</p>
        </>
      ) : (
        <>
          <strong>Select a workspace</strong>
          <p>Personal and family budgets will appear here.</p>
        </>
      )}
    </div>
  );
}

function Shell() {
  const workspacesQuery = useWorkspaces();
  const activeWorkspace = workspacesQuery.data?.[0];

  return (
    <div className="app-shell">
      <aside className="sidebar" aria-label="Main navigation">
        <div className="brand">
          <span className="brand-mark" aria-hidden="true">₽</span>
          <div>
            <p className="eyebrow">Finance OS</p>
            <h1>Personal Budget</h1>
          </div>
        </div>

        <WorkspaceCard workspacesQuery={workspacesQuery} />

        <nav className="nav-list">
          {navigationItems.map((item) => (
            <Link key={item.path} to={item.path}>
              {item.label}
            </Link>
          ))}
        </nav>
      </aside>

      <main className="content">
        <Routes>
          <Route index element={<FeaturePage title="Dashboard" description="Overview cards for spending, income, budgets, debts, rewards, and recent transactions." />} />
          <Route path="transactions" element={<TransactionsPage activeWorkspace={activeWorkspace} />} />
          <Route path="accounts" element={<AccountsPage activeWorkspace={activeWorkspace} />} />
          <Route path="categories" element={<CategoriesPage activeWorkspace={activeWorkspace} />} />
          <Route path="imports" element={<FeaturePage title="Imports" description="Upload CSV, XLSX, or PDF statements, preview rows, and confirm imports." />} />
          <Route path="budgets" element={<FeaturePage title="Budgets" description="Monthly plans, category limits, progress bars, and over-budget warnings." />} />
          <Route path="debts" element={<FeaturePage title="Debts" description="Contacts, debts in both directions, repayments, and balances." />} />
          <Route path="rewards" element={<FeaturePage title="Rewards" description="Cashback, points, miles, accrual rules, and reward balances." />} />
          <Route path="settings" element={<SettingsPage activeWorkspace={activeWorkspace} />} />
          <Route path="*" element={<NotFoundPage />} />
        </Routes>
      </main>
    </div>
  );
}

function normalizeManualAmount(type: ManualTransactionType, amount: string): string {
  const trimmedAmount = amount.trim();
  if (type === "expense") {
    return trimmedAmount.startsWith("-") ? trimmedAmount : `-${trimmedAmount}`;
  }
  if (type === "income") {
    return trimmedAmount.replace(/^-/, "");
  }
  return trimmedAmount;
}

function toApiDateTime(value: string): string {
  if (/^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}$/.test(value)) {
    return `${value}:00.000Z`;
  }
  return new Date(value).toISOString();
}

function TransactionsPage({ activeWorkspace }: { activeWorkspace?: Workspace }) {
  const queryClient = useQueryClient();
  const [accountId, setAccountId] = useState("");
  const [transactionType, setTransactionType] = useState<ManualTransactionType>("expense");
  const [description, setDescription] = useState("");
  const [amount, setAmount] = useState("");
  const [occurredAt, setOccurredAt] = useState("");
  const [categoryId, setCategoryId] = useState("");
  const [merchantName, setMerchantName] = useState("");
  const [notes, setNotes] = useState("");
  const [statusMessage, setStatusMessage] = useState<string | null>(null);

  const accountsQuery = useQuery({
    queryKey: ["accounts", activeWorkspace?.id, "transactions-form"],
    queryFn: () => apiGet<Account[]>(`/workspaces/${activeWorkspace?.id}/accounts`),
    enabled: Boolean(activeWorkspace),
  });
  const categoriesQuery = useQuery({
    queryKey: ["categories", activeWorkspace?.id, "transactions-form"],
    queryFn: () => apiGet<Category[]>(`/workspaces/${activeWorkspace?.id}/categories`),
    enabled: Boolean(activeWorkspace),
  });
  const transactionsQuery = useQuery({
    queryKey: ["transactions", activeWorkspace?.id],
    queryFn: () => apiGet<Transaction[]>(`/workspaces/${activeWorkspace?.id}/transactions`),
    enabled: Boolean(activeWorkspace),
  });

  const accountsById = new Map(accountsQuery.data?.map((account) => [account.id, account]));
  const categoriesById = new Map(categoriesQuery.data?.map((category) => [category.id, category]));
  const selectedAccount = accountsById.get(accountId);

  async function handleCreateTransaction(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!activeWorkspace) {
      setStatusMessage("Select a workspace before creating transactions");
      return;
    }
    if (!selectedAccount) {
      setStatusMessage("Select an account before creating transactions");
      return;
    }

    setStatusMessage(null);
    const payload: TransactionCreatePayload = {
      account_id: selectedAccount.id,
      type: transactionType,
      occurred_at: toApiDateTime(occurredAt),
      amount: normalizeManualAmount(transactionType, amount),
      currency_code: selectedAccount.currency_code,
      description: description.trim(),
      ...(categoryId ? { category_id: categoryId } : {}),
      ...(merchantName.trim() ? { merchant_name: merchantName.trim() } : {}),
      ...(notes.trim() ? { notes: notes.trim() } : {}),
    };

    try {
      const transaction = await apiPost<Transaction, TransactionCreatePayload>(
        `/workspaces/${activeWorkspace.id}/transactions`,
        payload,
      );
      setStatusMessage(`Created transaction ${transaction.description}`);
      setDescription("");
      setAmount("");
      setOccurredAt("");
      setCategoryId("");
      setMerchantName("");
      setNotes("");
      await queryClient.invalidateQueries({ queryKey: ["transactions", activeWorkspace.id] });
    } catch {
      setStatusMessage("Unable to create transaction");
    }
  }

  return (
    <section className="page-card transactions-page">
      <p className="eyebrow">MVP module</p>
      <h2>Transactions</h2>
      <p>Manual expense, income, and adjustment entries for the active workspace.</p>

      <div className="settings-grid">
        <form className="settings-panel" onSubmit={handleCreateTransaction}>
          <h3>Create transaction</h3>
          <p>
            Active workspace: <strong>{activeWorkspace?.name ?? "none"}</strong>
          </p>
          <label>
            Account
            <select value={accountId} onChange={(event) => setAccountId(event.target.value)} required>
              <option value="">Select account</option>
              {accountsQuery.data?.map((account) => (
                <option key={account.id} value={account.id}>
                  {account.name} · {account.currency_code}
                </option>
              ))}
            </select>
          </label>
          <label>
            Transaction type
            <select
              value={transactionType}
              onChange={(event) => setTransactionType(event.target.value as ManualTransactionType)}
            >
              <option value="expense">expense</option>
              <option value="income">income</option>
              <option value="adjustment">adjustment</option>
            </select>
          </label>
          <label>
            Description
            <input value={description} onChange={(event) => setDescription(event.target.value)} minLength={1} required />
          </label>
          <label>
            Amount
            <input inputMode="decimal" value={amount} onChange={(event) => setAmount(event.target.value)} required />
          </label>
          <label>
            Occurred at
            <input
              type="datetime-local"
              value={occurredAt}
              onChange={(event) => setOccurredAt(event.target.value)}
              required
            />
          </label>
          <label>
            Category
            <select value={categoryId} onChange={(event) => setCategoryId(event.target.value)}>
              <option value="">Uncategorized</option>
              {categoriesQuery.data?.map((category) => (
                <option key={category.id} value={category.id}>
                  {category.name} · {category.type}
                </option>
              ))}
            </select>
          </label>
          <label>
            Merchant
            <input value={merchantName} onChange={(event) => setMerchantName(event.target.value)} />
          </label>
          <label>
            Notes
            <input value={notes} onChange={(event) => setNotes(event.target.value)} />
          </label>
          <button type="submit" disabled={!activeWorkspace || !accountsQuery.data?.length}>Create transaction</button>
          {statusMessage ? <p role="status">{statusMessage}</p> : null}
        </form>

        <div className="settings-panel">
          <h3>Transaction list</h3>
          {!activeWorkspace ? <p>Select a workspace to load transactions.</p> : null}
          {accountsQuery.isLoading || categoriesQuery.isLoading || transactionsQuery.isLoading ? (
            <p>Loading transactions…</p>
          ) : null}
          {transactionsQuery.isError ? <p role="alert">Unable to load transactions</p> : null}
          {transactionsQuery.data?.length === 0 ? <p>No transactions yet.</p> : null}
          {transactionsQuery.data?.length ? (
            <ul className="entity-list">
              {transactionsQuery.data.map((transaction) => {
                const account = accountsById.get(transaction.account_id);
                const category = transaction.category_id ? categoriesById.get(transaction.category_id) : undefined;
                return (
                  <li key={transaction.id}>
                    <strong>{transaction.description}</strong>
                    <span>
                      {transaction.type} · {transaction.amount} {transaction.currency_code}
                    </span>
                    <span>{[account?.name ?? transaction.account_id, category?.name ?? "Uncategorized"].join(" · ")}</span>
                    {transaction.merchant_name ? <span>Merchant: {transaction.merchant_name}</span> : null}
                    <span>Occurred: {new Date(transaction.occurred_at).toLocaleString()}</span>
                  </li>
                );
              })}
            </ul>
          ) : null}
        </div>
      </div>
    </section>
  );
}

function AccountsPage({ activeWorkspace }: { activeWorkspace?: Workspace }) {
  const queryClient = useQueryClient();
  const [name, setName] = useState("");
  const [accountType, setAccountType] = useState<AccountType>("bank_card");
  const [currencyCode, setCurrencyCode] = useState(activeWorkspace?.base_currency_code ?? "");
  const [openingBalance, setOpeningBalance] = useState("");
  const [institutionName, setInstitutionName] = useState("");
  const [maskedNumber, setMaskedNumber] = useState("");
  const [statusMessage, setStatusMessage] = useState<string | null>(null);

  const accountsQuery = useQuery({
    queryKey: ["accounts", activeWorkspace?.id],
    queryFn: () => apiGet<Account[]>(`/workspaces/${activeWorkspace?.id}/accounts`),
    enabled: Boolean(activeWorkspace),
  });

  async function handleCreateAccount(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!activeWorkspace) {
      setStatusMessage("Select a workspace before creating accounts");
      return;
    }

    setStatusMessage(null);
    const payload: AccountCreatePayload = {
      name: name.trim(),
      type: accountType,
      currency_code: currencyCode.trim().toUpperCase(),
      opening_balance: openingBalance.trim() || "0",
      ...(institutionName.trim() ? { institution_name: institutionName.trim() } : {}),
      ...(maskedNumber.trim() ? { masked_number: maskedNumber.trim() } : {}),
    };

    try {
      const account = await apiPost<Account, AccountCreatePayload>(
        `/workspaces/${activeWorkspace.id}/accounts`,
        payload,
      );
      setStatusMessage(`Created account ${account.name}`);
      setName("");
      setAccountType("bank_card");
      setCurrencyCode(activeWorkspace.base_currency_code);
      setOpeningBalance("");
      setInstitutionName("");
      setMaskedNumber("");
      await queryClient.invalidateQueries({ queryKey: ["accounts", activeWorkspace.id] });
    } catch {
      setStatusMessage("Unable to create account");
    }
  }

  return (
    <section className="page-card accounts-page">
      <p className="eyebrow">MVP module</p>
      <h2>Accounts</h2>
      <p>Cards, cash wallets, bank accounts, bonus balances, crypto, and investments.</p>

      <div className="settings-grid">
        <form className="settings-panel" onSubmit={handleCreateAccount}>
          <h3>Create account</h3>
          <p>
            Active workspace: <strong>{activeWorkspace?.name ?? "none"}</strong>
          </p>
          <label>
            Account name
            <input value={name} onChange={(event) => setName(event.target.value)} minLength={1} required />
          </label>
          <label>
            Account type
            <select value={accountType} onChange={(event) => setAccountType(event.target.value as AccountType)}>
              <option value="bank_card">bank_card</option>
              <option value="cash">cash</option>
              <option value="bank_account">bank_account</option>
              <option value="bonus">bonus</option>
              <option value="investment">investment</option>
              <option value="crypto">crypto</option>
              <option value="other">other</option>
            </select>
          </label>
          <label>
            Currency
            <input
              value={currencyCode}
              onChange={(event) => setCurrencyCode(event.target.value)}
              placeholder={activeWorkspace?.base_currency_code ?? "RUB"}
              minLength={3}
              maxLength={3}
              required
            />
          </label>
          <label>
            Opening balance
            <input
              inputMode="decimal"
              value={openingBalance}
              onChange={(event) => setOpeningBalance(event.target.value)}
            />
          </label>
          <label>
            Institution name
            <input value={institutionName} onChange={(event) => setInstitutionName(event.target.value)} />
          </label>
          <label>
            Masked number
            <input value={maskedNumber} onChange={(event) => setMaskedNumber(event.target.value)} />
          </label>
          <button type="submit" disabled={!activeWorkspace}>Create account</button>
          {statusMessage ? <p role="status">{statusMessage}</p> : null}
        </form>

        <div className="settings-panel">
          <h3>Account list</h3>
          {!activeWorkspace ? <p>Select a workspace to load accounts.</p> : null}
          {accountsQuery.isLoading ? <p>Loading accounts…</p> : null}
          {accountsQuery.isError ? <p role="alert">Unable to load accounts</p> : null}
          {accountsQuery.data?.length === 0 ? <p>No accounts yet.</p> : null}
          {accountsQuery.data?.length ? (
            <ul className="entity-list">
              {accountsQuery.data.map((account) => (
                <li key={account.id}>
                  <strong>{account.name}</strong>
                  <span>
                    {account.type} · {account.currency_code}
                  </span>
                  {account.institution_name || account.masked_number ? (
                    <span>
                      {[account.institution_name, account.masked_number].filter(Boolean).join(" · ")}
                    </span>
                  ) : null}
                  <span>Opening balance: {account.opening_balance}</span>
                </li>
              ))}
            </ul>
          ) : null}
        </div>
      </div>
    </section>
  );
}

function CategoriesPage({ activeWorkspace }: { activeWorkspace?: Workspace }) {
  const queryClient = useQueryClient();
  const [name, setName] = useState("");
  const [categoryType, setCategoryType] = useState<CategoryType>("expense");
  const [color, setColor] = useState("");
  const [icon, setIcon] = useState("");
  const [sortOrder, setSortOrder] = useState("0");
  const [statusMessage, setStatusMessage] = useState<string | null>(null);

  const categoriesQuery = useQuery({
    queryKey: ["categories", activeWorkspace?.id],
    queryFn: () => apiGet<Category[]>(`/workspaces/${activeWorkspace?.id}/categories`),
    enabled: Boolean(activeWorkspace),
  });

  async function handleCreateCategory(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!activeWorkspace) {
      setStatusMessage("Select a workspace before creating categories");
      return;
    }

    setStatusMessage(null);
    const payload: CategoryCreatePayload = {
      name: name.trim(),
      type: categoryType,
      ...(color.trim() ? { color: color.trim() } : {}),
      ...(icon.trim() ? { icon: icon.trim() } : {}),
      sort_order: Number.parseInt(sortOrder, 10) || 0,
    };

    try {
      const category = await apiPost<Category, CategoryCreatePayload>(
        `/workspaces/${activeWorkspace.id}/categories`,
        payload,
      );
      setStatusMessage(`Created category ${category.name}`);
      setName("");
      setCategoryType("expense");
      setColor("");
      setIcon("");
      setSortOrder("0");
      await queryClient.invalidateQueries({ queryKey: ["categories", activeWorkspace.id] });
    } catch {
      setStatusMessage("Unable to create category");
    }
  }

  return (
    <section className="page-card categories-page">
      <p className="eyebrow">MVP module</p>
      <h2>Categories</h2>
      <p>Hierarchical categories and auto-categorization rules.</p>

      <div className="settings-grid">
        <form className="settings-panel" onSubmit={handleCreateCategory}>
          <h3>Create category</h3>
          <p>
            Active workspace: <strong>{activeWorkspace?.name ?? "none"}</strong>
          </p>
          <label>
            Category name
            <input value={name} onChange={(event) => setName(event.target.value)} minLength={1} required />
          </label>
          <label>
            Category type
            <select value={categoryType} onChange={(event) => setCategoryType(event.target.value as CategoryType)}>
              <option value="expense">expense</option>
              <option value="income">income</option>
              <option value="transfer">transfer</option>
              <option value="mixed">mixed</option>
            </select>
          </label>
          <label>
            Color
            <input value={color} onChange={(event) => setColor(event.target.value)} placeholder="#22c55e" />
          </label>
          <label>
            Icon
            <input value={icon} onChange={(event) => setIcon(event.target.value)} placeholder="cart" />
          </label>
          <label>
            Sort order
            <input
              inputMode="numeric"
              value={sortOrder}
              onChange={(event) => setSortOrder(event.target.value)}
            />
          </label>
          <button type="submit" disabled={!activeWorkspace}>Create category</button>
          {statusMessage ? <p role="status">{statusMessage}</p> : null}
        </form>

        <div className="settings-panel">
          <h3>Category list</h3>
          {!activeWorkspace ? <p>Select a workspace to load categories.</p> : null}
          {categoriesQuery.isLoading ? <p>Loading categories…</p> : null}
          {categoriesQuery.isError ? <p role="alert">Unable to load categories</p> : null}
          {categoriesQuery.data?.length === 0 ? <p>No categories yet.</p> : null}
          {categoriesQuery.data?.length ? (
            <ul className="entity-list">
              {categoriesQuery.data.map((category) => (
                <li key={category.id}>
                  <strong>{category.name}</strong>
                  <span>{[category.type, category.color, category.icon].filter(Boolean).join(" · ")}</span>
                  {category.parent_id ? <span>Parent: {category.parent_id}</span> : null}
                  <span>Sort order: {category.sort_order}</span>
                </li>
              ))}
            </ul>
          ) : null}
        </div>
      </div>
    </section>
  );
}

function SettingsPage({ activeWorkspace }: { activeWorkspace?: Workspace }) {
  const [displayName, setDisplayName] = useState("");
  const [email, setEmail] = useState("");
  const [createdUser, setCreatedUser] = useState<User | null>(null);
  const [createError, setCreateError] = useState<string | null>(null);
  const [lookupEmail, setLookupEmail] = useState("");
  const [lookupUser, setLookupUser] = useState<User | null>(null);
  const [lookupError, setLookupError] = useState<string | null>(null);
  const [role, setRole] = useState<AssignableRole>("member");
  const [memberStatus, setMemberStatus] = useState<string | null>(null);

  async function handleCreateUser(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setCreateError(null);
    setCreatedUser(null);

    const payload = {
      display_name: displayName.trim(),
      ...(email.trim() ? { email: email.trim().toLowerCase() } : {}),
    };

    try {
      const user = await apiPost<User, typeof payload>("/users", payload);
      setCreatedUser(user);
      setDisplayName("");
      setEmail("");
    } catch {
      setCreateError("Unable to create user");
    }
  }

  async function handleFindUser(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setLookupError(null);
    setLookupUser(null);
    setMemberStatus(null);

    const normalizedEmail = lookupEmail.trim().toLowerCase();
    if (!normalizedEmail) {
      setLookupError("Enter an email to find a user");
      return;
    }

    try {
      const users = await apiGet<User[]>(`/users?email=${encodeURIComponent(normalizedEmail)}`);
      const firstUser = users[0];
      if (!firstUser) {
        setLookupError("No user found for this email");
        return;
      }
      setLookupUser(firstUser);
    } catch {
      setLookupError("Unable to find user");
    }
  }

  async function handleAddMember(user: User) {
    if (!activeWorkspace) {
      setMemberStatus("Select a workspace before adding members");
      return;
    }

    try {
      await apiPost<WorkspaceMember, { user_id: string; role: AssignableRole }>(
        `/workspaces/${activeWorkspace.id}/members`,
        { user_id: user.id, role },
      );
      setMemberStatus(`Added ${user.display_name} to ${activeWorkspace.name} as ${role}`);
    } catch {
      setMemberStatus("Unable to add workspace member");
    }
  }

  return (
    <section className="page-card settings-page">
      <p className="eyebrow">Development settings</p>
      <h2>Settings</h2>
      <p>Create local development users and add existing users to the active workspace.</p>

      <div className="settings-grid">
        <form className="settings-panel" onSubmit={handleCreateUser}>
          <h3>Create development user</h3>
          <label>
            Display name
            <input
              value={displayName}
              onChange={(event) => setDisplayName(event.target.value)}
              minLength={1}
              required
            />
          </label>
          <label>
            Email
            <input
              type="email"
              value={email}
              onChange={(event) => setEmail(event.target.value)}
            />
          </label>
          <button type="submit">Create user</button>
          {createdUser ? <p role="status">Created user {createdUser.display_name}</p> : null}
          {createError ? <p role="alert">{createError}</p> : null}
        </form>

        <form className="settings-panel" onSubmit={handleFindUser}>
          <h3>Add workspace member</h3>
          <p>
            Active workspace: <strong>{activeWorkspace?.name ?? "none"}</strong>
          </p>
          <label>
            Find user by email
            <input
              type="email"
              value={lookupEmail}
              onChange={(event) => setLookupEmail(event.target.value)}
              required
            />
          </label>
          <label>
            Workspace role
            <select value={role} onChange={(event) => setRole(event.target.value as AssignableRole)}>
              <option value="admin">admin</option>
              <option value="member">member</option>
              <option value="viewer">viewer</option>
            </select>
          </label>
          <button type="submit">Find user</button>
          {lookupError ? <p role="alert">{lookupError}</p> : null}
          {lookupUser ? (
            <div className="user-result">
              <p>
                Found {lookupUser.display_name} {lookupUser.email ? `(${lookupUser.email})` : ""}
              </p>
              <button type="button" onClick={() => void handleAddMember(lookupUser)}>
                Add {lookupUser.display_name} as {role}
              </button>
            </div>
          ) : null}
          {memberStatus ? <p role="status">{memberStatus}</p> : null}
        </form>
      </div>
    </section>
  );
}

function NotFoundPage() {
  return (
    <section className="page-card">
      <p className="eyebrow">404</p>
      <h2>Page not found</h2>
      <p>This frontend module is not available yet.</p>
      <Link className="primary-link" to="/">
        Back to dashboard
      </Link>
    </section>
  );
}

function FeaturePage({ title, description }: { title: string; description: string }) {
  return (
    <section className="page-card">
      <p className="eyebrow">MVP module</p>
      <h2>{title}</h2>
      <p>{description}</p>
    </section>
  );
}

export function App() {
  const [queryClient] = useState(() => new QueryClient());

  return (
    <QueryClientProvider client={queryClient}>
      <BrowserRouter>
        <Shell />
      </BrowserRouter>
    </QueryClientProvider>
  );
}
