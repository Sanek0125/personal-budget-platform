import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { BrowserRouter, Link, Route, Routes } from "react-router-dom";

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

const queryClient = new QueryClient();

function Shell() {
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

        <div className="workspace-card">
          <span className="workspace-label">Workspace</span>
          <strong>Select a workspace</strong>
          <p>Personal and family budgets will appear here.</p>
        </div>

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
          <Route path="transactions" element={<FeaturePage title="Transactions" description="Manual entries, splits, transfers, and imported operations." />} />
          <Route path="accounts" element={<FeaturePage title="Accounts" description="Cards, cash wallets, bank accounts, bonus balances, crypto, and investments." />} />
          <Route path="categories" element={<FeaturePage title="Categories" description="Hierarchical categories and auto-categorization rules." />} />
          <Route path="imports" element={<FeaturePage title="Imports" description="Upload CSV, XLSX, or PDF statements, preview rows, and confirm imports." />} />
          <Route path="budgets" element={<FeaturePage title="Budgets" description="Monthly plans, category limits, progress bars, and over-budget warnings." />} />
          <Route path="debts" element={<FeaturePage title="Debts" description="Contacts, debts in both directions, repayments, and balances." />} />
          <Route path="rewards" element={<FeaturePage title="Rewards" description="Cashback, points, miles, accrual rules, and reward balances." />} />
          <Route path="settings" element={<FeaturePage title="Settings" description="Workspace, profile, preferences, and integrations." />} />
          <Route path="*" element={<NotFoundPage />} />
        </Routes>
      </main>
    </div>
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
  return (
    <QueryClientProvider client={queryClient}>
      <BrowserRouter>
        <Shell />
      </BrowserRouter>
    </QueryClientProvider>
  );
}
