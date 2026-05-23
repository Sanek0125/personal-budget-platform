import { type FormEvent, useState } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";

import { apiGet, apiPost } from "../../api/client";
import type { Budget, BudgetCreatePayload, Category, Workspace } from "../../types";

export function BudgetsPage({ activeWorkspace }: { activeWorkspace?: Workspace }) {
  const queryClient = useQueryClient();
  const [name, setName] = useState("");
  const [periodStart, setPeriodStart] = useState("");
  const [periodEnd, setPeriodEnd] = useState("");
  const [currencyCode, setCurrencyCode] = useState(activeWorkspace?.base_currency_code ?? "");
  const [isActive, setIsActive] = useState(true);
  const [statusMessage, setStatusMessage] = useState<string | null>(null);

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
      </div>
    </section>
  );
}
