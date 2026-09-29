import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { AuthProvider } from "../auth/AuthProvider";
import { LoginPage } from "./LoginPage";

describe("LoginPage", () => {
  beforeEach(() => {
    window.sessionStorage.clear();
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  it("renders a username and password login form", () => {
    render(
      <MemoryRouter>
        <AuthProvider>
          <LoginPage />
        </AuthProvider>
      </MemoryRouter>,
    );

    expect(screen.getByRole("heading", { name: "ProductFlow" })).toBeInTheDocument();
    expect(screen.getByLabelText("邮箱或用户名")).toBeEnabled();
    expect(screen.getByLabelText("密码")).toBeEnabled();
    expect(screen.getByRole("button", { name: "登 录" })).toBeEnabled();
  });

  it("stores the token and enters the protected workspace", async () => {
    vi.spyOn(window, "fetch").mockResolvedValue(
      new Response(
        JSON.stringify({
          access_token: "signed-token",
          token_type: "bearer",
          expires_in: 1800,
          user: {
            id: "user-id",
            tenant_id: "tenant-id",
            username: "owner",
            email: "owner@example.test",
            role: "owner",
            is_platform_admin: false,
            status: "active",
          },
          tenant: { id: "tenant-id", name: "Demo", slug: "demo" },
        }),
        { status: 200, headers: { "Content-Type": "application/json" } },
      ),
    );

    render(
      <MemoryRouter initialEntries={["/login"]}>
        <AuthProvider>
          <Routes>
            <Route path="/login" element={<LoginPage />} />
            <Route path="/dashboard" element={<p>受保护工作空间</p>} />
          </Routes>
        </AuthProvider>
      </MemoryRouter>,
    );

    fireEvent.change(screen.getByLabelText("邮箱或用户名"), {
      target: { value: "owner@example.test" },
    });
    fireEvent.change(screen.getByLabelText("密码"), {
      target: { value: "ValidPassword123!" },
    });
    fireEvent.click(screen.getByRole("button", { name: "登 录" }));

    await waitFor(() => expect(screen.getByText("受保护工作空间")).toBeInTheDocument());
    expect(window.sessionStorage.getItem("productflow.access_token")).toBe("signed-token");
  });

  it("registers a tenant owner from the login page", async () => {
    const fetchMock = vi.spyOn(window, "fetch").mockResolvedValue(
      new Response(
        JSON.stringify({
          access_token: "registration-token",
          token_type: "bearer",
          expires_in: 1800,
          user: {
            id: "new-user-id",
            tenant_id: "new-tenant-id",
            username: "new-owner",
            email: "new-owner@example.test",
            role: "owner",
            is_platform_admin: false,
            status: "active",
          },
          tenant: { id: "new-tenant-id", name: "New Trading", slug: "new-trading" },
        }),
        { status: 201, headers: { "Content-Type": "application/json" } },
      ),
    );

    render(
      <MemoryRouter initialEntries={["/login"]}>
        <AuthProvider>
          <Routes>
            <Route path="/login" element={<LoginPage />} />
            <Route path="/dashboard" element={<p>新企业工作空间</p>} />
          </Routes>
        </AuthProvider>
      </MemoryRouter>,
    );

    fireEvent.click(screen.getByRole("button", { name: "注册企业账号" }));
    fireEvent.change(screen.getByLabelText("企业名称"), { target: { value: "New Trading" } });
    fireEvent.change(screen.getByLabelText("管理员用户名"), { target: { value: "new-owner" } });
    fireEvent.change(screen.getByLabelText("管理员邮箱"), { target: { value: "new-owner@example.test" } });
    fireEvent.change(screen.getByLabelText("密码"), { target: { value: "RegisteredPassword123!" } });
    fireEvent.change(screen.getByLabelText("确认密码"), { target: { value: "RegisteredPassword123!" } });
    fireEvent.click(screen.getByRole("button", { name: "创建企业账号" }));

    await waitFor(() => expect(screen.getByText("新企业工作空间")).toBeInTheDocument());
    expect(fetchMock).toHaveBeenCalledWith(
      "/api/v1/auth/register",
      expect.objectContaining({ method: "POST" }),
    );
    expect(window.sessionStorage.getItem("productflow.access_token")).toBe("registration-token");
  });
});
