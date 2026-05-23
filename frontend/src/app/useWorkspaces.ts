import { useQuery } from "@tanstack/react-query";

import { apiGet } from "../api/client";
import type { Workspace } from "../types";

export function useWorkspaces() {
  return useQuery({
    queryKey: ["workspaces"],
    queryFn: () => apiGet<Workspace[]>("/workspaces"),
  });
}
