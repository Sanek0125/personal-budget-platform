import { describe, expect, it, vi } from "vitest";

import { apiGet, buildApiUrl } from "./client";

describe("buildApiUrl", () => {
  it("joins configured base URL and path without duplicate slashes", () => {
    expect(buildApiUrl("/health", "http://localhost:8000/api/")).toBe("http://localhost:8000/api/health");
  });

  it("uses root-relative URLs when no base URL is configured", () => {
    expect(buildApiUrl("health", "")).toBe("/health");
  });
});

describe("apiGet", () => {
  it("returns undefined for successful empty responses", async () => {
    const fetchMock = vi.spyOn(globalThis, "fetch").mockResolvedValueOnce(
      new Response(null, {
        status: 204,
      }),
    );

    await expect(apiGet("/health")).resolves.toBeUndefined();
    expect(fetchMock).toHaveBeenCalledWith("/health", expect.objectContaining({ method: "GET" }));

    fetchMock.mockRestore();
  });
});
