import { useQuery } from "@tanstack/react-query";

import { apiGet } from "../api/client";
import type { Workspace } from "../types";

export const WORKSPACES_QUERY_KEY = ["workspaces"] as const;

export function useWorkspaces() {
  return useQuery({
    queryKey: WORKSPACES_QUERY_KEY,
    queryFn: () => apiGet<Workspace[]>("/workspaces"),
  });
}
