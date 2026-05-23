// @vitest-environment node

import { describe, expect, it } from "vitest";

import viteConfig from "./vite.config";

describe("Vite development proxy", () => {
  it("proxies API requests to the local backend to avoid browser CORS during development", () => {
    expect(viteConfig.server?.proxy).toMatchObject({
      "/api": {
        target: "http://localhost:8000",
        changeOrigin: true,
        rewrite: expect.any(Function),
      },
    });

    const apiProxy = viteConfig.server?.proxy?.["/api"];
    expect(typeof apiProxy).toBe("object");
    if (typeof apiProxy === "object" && "rewrite" in apiProxy && typeof apiProxy.rewrite === "function") {
      expect(apiProxy.rewrite("/api/workspaces")).toBe("/workspaces");
    }
  });
});
