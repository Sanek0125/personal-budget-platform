const DEFAULT_API_BASE_URL = import.meta.env.VITE_API_BASE_URL ?? "";
const DEFAULT_DEV_USER_ID =
  import.meta.env.VITE_DEV_USER_ID ?? "00000000-0000-0000-0000-000000000001";

type ApiRequestOptions = RequestInit & {
  devUserId?: string;
};

export function buildApiUrl(path: string, baseUrl = DEFAULT_API_BASE_URL): string {
  const normalizedPath = path.startsWith("/") ? path : `/${path}`;
  const normalizedBase = baseUrl.replace(/\/$/, "");

  if (!normalizedBase) {
    return normalizedPath;
  }

  return `${normalizedBase}${normalizedPath}`;
}

function buildHeaders(init?: ApiRequestOptions): HeadersInit {
  const devUserId = init?.devUserId ?? DEFAULT_DEV_USER_ID;
  return {
    Accept: "application/json",
    ...(devUserId ? { "X-User-Id": devUserId } : {}),
    ...init?.headers,
  };
}

export async function apiGet<TResponse>(path: string, init?: ApiRequestOptions): Promise<TResponse> {
  const requestInit: RequestInit = { ...init };
  delete (requestInit as ApiRequestOptions).devUserId;

  const response = await fetch(buildApiUrl(path), {
    ...requestInit,
    method: "GET",
    headers: buildHeaders(init),
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
