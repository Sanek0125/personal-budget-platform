import { type FormEvent, useState } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";

import { apiGet, apiPost } from "../../api/client";
import type { Debt, DebtCreatePayload, DebtDirection, DebtSummary, Workspace } from "../../types";

export function DebtsPage({ activeWorkspace }: { activeWorkspace?: Workspace }) {
  const queryClient = useQueryClient();
  const [contactName, setContactName] = useState("");
  const [direction, setDirection] = useState<DebtDirection>("they_owe_me");
  const [principalAmount, setPrincipalAmount] = useState("");
  const [currencyCode, setCurrencyCode] = useState(activeWorkspace?.base_currency_code ?? "");
  const [description, setDescription] = useState("");
  const [dueDate, setDueDate] = useState("");
  const [statusMessage, setStatusMessage] = useState<string | null>(null);

  const debtsQuery = useQuery({
    queryKey: ["debts", activeWorkspace?.id],
    queryFn: () => apiGet<Debt[]>(`/workspaces/${activeWorkspace?.id}/debts`),
    enabled: Boolean(activeWorkspace),
  });
  const summaryQuery = useQuery({
    queryKey: ["debts-summary", activeWorkspace?.id],
    queryFn: () => apiGet<DebtSummary>(`/workspaces/${activeWorkspace?.id}/debts/summary`),
    enabled: Boolean(activeWorkspace),
  });

  async function handleCreateDebt(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!activeWorkspace) {
      setStatusMessage("Select a workspace before creating debts");
      return;
    }

    setStatusMessage(null);
    const payload: DebtCreatePayload = {
      contact_name: contactName.trim(),
      direction,
      principal_amount: principalAmount.trim(),
      currency_code: currencyCode.trim().toUpperCase(),
      description: description.trim(),
      ...(dueDate ? { due_date: dueDate } : {}),
    };

    try {
      const debt = await apiPost<Debt, DebtCreatePayload>(`/workspaces/${activeWorkspace.id}/debts`, payload);
      setStatusMessage(`Created debt ${debt.description}`);
      setContactName("");
      setDirection("they_owe_me");
      setPrincipalAmount("");
      setCurrencyCode(activeWorkspace.base_currency_code);
      setDescription("");
      setDueDate("");
      await queryClient.invalidateQueries({ queryKey: ["debts", activeWorkspace.id] });
      await queryClient.invalidateQueries({ queryKey: ["debts-summary", activeWorkspace.id] });
    } catch {
      setStatusMessage("Unable to create debt");
    }
  }

  return (
    <section className="page-card debts-page">
      <p className="eyebrow">MVP module</p>
      <h2>Debts</h2>
      <p>Track money owed in both directions, simple due dates, repayments, and balances.</p>

      <div className="settings-grid">
        <form className="settings-panel" onSubmit={handleCreateDebt}>
          <h3>Create debt</h3>
          <p>
            Active workspace: <strong>{activeWorkspace?.name ?? "none"}</strong>
          </p>
          <label>
            Contact name
            <input value={contactName} onChange={(event) => setContactName(event.target.value)} minLength={1} required />
          </label>
          <label>
            Debt direction
            <select value={direction} onChange={(event) => setDirection(event.target.value as DebtDirection)}>
              <option value="they_owe_me">they_owe_me</option>
              <option value="i_owe_them">i_owe_them</option>
            </select>
          </label>
          <label>
            Principal amount
            <input
              inputMode="decimal"
              value={principalAmount}
              onChange={(event) => setPrincipalAmount(event.target.value)}
              required
            />
          </label>
          <label>
            Debt currency
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
            Debt description
            <input value={description} onChange={(event) => setDescription(event.target.value)} minLength={1} required />
          </label>
          <label>
            Due date
            <input type="date" value={dueDate} onChange={(event) => setDueDate(event.target.value)} />
          </label>
          <button type="submit" disabled={!activeWorkspace}>Create debt</button>
          {statusMessage ? <p role="status">{statusMessage}</p> : null}
        </form>

        <div className="settings-panel">
          <h3>Debt list</h3>
          {!activeWorkspace ? <p>Select a workspace to load debts.</p> : null}
          {debtsQuery.isLoading || summaryQuery.isLoading ? <p>Loading debts…</p> : null}
          {debtsQuery.isError || summaryQuery.isError ? <p role="alert">Unable to load debts</p> : null}
          {summaryQuery.data?.totals.length ? (
            <div>
              <h4>Summary</h4>
              <ul className="entity-list">
                {summaryQuery.data.totals.map((total) => (
                  <li key={`${total.direction}-${total.currency_code}`}>
                    <strong>
                      {total.direction} · {total.currency_code}
                    </strong>
                    <span>Principal: {total.principal_amount}</span>
                    <span>Paid: {total.paid_amount}</span>
                    <span>
                      Remaining: {total.remaining_amount} {total.currency_code}
                    </span>
                  </li>
                ))}
              </ul>
            </div>
          ) : null}
          {debtsQuery.data?.length === 0 ? <p>No debts yet.</p> : null}
          {debtsQuery.data?.length ? (
            <ul className="entity-list">
              {debtsQuery.data.map((debt) => {
                const paidAmount = debt.payments.reduce((sum, payment) => sum + Number.parseFloat(payment.amount), 0);
                return (
                  <li key={debt.id}>
                    <strong>{debt.description}</strong>
                    <span>
                      {debt.direction} · {debt.principal_amount} {debt.currency_code} · {debt.status}
                    </span>
                    <span>Contact: {debt.contact_id}</span>
                    {debt.due_date ? <span>Due: {debt.due_date}</span> : null}
                    <span>
                      Payments: {debt.payments.length} · paid {paidAmount.toFixed(2)} {debt.currency_code}
                    </span>
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
