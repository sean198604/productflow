import { fireEvent, render, screen, waitFor } from "@testing-library/react";
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
    expect(screen.getByText("业务数据只读 · 账号密码可安全重置")).toBeInTheDocument();
    expect(screen.getByText("acme")).toBeInTheDocument();
  });

  it("allows a platform administrator to reset an account password", async () => {
    const requests: Array<{ url: string; body?: unknown }> = [];
    vi.spyOn(window, "fetch").mockImplementation((input, init) => {
      const url = String(input);
      if (url.includes("/admin/users/user-1/reset-password")) {
        requests.push({ url, body: JSON.parse(String(init?.body)) });
        return Promise.resolve(Response.json({ user_id: "user-1", username: "NE", sessions_revoked: true }));
      }
      if (url.includes("/admin/overview")) return Promise.resolve(Response.json({ counts: { tenants: 1, users: 1 } }));
      if (url.includes("/admin/data/")) return Promise.resolve(Response.json({ entity: "field_definitions", items: [], total: 0, page: 1, page_size: 100 }));
      if (url.includes("/admin/users")) return Promise.resolve(Response.json({ items: [{ id: "user-1", tenant_id: "tenant-1", tenant_name: "ProductFlow", tenant_slug: "productflow", username: "NE", email: "ne@example.test", role: "member", is_platform_admin: false, status: "active", last_login_at: null, created_at: "2026-09-30T00:00:00Z" }], total: 1, page: 1, page_size: 100 }));
      return Promise.resolve(Response.json({ items: [], total: 0, page: 1, page_size: 100 }));
    });

    render(<AdminPage />);
    fireEvent.click(await screen.findByRole("button", { name: /账号/ }));
    fireEvent.click(await screen.findByRole("button", { name: "重置密码" }));
    expect(screen.getByRole("dialog", { name: "重置账号 NE" })).toBeInTheDocument();
    const passwordInputs = screen.getAllByLabelText(/新密码/);
    fireEvent.change(passwordInputs[0], { target: { value: "NewPassword123!" } });
    fireEvent.change(passwordInputs[1], { target: { value: "NewPassword123!" } });
    fireEvent.click(screen.getByRole("button", { name: "确认重置" }));

    await waitFor(() => expect(requests).toHaveLength(1));
    expect(requests[0].body).toEqual({ new_password: "NewPassword123!" });
    expect(await screen.findByRole("status")).toHaveTextContent("NE 的密码已重置");
  });
});
