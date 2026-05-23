const DEFAULT_API_BASE_URL = import.meta.env.VITE_API_BASE_URL ?? "";
export const AUTH_TOKEN_STORAGE_KEY = "personal-budget.auth-token";
export const EXPLICIT_DEV_USER_ID = import.meta.env.VITE_DEV_USER_ID;

type ApiRequestOptions = RequestInit & {
  accessToken?: string | null;
  devUserId?: string;
};

export function readStoredAccessToken(): string | null {
  return localStorage.getItem(AUTH_TOKEN_STORAGE_KEY);
}

export function storeAccessToken(accessToken: string) {
  localStorage.setItem(AUTH_TOKEN_STORAGE_KEY, accessToken);
}

export function clearAccessToken() {
  localStorage.removeItem(AUTH_TOKEN_STORAGE_KEY);
}

export function buildApiUrl(path: string, baseUrl = DEFAULT_API_BASE_URL): string {
  const normalizedPath = path.startsWith("/") ? path : `/${path}`;
  const normalizedBase = baseUrl.replace(/\/$/, "");

  if (!normalizedBase) {
    return normalizedPath;
  }

  return `${normalizedBase}${normalizedPath}`;
}

function buildHeaders(init?: ApiRequestOptions, hasJsonBody = false): HeadersInit {
  const accessToken = init?.accessToken === undefined ? readStoredAccessToken() : init.accessToken;
  return {
    Accept: "application/json",
    ...(hasJsonBody ? { "Content-Type": "application/json" } : {}),
    ...(accessToken ? { Authorization: `Bearer ${accessToken}` } : {}),
    ...(init?.devUserId ? { "X-User-Id": init.devUserId } : {}),
    ...init?.headers,
  };
}

async function parseResponse<TResponse>(response: Response): Promise<TResponse> {
  if (!response.ok) {
    throw new Error(`API request failed with ${response.status}`);
  }

  const body = await response.text();
  if (!body) {
    return undefined as TResponse;
  }

  return JSON.parse(body) as TResponse;
}

function sanitizeRequestInit(init?: ApiRequestOptions): RequestInit {
  const requestInit: RequestInit = { ...init };
  delete (requestInit as ApiRequestOptions).accessToken;
  delete (requestInit as ApiRequestOptions).devUserId;
  return requestInit;
}

export async function apiGet<TResponse>(path: string, init?: ApiRequestOptions): Promise<TResponse> {
  const requestInit = sanitizeRequestInit(init);
  const response = await fetch(buildApiUrl(path), {
    ...requestInit,
    method: "GET",
    headers: buildHeaders(init),
  });

  return parseResponse<TResponse>(response);
}

export async function apiPost<TResponse, TPayload extends object>(
  path: string,
  payload: TPayload,
  init?: ApiRequestOptions,
): Promise<TResponse> {
  const requestInit = sanitizeRequestInit(init);
  const response = await fetch(buildApiUrl(path), {
    ...requestInit,
    method: "POST",
    headers: buildHeaders(init, true),
    body: JSON.stringify(payload),
  });

  return parseResponse<TResponse>(response);
}
