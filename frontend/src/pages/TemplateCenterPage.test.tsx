import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { afterEach, describe, expect, it, vi } from "vitest";

import { AuthProvider } from "../auth/AuthProvider";
import { GlobalErrorProvider } from "../components/errors/GlobalErrorProvider";
import { TemplateCenterPage } from "./TemplateCenterPage";

describe("TemplateCenterPage", () => {
  afterEach(() => {
    vi.restoreAllMocks();
    window.sessionStorage.clear();
  });

  it("shows template validation and mapping status", async () => {
    vi.spyOn(window, "fetch").mockImplementation((input) => {
      if (String(input).endsWith("/import-templates")) {
        return Promise.resolve(Response.json({ items: [], total: 0 }));
      }
      return Promise.resolve(Response.json({
        items: [
          {
            id: "template-1",
            tenant_id: "tenant-1",
            name: "Customer quotation",
            description: "Standard customer deck",
            output_type: "pptx",
            status: "active",
            current_version_number: 1,
            current_version: {
              id: "version-1",
              version_number: 1,
              template_sha256: "a".repeat(64),
              original_filename: "quotation.pptx",
              safe_filename: "quotation.pptx",
              mime_type: "application/vnd.openxmlformats-officedocument.presentationml.presentation",
              size_bytes: 10240,
              validation_report: {
                format: "pptx",
                is_valid: true,
                object_count: 5,
                parameterizable_count: 4,
                unsupported_count: 1,
                objects: [],
                warnings: [],
                errors: [],
                capabilities: [],
                unsupported_capabilities: [],
              },
              mapping_config: {
                version: "1.0",
                template_sha256: "a".repeat(64),
                bindings: [],
              },
              status: "needs_mapping",
              created_at: "2026-09-28T00:00:00Z",
              updated_at: "2026-09-28T00:00:00Z",
            },
            created_at: "2026-09-28T00:00:00Z",
            updated_at: "2026-09-28T00:00:00Z",
          },
        ],
        total: 1,
      }));
    });

    render(
      <MemoryRouter>
        <AuthProvider>
          <GlobalErrorProvider>
            <TemplateCenterPage />
          </GlobalErrorProvider>
        </AuthProvider>
      </MemoryRouter>,
    );

    await waitFor(() => expect(screen.getByText("Customer quotation")).toBeInTheDocument());
    expect(screen.getAllByText("待配置映射")).toHaveLength(1);
    expect(screen.getByText("4")).toBeInTheDocument();
    expect(screen.getByText("quotation.pptx")).toBeInTheDocument();
  });

  it("lets an administrator delete an import template after confirmation", async () => {
    window.sessionStorage.setItem("productflow.access_token", "test-token");
    const fetchMock = vi.spyOn(window, "fetch").mockImplementation((input, init) => {
      const url = String(input);
      if (url.endsWith("/auth/me")) {
        return Promise.resolve(Response.json({
          user: { id: "user-1", tenant_id: "tenant-1", username: "admin", email: "admin@example.com", role: "admin", is_platform_admin: false, status: "active" },
          tenant: { id: "tenant-1", name: "Tenant", slug: "tenant" },
        }));
      }
      if (url.endsWith("/output-templates")) return Promise.resolve(Response.json({ items: [], total: 0 }));
      if (url.endsWith("/import-templates/import-template-1") && init?.method === "DELETE") {
        return Promise.resolve(new Response(null, { status: 204 }));
      }
      if (url.endsWith("/import-templates")) {
        return Promise.resolve(Response.json({
          items: [{
            id: "import-template-1",
            tenant_id: "tenant-1",
            name: "供应商映射",
            description: null,
            source_type: "xlsx",
            mapping_config: { version: "1.0", sheet_names: ["Products"], header_row: 1, data_start_row: 2, fields: [] },
            status: "active",
            created_at: "2026-09-28T00:00:00Z",
            updated_at: "2026-09-28T00:00:00Z",
          }],
          total: 1,
        }));
      }
      return Promise.reject(new Error(`Unexpected request: ${url}`));
    });

    render(
      <MemoryRouter>
        <AuthProvider>
          <GlobalErrorProvider>
            <TemplateCenterPage />
          </GlobalErrorProvider>
        </AuthProvider>
      </MemoryRouter>,
    );

    fireEvent.click(await screen.findByRole("button", { name: "删除导入模板 供应商映射" }));
    fireEvent.click(screen.getByRole("button", { name: "永久删除模板" }));
    await waitFor(() => expect(screen.queryByText("供应商映射")).not.toBeInTheDocument());
    expect(fetchMock).toHaveBeenCalledWith(
      "/api/v1/import-templates/import-template-1",
      expect.objectContaining({ method: "DELETE" }),
    );
  });
});
