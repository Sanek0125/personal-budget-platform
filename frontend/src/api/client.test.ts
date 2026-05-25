import { describe, expect, it, vi } from "vitest";

import { apiGet, apiPost, apiPostForm, buildApiUrl } from "./client";

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

  it("sends the temporary development user header when configured", async () => {
    const fetchMock = vi.spyOn(globalThis, "fetch").mockResolvedValueOnce(
      new Response("[]", {
        status: 200,
        headers: { "Content-Type": "application/json" },
      }),
    );

    await apiGet("/workspaces", { devUserId: "11111111-1111-1111-1111-111111111111" });

    expect(fetchMock).toHaveBeenCalledWith(
      "/workspaces",
      expect.objectContaining({
        headers: expect.objectContaining({
          Accept: "application/json",
          "X-User-Id": "11111111-1111-1111-1111-111111111111",
        }),
      }),
    );

    fetchMock.mockRestore();
  });


  it("does not send a development user header unless explicitly requested", async () => {
    const fetchMock = vi.spyOn(globalThis, "fetch").mockResolvedValueOnce(
      new Response("[]", {
        status: 200,
        headers: { "Content-Type": "application/json" },
      }),
    );

    await apiGet("/workspaces");

    expect(fetchMock).toHaveBeenCalledWith(
      "/workspaces",
      expect.objectContaining({
        headers: expect.not.objectContaining({ "X-User-Id": expect.any(String) }),
      }),
    );

    fetchMock.mockRestore();
  });

  it("sends bearer Authorization when a token is provided", async () => {
    const fetchMock = vi.spyOn(globalThis, "fetch").mockResolvedValueOnce(
      new Response("[]", {
        status: 200,
        headers: { "Content-Type": "application/json" },
      }),
    );

    await apiGet("/workspaces", { accessToken: "test-token" });

    expect(fetchMock).toHaveBeenCalledWith(
      "/workspaces",
      expect.objectContaining({
        headers: expect.objectContaining({ Authorization: "Bearer test-token" }),
      }),
    );

    fetchMock.mockRestore();
  });
});

describe("apiPost", () => {
  it("serializes JSON payloads and sends the temporary development user header", async () => {
    const fetchMock = vi.spyOn(globalThis, "fetch").mockResolvedValueOnce(
      new Response(JSON.stringify({ id: "user-1", display_name: "Olga" }), {
        status: 201,
        headers: { "Content-Type": "application/json" },
      }),
    );

    await expect(
      apiPost("/users", { display_name: "Olga" }, { devUserId: "11111111-1111-1111-1111-111111111111" }),
    ).resolves.toEqual({ id: "user-1", display_name: "Olga" });

    expect(fetchMock).toHaveBeenCalledWith(
      "/users",
      expect.objectContaining({
        method: "POST",
        body: JSON.stringify({ display_name: "Olga" }),
        headers: expect.objectContaining({
          Accept: "application/json",
          "Content-Type": "application/json",
          "X-User-Id": "11111111-1111-1111-1111-111111111111",
        }),
      }),
    );

    fetchMock.mockRestore();
  });
});

describe("apiPostForm", () => {
  it("sends multipart form data without forcing a JSON content type", async () => {
    const fetchMock = vi.spyOn(globalThis, "fetch").mockResolvedValueOnce(
      new Response(JSON.stringify({ id: "batch-1" }), {
        status: 201,
        headers: { "Content-Type": "application/json" },
      }),
    );
    const formData = new FormData();
    formData.append("file", new File(["%PDF-1.4"], "statement.pdf", { type: "application/pdf" }));

    await expect(apiPostForm("/imports/upload-file", formData, { accessToken: "test-token" })).resolves.toEqual({
      id: "batch-1",
    });

    expect(fetchMock).toHaveBeenCalledWith(
      "/imports/upload-file",
      expect.objectContaining({
        method: "POST",
        body: formData,
        headers: expect.objectContaining({
          Accept: "application/json",
          Authorization: "Bearer test-token",
        }),
      }),
    );
    const request = fetchMock.mock.calls[0][1] as RequestInit;
    expect(request.headers).not.toEqual(expect.objectContaining({ "Content-Type": expect.any(String) }));

    fetchMock.mockRestore();
  });
});
