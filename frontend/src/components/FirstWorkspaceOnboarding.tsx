import { type FormEvent, useState } from "react";
import { useMutation } from "@tanstack/react-query";

import { apiPost } from "../api/client";
import type { Workspace, WorkspaceCreatePayload, WorkspaceKind } from "../types";

type FirstWorkspaceOnboardingProps = {
  onWorkspaceCreated: (workspace: Workspace) => void;
};

export function FirstWorkspaceOnboarding({ onWorkspaceCreated }: FirstWorkspaceOnboardingProps) {
  const [name, setName] = useState("Personal Budget");
  const [kind, setKind] = useState<WorkspaceKind>("personal");
  const [baseCurrencyCode, setBaseCurrencyCode] = useState("RUB");
  const [errorMessage, setErrorMessage] = useState<string | null>(null);

  const createWorkspace = useMutation({
    mutationFn: (payload: WorkspaceCreatePayload) => apiPost<Workspace, WorkspaceCreatePayload>("/workspaces", payload),
    onSuccess: (workspace) => {
      setErrorMessage(null);
      onWorkspaceCreated(workspace);
    },
    onError: () => {
      setErrorMessage("Unable to create workspace");
    },
  });

  function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setErrorMessage(null);
    createWorkspace.mutate({
      name: name.trim(),
      kind,
      base_currency_code: baseCurrencyCode.trim().toUpperCase(),
    });
  }

  return (
    <section className="page-card onboarding-card">
      <p className="eyebrow">Workspace setup</p>
      <h2>Create your first workspace</h2>
      <p>Start with one personal or family budget space. You can add more workspaces later.</p>
      <form className="stacked-form" onSubmit={handleSubmit}>
        <label>
          Workspace name
          <input value={name} onChange={(event) => setName(event.target.value)} required />
        </label>
        <label>
          Workspace type
          <select value={kind} onChange={(event) => setKind(event.target.value as WorkspaceKind)}>
            <option value="personal">Personal</option>
            <option value="family">Family</option>
            <option value="trip">Trip</option>
            <option value="other">Other</option>
          </select>
        </label>
        <label>
          Base currency
          <input value={baseCurrencyCode} onChange={(event) => setBaseCurrencyCode(event.target.value)} required />
        </label>
        <button type="submit" disabled={createWorkspace.isPending}>
          {createWorkspace.isPending ? "Creating…" : "Create workspace"}
        </button>
      </form>
      {errorMessage ? <p role="alert">{errorMessage}</p> : null}
    </section>
  );
}
