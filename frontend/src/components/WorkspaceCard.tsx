import type { UseQueryResult } from "@tanstack/react-query";

import type { Workspace } from "../types";

type WorkspaceQuery = UseQueryResult<Workspace[], Error>;

type WorkspaceCardProps = {
  activeWorkspace: Workspace | undefined;
  selectedWorkspaceId: string | undefined;
  workspacesQuery: WorkspaceQuery;
  onWorkspaceChange: (workspaceId: string) => void;
};

export function WorkspaceCard({
  activeWorkspace,
  selectedWorkspaceId,
  workspacesQuery,
  onWorkspaceChange,
}: WorkspaceCardProps) {
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
          <label className="workspace-switcher">
            <span>Active workspace</span>
            <select value={selectedWorkspaceId} onChange={(event) => onWorkspaceChange(event.target.value)}>
              {workspacesQuery.data?.map((workspace) => (
                <option key={workspace.id} value={workspace.id}>
                  {workspace.name}
                </option>
              ))}
            </select>
          </label>
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
