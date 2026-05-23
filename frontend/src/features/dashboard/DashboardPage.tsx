import { useEffect, useState } from "react";
import { useQuery } from "@tanstack/react-query";

import { apiGet } from "../../api/client";
import type { Account, Budget, DebtSummary, RewardEvent, Transaction, Workspace } from "../../types";

function decimalValue(value: string | null | undefined): number {
  const parsed = Number.parseFloat(value ?? "0");
  return Number.isFinite(parsed) ? parsed : 0;
}

function money(value: number, currencyCode: string): string {
  return `${value.toFixed(2)} ${currencyCode}`;
}

function summarizeNetCashflow(transactions: Transaction[], currencyCode: string): string {
  const total = transactions
    .filter((transaction) => transaction.status === "posted")
    .reduce((sum, transaction) => sum + decimalValue(transaction.amount), 0);
  return money(total, currencyCode);
}

function summarizeDebtRemaining(summary: DebtSummary | undefined, currencyCode: string): string {
  const total =
    summary?.totals
      .filter((item) => item.currency_code === currencyCode)
      .reduce((sum, item) => sum + decimalValue(item.remaining_amount), 0) ?? 0;
  return money(total, currencyCode);
}

function sortByOccurredAt<T extends { occurred_at: string }>(items: T[]): T[] {
  return [...items].sort((left, right) => Date.parse(right.occurred_at) - Date.parse(left.occurred_at));
}

export function DashboardPage({ activeWorkspace }: { activeWorkspace?: Workspace }) {
  const workspaceId = activeWorkspace?.id;
  const [overviewWorkspaceId, setOverviewWorkspaceId] = useState<string | undefined>();

  useEffect(() => {
    if (!workspaceId) {
      return undefined;
    }

    const timeoutId = window.setTimeout(() => setOverviewWorkspaceId(workspaceId), 50);
    return () => window.clearTimeout(timeoutId);
  }, [workspaceId]);

  const shouldLoadOverview = Boolean(workspaceId && overviewWorkspaceId === workspaceId);

  const accountsQuery = useQuery({
    queryKey: ["dashboard", "accounts", workspaceId],
    queryFn: () => apiGet<Account[]>(`/workspaces/${workspaceId}/accounts`),
    enabled: Boolean(workspaceId && shouldLoadOverview),
  });
  const transactionsQuery = useQuery({
    queryKey: ["dashboard", "transactions", workspaceId],
    queryFn: () => apiGet<Transaction[]>(`/workspaces/${workspaceId}/transactions`),
    enabled: Boolean(workspaceId && shouldLoadOverview),
  });
  const budgetsQuery = useQuery({
    queryKey: ["dashboard", "budgets", workspaceId],
    queryFn: () => apiGet<Budget[]>(`/workspaces/${workspaceId}/budgets`),
    enabled: Boolean(workspaceId && shouldLoadOverview),
  });
  const debtSummaryQuery = useQuery({
    queryKey: ["dashboard", "debts-summary", workspaceId],
    queryFn: () => apiGet<DebtSummary>(`/workspaces/${workspaceId}/debts/summary`),
    enabled: Boolean(workspaceId && shouldLoadOverview),
  });
  const rewardEventsQuery = useQuery({
    queryKey: ["dashboard", "reward-events", workspaceId],
    queryFn: () => apiGet<RewardEvent[]>(`/workspaces/${workspaceId}/rewards/events`),
    enabled: Boolean(workspaceId && shouldLoadOverview),
  });

  const accounts = accountsQuery.data ?? [];
  const transactions = transactionsQuery.data ?? [];
  const budgets = budgetsQuery.data ?? [];
  const rewardEvents = rewardEventsQuery.data ?? [];
  const currencyCode = activeWorkspace?.base_currency_code ?? "RUB";
  const isLoading =
    accountsQuery.isLoading ||
    transactionsQuery.isLoading ||
    budgetsQuery.isLoading ||
    debtSummaryQuery.isLoading ||
    rewardEventsQuery.isLoading;
  const isError =
    accountsQuery.isError ||
    transactionsQuery.isError ||
    budgetsQuery.isError ||
    debtSummaryQuery.isError ||
    rewardEventsQuery.isError;

  const recentTransactions = sortByOccurredAt(transactions).slice(0, 5);
  const recentRewardEvents = sortByOccurredAt(rewardEvents).slice(0, 3);

  return (
    <section className="page-card dashboard-page">
      <p className="eyebrow">Workspace overview</p>
      <h2>Dashboard</h2>
      <p>Overview cards for the active workspace.</p>

      {!activeWorkspace ? <p>Select a workspace to load the dashboard.</p> : null}
      {isLoading ? <p>Loading dashboard…</p> : null}
      {isError ? <p role="alert">Unable to load dashboard overview</p> : null}

      {activeWorkspace ? (
        <>
          <div className="settings-grid">
            <article className="settings-panel">
              <h3>Accounts</h3>
              <strong>{accounts.filter((account) => account.is_active).length} active</strong>
              <span>{accounts.length} total</span>
            </article>
            <article className="settings-panel">
              <h3>Net cashflow</h3>
              <strong>{summarizeNetCashflow(transactions, currencyCode)}</strong>
              <span>Posted transactions only</span>
            </article>
            <article className="settings-panel">
              <h3>Budgets</h3>
              <strong>{budgets.filter((budget) => budget.is_active).length} active</strong>
              <span>{budgets.length} total</span>
            </article>
            <article className="settings-panel">
              <h3>Debt remaining</h3>
              <strong>{summarizeDebtRemaining(debtSummaryQuery.data, currencyCode)}</strong>
              <span>In {currencyCode}</span>
            </article>
            <article className="settings-panel">
              <h3>Reward events</h3>
              <strong>{rewardEvents.length} tracked</strong>
              <span>Manual cashback, points, and miles events</span>
            </article>
          </div>

          <div className="settings-grid">
            <div className="settings-panel">
              <h3>Recent transactions</h3>
              {recentTransactions.length === 0 ? <p>No transactions yet.</p> : null}
              {recentTransactions.length ? (
                <ul className="entity-list">
                  {recentTransactions.map((transaction) => (
                    <li key={transaction.id}>
                      <strong>{transaction.description}</strong>
                      <span>
                        {transaction.type} · {transaction.amount} {transaction.currency_code}
                      </span>
                      <span>Occurred: {new Date(transaction.occurred_at).toLocaleString()}</span>
                    </li>
                  ))}
                </ul>
              ) : null}
            </div>

            <div className="settings-panel">
              <h3>Recent rewards</h3>
              {recentRewardEvents.length === 0 ? <p>No reward events yet.</p> : null}
              {recentRewardEvents.length ? (
                <ul className="entity-list">
                  {recentRewardEvents.map((event) => (
                    <li key={event.id}>
                      <strong>{event.description}</strong>
                      <span>
                        {event.event_type} · {event.amount} {event.currency_code ?? event.reward_kind}
                      </span>
                      <span>Status: {event.status}</span>
                    </li>
                  ))}
                </ul>
              ) : null}
            </div>
          </div>
        </>
      ) : null}
    </section>
  );
}
