import { type FormEvent, useState } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";

import { apiGet, apiPost } from "../../api/client";
import type {
  Budget,
  BudgetCreatePayload,
  BudgetLimit,
  BudgetLimitCreatePayload,
  BudgetProgress,
  Category,
  Workspace,
} from "../../types";

export function BudgetsPage({ activeWorkspace }: { activeWorkspace?: Workspace }) {
  const queryClient = useQueryClient();
  const [name, setName] = useState("");
  const [periodStart, setPeriodStart] = useState("");
  const [periodEnd, setPeriodEnd] = useState("");
  const [currencyCode, setCurrencyCode] = useState(activeWorkspace?.base_currency_code ?? "");
  const [isActive, setIsActive] = useState(true);
  const [limitCategoryId, setLimitCategoryId] = useState("");
  const [limitAmount, setLimitAmount] = useState("");
  const [limitCurrencyCode, setLimitCurrencyCode] = useState(activeWorkspace?.base_currency_code ?? "");
  const [limitRollover, setLimitRollover] = useState(false);
  const [statusMessage, setStatusMessage] = useState<string | null>(null);
  const [limitStatusMessage, setLimitStatusMessage] = useState<string | null>(null);

  const budgetsQuery = useQuery({
    queryKey: ["budgets", activeWorkspace?.id],
    queryFn: () => apiGet<Budget[]>(`/workspaces/${activeWorkspace?.id}/budgets`),
    enabled: Boolean(activeWorkspace),
  });
  const categoriesQuery = useQuery({
    queryKey: ["categories", activeWorkspace?.id, "budgets-page"],
    queryFn: () => apiGet<Category[]>(`/workspaces/${activeWorkspace?.id}/categories`),
    enabled: Boolean(activeWorkspace),
  });
  const activeBudget = budgetsQuery.data?.[0];
  const selectedLimitCategory = categoriesQuery.data?.find((category) => category.id === limitCategoryId);
  const progressQuery = useQuery({
    queryKey: ["budget-progress", activeBudget?.id],
    queryFn: () => apiGet<BudgetProgress>(`/budgets/${activeBudget?.id}/progress`),
    enabled: Boolean(activeBudget),
  });

  async function handleCreateBudget(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!activeWorkspace) {
      setStatusMessage("Select a workspace before creating budgets");
      return;
    }

    setStatusMessage(null);
    const payload: BudgetCreatePayload = {
      name: name.trim(),
      period_type: "monthly",
      period_start: periodStart,
      period_end: periodEnd,
      currency_code: currencyCode.trim().toUpperCase(),
      is_active: isActive,
    };

    try {
      const budget = await apiPost<Budget, BudgetCreatePayload>(
        `/workspaces/${activeWorkspace.id}/budgets`,
        payload,
      );
      setStatusMessage(`Created budget ${budget.name}`);
      setName("");
      setPeriodStart("");
      setPeriodEnd("");
      setCurrencyCode(activeWorkspace.base_currency_code);
      setIsActive(true);
      await queryClient.invalidateQueries({ queryKey: ["budgets", activeWorkspace.id] });
    } catch {
      setStatusMessage("Unable to create budget");
    }
  }

  async function handleCreateLimit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!activeBudget) {
      setLimitStatusMessage("Create a budget before adding limits");
      return;
    }

    const payload: BudgetLimitCreatePayload = {
      category_id: limitCategoryId,
      amount: limitAmount.trim(),
      currency_code: (limitCurrencyCode || activeBudget.currency_code).trim().toUpperCase(),
      rollover: limitRollover,
    };

    try {
      await apiPost<BudgetLimit, BudgetLimitCreatePayload>(`/budgets/${activeBudget.id}/limits`, payload);
      setLimitStatusMessage(`Created budget limit for ${selectedLimitCategory?.name ?? "category"}`);
      setLimitAmount("");
      setLimitCurrencyCode(activeBudget.currency_code);
      setLimitRollover(false);
      await queryClient.invalidateQueries({ queryKey: ["budget-progress", activeBudget.id] });
    } catch {
      setLimitStatusMessage("Unable to create budget limit");
    }
  }

  function categoryName(categoryId: string) {
    return categoriesQuery.data?.find((category) => category.id === categoryId)?.name ?? "Uncategorized";
  }

  return (
    <section className="page-card budgets-page">
      <p className="eyebrow">MVP module</p>
      <h2>Budgets</h2>
      <p>Monthly budget plans for the active workspace, with categories ready for limit planning.</p>

      <div className="settings-grid">
        <form className="settings-panel" onSubmit={handleCreateBudget}>
          <h3>Create budget</h3>
          <p>
            Active workspace: <strong>{activeWorkspace?.name ?? "none"}</strong>
          </p>
          <label>
            Budget name
            <input value={name} onChange={(event) => setName(event.target.value)} minLength={1} required />
          </label>
          <label>
            Period start
            <input type="date" value={periodStart} onChange={(event) => setPeriodStart(event.target.value)} required />
          </label>
          <label>
            Period end
            <input type="date" value={periodEnd} onChange={(event) => setPeriodEnd(event.target.value)} required />
          </label>
          <label>
            Budget currency
            <input
              value={currencyCode}
              onChange={(event) => setCurrencyCode(event.target.value)}
              placeholder={activeWorkspace?.base_currency_code ?? "RUB"}
              minLength={3}
              maxLength={3}
              required
            />
          </label>
          <label className="checkbox-label">
            <input type="checkbox" checked={isActive} onChange={(event) => setIsActive(event.target.checked)} />
            Active budget
          </label>
          <button type="submit" disabled={!activeWorkspace}>Create budget</button>
          {statusMessage ? <p role="status">{statusMessage}</p> : null}
        </form>

        <div className="settings-panel">
          <h3>Budget list</h3>
          {!activeWorkspace ? <p>Select a workspace to load budgets.</p> : null}
          {budgetsQuery.isLoading || categoriesQuery.isLoading ? <p>Loading budgets…</p> : null}
          {budgetsQuery.isError ? <p role="alert">Unable to load budgets</p> : null}
          {budgetsQuery.data?.length === 0 ? <p>No budgets yet.</p> : null}
          {categoriesQuery.data?.length ? <p>Limit categories available: {categoriesQuery.data.length}</p> : null}
          {budgetsQuery.data?.length ? (
            <ul className="entity-list">
              {budgetsQuery.data.map((budget) => (
                <li key={budget.id}>
                  <strong>{budget.name}</strong>
                  <span>
                    {budget.period_type} · {budget.period_start} → {budget.period_end}
                  </span>
                  <span>
                    {budget.currency_code} · {budget.is_active ? "active" : "inactive"}
                  </span>
                </li>
              ))}
            </ul>
          ) : null}
        </div>

        <form className="settings-panel" onSubmit={handleCreateLimit}>
          <h3>Budget limits</h3>
          <p>{activeBudget ? "Limits apply to the first active budget in the list." : "Create a budget before adding limits."}</p>
          <label>
            Limit category
            <select
              value={limitCategoryId}
              onChange={(event) => setLimitCategoryId(event.target.value)}
              disabled={!activeBudget || !categoriesQuery.data?.length}
              required
            >
              <option value="">Choose category</option>
              {categoriesQuery.data?.map((category) => (
                <option key={category.id} value={category.id}>
                  {category.name}
                </option>
              ))}
            </select>
          </label>
          <label>
            Limit amount
            <input
              inputMode="decimal"
              value={limitAmount}
              onChange={(event) => setLimitAmount(event.target.value)}
              placeholder="10000"
              required
            />
          </label>
          <label>
            Limit currency
            <input
              value={limitCurrencyCode}
              onChange={(event) => setLimitCurrencyCode(event.target.value)}
              placeholder={activeBudget?.currency_code ?? activeWorkspace?.base_currency_code ?? "RUB"}
              minLength={3}
              maxLength={3}
              required
            />
          </label>
          <label className="checkbox-label">
            <input type="checkbox" checked={limitRollover} onChange={(event) => setLimitRollover(event.target.checked)} />
            Rollover unused amount
          </label>
          <button type="submit" disabled={!activeBudget || !categoriesQuery.data?.length}>Add budget limit</button>
          {limitStatusMessage ? <p role="status">{limitStatusMessage}</p> : null}
        </form>

        <div className="settings-panel">
          <h3>Budget progress</h3>
          {!activeBudget ? <p>Create a budget to see progress.</p> : null}
          {progressQuery.isLoading ? <p>Loading budget progress…</p> : null}
          {progressQuery.isError ? <p role="alert">Unable to load budget progress</p> : null}
          {progressQuery.data ? (
            <div className="entity-list">
              <p>Total limit: {progressQuery.data.total_limit} {progressQuery.data.currency_code}</p>
              <p>Total spent: {progressQuery.data.total_spent} {progressQuery.data.currency_code}</p>
              <p>Total remaining: {progressQuery.data.total_remaining} {progressQuery.data.currency_code}</p>
              {progressQuery.data.limits.length ? (
                <ul className="entity-list">
                  {progressQuery.data.limits.map((limit) => (
                    <li key={limit.category_id}>
                      <strong>{categoryName(limit.category_id)}</strong>
                      <span>
                        {categoryName(limit.category_id)}: {limit.spent_amount} spent of {limit.limit_amount} {limit.currency_code}
                      </span>
                      <span>{limit.remaining_amount} remaining · {limit.percent_used}% used</span>
                    </li>
                  ))}
                </ul>
              ) : (
                <p>No category limits yet.</p>
              )}
            </div>
          ) : null}
        </div>
      </div>
    </section>
  );
}
