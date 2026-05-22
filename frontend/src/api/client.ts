const DEFAULT_API_BASE_URL = import.meta.env.VITE_API_BASE_URL ?? "";

export function buildApiUrl(path: string, baseUrl = DEFAULT_API_BASE_URL): string {
  const normalizedPath = path.startsWith("/") ? path : `/${path}`;
  const normalizedBase = baseUrl.replace(/\/$/, "");

  if (!normalizedBase) {
    return normalizedPath;
  }

  return `${normalizedBase}${normalizedPath}`;
}

export async function apiGet<TResponse>(path: string, init?: RequestInit): Promise<TResponse> {
  const response = await fetch(buildApiUrl(path), {
    ...init,
    method: "GET",
    headers: {
      Accept: "application/json",
      ...init?.headers,
    },
  });

  if (!response.ok) {
    throw new Error(`API request failed with ${response.status}`);
  }

  return response.text().then((body) => {
    if (!body) {
      return undefined as TResponse;
    }

    return JSON.parse(body) as TResponse;
  });
}
