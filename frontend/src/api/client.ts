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

function buildHeaders(init?: ApiRequestOptions, hasJsonBody = false): HeadersInit {
  const devUserId = init?.devUserId ?? DEFAULT_DEV_USER_ID;
  return {
    Accept: "application/json",
    ...(hasJsonBody ? { "Content-Type": "application/json" } : {}),
    ...(devUserId ? { "X-User-Id": devUserId } : {}),
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
