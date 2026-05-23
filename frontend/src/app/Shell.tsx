import { Link, Route, Routes } from "react-router-dom";

import { WorkspaceCard } from "../components/WorkspaceCard";
import { AccountsPage } from "../features/accounts/AccountsPage";
import { BudgetsPage } from "../features/budgets/BudgetsPage";
import { CategoriesPage } from "../features/categories/CategoriesPage";
import { DebtsPage } from "../features/debts/DebtsPage";
import { ImportsPage } from "../features/imports/ImportsPage";
import { TransactionsPage } from "../features/transactions/TransactionsPage";
import { FeaturePage } from "../pages/FeaturePage";
import { NotFoundPage } from "../pages/NotFoundPage";
import { SettingsPage } from "../pages/SettingsPage";
import { navigationItems } from "../routes/navigation";
import { useWorkspaces } from "./useWorkspaces";

export function Shell() {
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
          <Route path="imports" element={<ImportsPage activeWorkspace={activeWorkspace} />} />
          <Route path="budgets" element={<BudgetsPage activeWorkspace={activeWorkspace} />} />
          <Route path="debts" element={<DebtsPage activeWorkspace={activeWorkspace} />} />
          <Route path="rewards" element={<FeaturePage title="Rewards" description="Cashback, points, miles, accrual rules, and reward balances." />} />
          <Route path="settings" element={<SettingsPage activeWorkspace={activeWorkspace} />} />
          <Route path="*" element={<NotFoundPage />} />
        </Routes>
      </main>
    </div>
  );
}
