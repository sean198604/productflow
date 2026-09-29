import { render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { afterEach, describe, expect, it, vi } from "vitest";

import { AuthProvider } from "../auth/AuthProvider";
import { GlobalErrorProvider } from "../components/errors/GlobalErrorProvider";
import { TemplateDetailPage } from "./TemplateDetailPage";

const version = {
  id: "version-2",
  version_number: 2,
  template_sha256: "b".repeat(64),
  original_filename: "quotation-v2.pptx",
  safe_filename: "quotation-v2.pptx",
  mime_type: "application/vnd.openxmlformats-officedocument.presentationml.presentation",
  size_bytes: 1024,
  validation_report: {
    format: "pptx",
    is_valid: true,
    object_count: 2,
    parameterizable_count: 1,
    unsupported_count: 1,
    template_changed: true,
    fingerprint_message: "模板文件发生变化，请重新验证字段映射。",
    objects: [
      {
        object_key: "pptx:s1:shape:2",
        container: "Slide 1",
        slide_index: 1,
        shape_id: 2,
        shape_name: "Product title",
        object_type: "text",
        supported: true,
        reason: null,
        preview: "Product Name",
        position: { x: 10, y: 10 },
        size: { width: 100, height: 30 },
        font: {},
      },
      {
        object_key: "pptx:s1:shape:3",
        container: "Slide 1",
        slide_index: 1,
        shape_id: 3,
        shape_name: "Sales chart",
        object_type: "chart",
        supported: false,
        reason: "复杂图表暂不支持",
        preview: null,
        position: {},
        size: {},
        font: {},
      },
    ],
    warnings: [],
    errors: [],
    capabilities: ["text"],
    unsupported_capabilities: ["complex_chart"],
  },
  mapping_config: {
    version: "1.0",
    template_sha256: "b".repeat(64),
    bindings: [],
  },
  status: "needs_mapping",
  created_at: "2026-09-28T00:00:00Z",
  updated_at: "2026-09-28T00:00:00Z",
};

describe("TemplateDetailPage", () => {
  afterEach(() => vi.restoreAllMocks());

  it("shows fingerprint warning and excludes internal fields from mappings", async () => {
    vi.spyOn(window, "fetch").mockImplementation((input) => {
      const url = String(input);
      if (url.endsWith("/field-definitions")) {
        return Promise.resolve(Response.json({
          items: [
            { id: "field-1", code: "product_name", label: "Product Name", data_type: "text", scope: "customer", is_system: true, is_core: true, is_required: true, options: {}, sort_order: 1, status: "active" },
            { id: "field-2", code: "supplier_cost", label: "Supplier Cost", data_type: "money", scope: "internal", is_system: true, is_core: false, is_required: false, options: {}, sort_order: 2, status: "active" },
          ],
        }));
      }
      return Promise.resolve(Response.json({
        id: "template-1",
        tenant_id: "tenant-1",
        name: "Customer quotation",
        description: null,
        output_type: "pptx",
        status: "active",
        current_version_number: 2,
        current_version: version,
        versions: [version],
        created_at: "2026-09-28T00:00:00Z",
        updated_at: "2026-09-28T00:00:00Z",
      }));
    });

    render(
      <MemoryRouter initialEntries={["/templates/template-1"]}>
        <AuthProvider>
          <GlobalErrorProvider>
            <Routes>
              <Route path="/templates/:templateId" element={<TemplateDetailPage />} />
            </Routes>
          </GlobalErrorProvider>
        </AuthProvider>
      </MemoryRouter>,
    );

    await waitFor(() => expect(screen.getByText("模板文件发生变化，请重新验证字段映射。")).toBeInTheDocument());
    expect(screen.getByRole("option", { name: "Product Name · product_name" })).toBeInTheDocument();
    expect(screen.queryByRole("option", { name: /Supplier Cost/ })).not.toBeInTheDocument();
    expect(screen.getByText("复杂图表暂不支持")).toBeInTheDocument();
  });
});
