import type { UseQueryResult } from "@tanstack/react-query";

import type { Workspace } from "../types";

type WorkspaceQuery = UseQueryResult<Workspace[], Error>;

export function WorkspaceCard({ workspacesQuery }: { workspacesQuery: WorkspaceQuery }) {
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
