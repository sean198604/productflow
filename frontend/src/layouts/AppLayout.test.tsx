import { fireEvent, render, screen } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { MemoryRouter, Route, Routes } from "react-router-dom";

import { AppLayout } from "./AppLayout";

vi.mock("../auth/AuthProvider", () => ({
  useAuth: () => ({
    session: {
      user: {
        id: "user-1",
        tenant_id: "tenant-1",
        username: "admin",
        email: "admin@example.com",
        role: "owner",
        is_platform_admin: true,
        status: "active",
      },
      tenant: { id: "tenant-1", name: "ProductFlow System", slug: "productflow-admin" },
    },
    logout: vi.fn(),
  }),
}));

function renderLayout() {
  return render(
    <MemoryRouter initialEntries={["/dashboard"]}>
      <Routes>
        <Route element={<AppLayout />}>
          <Route path="/dashboard" element={<div>页面内容</div>} />
        </Route>
      </Routes>
    </MemoryRouter>,
  );
}

describe("AppLayout desktop sidebar", () => {
  beforeEach(() => window.localStorage.clear());

  it("collapses and expands while keeping navigation accessible", () => {
    renderLayout();

    fireEvent.click(screen.getByRole("button", { name: "收起侧边栏" }));

    expect(screen.getByRole("button", { name: "展开侧边栏" })).toBeInTheDocument();
    expect(
      screen.getAllByRole("link", { name: "产品资料" }).find((link) => link.title === "产品资料"),
    ).toBeDefined();
    expect(window.localStorage.getItem("productflow.sidebar.collapsed")).toBe("true");

    fireEvent.click(screen.getByRole("button", { name: "展开侧边栏" }));

    expect(screen.getByRole("button", { name: "收起侧边栏" })).toBeInTheDocument();
    expect(window.localStorage.getItem("productflow.sidebar.collapsed")).toBe("false");
  });

  it("restores the saved collapsed preference", () => {
    window.localStorage.setItem("productflow.sidebar.collapsed", "true");

    renderLayout();

    expect(screen.getByRole("button", { name: "展开侧边栏" })).toBeInTheDocument();
    expect(
      screen.getAllByRole("link", { name: "系统后台" }).find((link) => link.title === "系统后台"),
    ).toBeDefined();
  });
});
