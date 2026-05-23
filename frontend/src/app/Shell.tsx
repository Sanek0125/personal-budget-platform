import { useState } from "react";
import { useQueryClient } from "@tanstack/react-query";
import { Link, Route, Routes } from "react-router-dom";

import { FirstWorkspaceOnboarding } from "../components/FirstWorkspaceOnboarding";
import { WorkspaceCard } from "../components/WorkspaceCard";
import { AccountsPage } from "../features/accounts/AccountsPage";
import { BudgetsPage } from "../features/budgets/BudgetsPage";
import { CategoriesPage } from "../features/categories/CategoriesPage";
import { DashboardPage } from "../features/dashboard/DashboardPage";
import { DebtsPage } from "../features/debts/DebtsPage";
import { ImportsPage } from "../features/imports/ImportsPage";
import { RewardsPage } from "../features/rewards/RewardsPage";
import { TransactionsPage } from "../features/transactions/TransactionsPage";
import { NotFoundPage } from "../pages/NotFoundPage";
import { SettingsPage } from "../pages/SettingsPage";
import { navigationItems } from "../routes/navigation";
import { useAuth } from "./authContext";
import { useWorkspaces, WORKSPACES_QUERY_KEY } from "./useWorkspaces";
import type { Workspace } from "../types";

const ACTIVE_WORKSPACE_STORAGE_KEY = "personal-budget.active-workspace-id";

function readStoredWorkspaceId() {
  return localStorage.getItem(ACTIVE_WORKSPACE_STORAGE_KEY) ?? undefined;
}

function storeWorkspaceId(workspaceId: string) {
  localStorage.setItem(ACTIVE_WORKSPACE_STORAGE_KEY, workspaceId);
}

export function Shell() {
  const { currentUser, logout } = useAuth();
  const queryClient = useQueryClient();
  const workspacesQuery = useWorkspaces();
  const [selectedWorkspaceId, setSelectedWorkspaceId] = useState(readStoredWorkspaceId);
  const activeWorkspace =
    workspacesQuery.data?.find((workspace) => workspace.id === selectedWorkspaceId) ?? workspacesQuery.data?.[0];
  const shouldShowWorkspaceOnboarding = workspacesQuery.isSuccess && workspacesQuery.data.length === 0;

  function handleWorkspaceChange(workspaceId: string) {
    setSelectedWorkspaceId(workspaceId);
    storeWorkspaceId(workspaceId);
  }

  function handleWorkspaceCreated(workspace: Workspace) {
    queryClient.setQueryData<Workspace[]>(WORKSPACES_QUERY_KEY, (workspaces = []) => [...workspaces, workspace]);
    handleWorkspaceChange(workspace.id);
  }

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

        <div className="auth-summary">
          <span>{currentUser?.display_name}</span>
          <button type="button" onClick={() => void logout()}>
            Sign out
          </button>
        </div>

        <WorkspaceCard
          activeWorkspace={activeWorkspace}
          selectedWorkspaceId={activeWorkspace?.id}
          workspacesQuery={workspacesQuery}
          onWorkspaceChange={handleWorkspaceChange}
        />

        {shouldShowWorkspaceOnboarding ? null : (
          <nav className="nav-list">
            {navigationItems.map((item) => (
              <Link key={item.path} to={item.path}>
                {item.label}
              </Link>
            ))}
          </nav>
        )}
      </aside>

      <main className="content">
        {shouldShowWorkspaceOnboarding && currentUser ? (
          <FirstWorkspaceOnboarding currentUser={currentUser} onWorkspaceCreated={handleWorkspaceCreated} />
        ) : (
          <Routes>
            <Route index element={<DashboardPage activeWorkspace={activeWorkspace} />} />
            <Route path="transactions" element={<TransactionsPage activeWorkspace={activeWorkspace} />} />
            <Route path="accounts" element={<AccountsPage activeWorkspace={activeWorkspace} />} />
            <Route path="categories" element={<CategoriesPage activeWorkspace={activeWorkspace} />} />
            <Route path="imports" element={<ImportsPage activeWorkspace={activeWorkspace} currentUser={currentUser!} />} />
            <Route path="budgets" element={<BudgetsPage activeWorkspace={activeWorkspace} />} />
            <Route path="debts" element={<DebtsPage activeWorkspace={activeWorkspace} />} />
            <Route path="rewards" element={<RewardsPage activeWorkspace={activeWorkspace} />} />
            <Route path="settings" element={<SettingsPage activeWorkspace={activeWorkspace} />} />
            <Route path="*" element={<NotFoundPage />} />
          </Routes>
        )}
      </main>
    </div>
  );
}
