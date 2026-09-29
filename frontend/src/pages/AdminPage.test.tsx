import { render, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { AdminPage } from "./AdminPage";

describe("AdminPage", () => {
  afterEach(() => vi.restoreAllMocks());

  it("shows cross-tenant overview and tenant records", async () => {
    vi.spyOn(window, "fetch").mockImplementation((input) => {
      const url = String(input);
      const payload = url.includes("/overview")
        ? {
            counts: {
              tenants: 2,
              users: 4,
              products: 8,
              stored_files: 3,
            },
          }
        : url.includes("/admin/data/")
          ? {
              entity: "field_definitions",
              items: [],
              total: 0,
              page: 1,
              page_size: 100,
            }
          : {
            items: [
              {
                id: "tenant-1",
                name: "Acme Trading",
                slug: "acme",
                status: "active",
                user_count: 2,
                product_count: 8,
                import_job_count: 1,
                file_count: 3,
                created_at: "2026-09-28T08:00:00Z",
              },
            ],
            total: 1,
            page: 1,
            page_size: 100,
          };
      return Promise.resolve(
        new Response(JSON.stringify(payload), {
          status: 200,
          headers: { "Content-Type": "application/json" },
        }),
      );
    });

    render(<AdminPage />);

    await waitFor(() => expect(screen.getByText("Acme Trading")).toBeInTheDocument());
    expect(screen.getByRole("heading", { name: "系统后台" })).toBeInTheDocument();
    expect(screen.getByText("平台管理员只读模式")).toBeInTheDocument();
    expect(screen.getByText("acme")).toBeInTheDocument();
  });
});
