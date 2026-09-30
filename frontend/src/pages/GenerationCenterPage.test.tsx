import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { afterEach, describe, expect, it, vi } from "vitest";

import { GlobalErrorProvider } from "../components/errors/GlobalErrorProvider";
import { GenerationCenterPage } from "./GenerationCenterPage";

describe("GenerationCenterPage", () => {
  afterEach(() => vi.restoreAllMocks());

  it("shows ready templates, mapped capacity, and immutable task history", async () => {
    vi.spyOn(window, "fetch").mockImplementation((input) => {
      const url = String(input);
      if (url.endsWith("/generation-tasks")) {
        return Promise.resolve(Response.json({
          items: [{
            id: "task-1",
            tenant_id: "tenant-1",
            name: "Autumn quotation",
            status: "completed",
            output_type: "pptx",
            customer_id: "customer-1",
            customer_name: "Customer A",
            product_set_id: "set-1",
            product_set_name: "Autumn set",
            output_template_version_id: "version-1",
            template_name: "Quotation deck",
            template_version_number: 1,
            product_count: 2,
            output_filename: "autumn.pptx",
            download_url: "/api/v1/generation-tasks/task-1/download",
            error_message: null,
            created_at: "2026-09-28T00:00:00Z",
            started_at: "2026-09-28T00:00:00Z",
            completed_at: "2026-09-28T00:00:01Z",
          }],
          total: 1,
        }));
      }
      if (url.endsWith("/customers")) {
        return Promise.resolve(Response.json({ items: [], total: 0 }));
      }
      if (url.endsWith("/product-sets")) {
        return Promise.resolve(Response.json({ items: [], total: 0 }));
      }
      if (url.endsWith("/output-templates")) {
        return Promise.resolve(Response.json({
          items: [{
            id: "template-1",
            tenant_id: "tenant-1",
            name: "Quotation deck",
            description: null,
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
              size_bytes: 100,
              validation_report: { format: "pptx", is_valid: true, object_count: 2, parameterizable_count: 2, unsupported_count: 0, objects: [], warnings: [], errors: [], capabilities: [], unsupported_capabilities: [] },
              mapping_config: { version: "1.0", template_sha256: "a".repeat(64), bindings: [{ object_key: "pptx:s1:shape:2", source: "product_name", visible: true, label: null, formatter: "text", default_value: null, fallback: [], transform: null, fit: null, position: null, product_slot: 2, allow_formula: false }] },
              status: "ready",
              created_at: "2026-09-28T00:00:00Z",
              updated_at: "2026-09-28T00:00:00Z",
            },
            created_at: "2026-09-28T00:00:00Z",
            updated_at: "2026-09-28T00:00:00Z",
          }],
          total: 1,
        }));
      }
      return Promise.resolve(Response.json({ items: [], total: 0, page: 1, page_size: 100 }));
    });

    render(
      <MemoryRouter>
        <GlobalErrorProvider>
          <GenerationCenterPage />
        </GlobalErrorProvider>
      </MemoryRouter>,
    );

    await waitFor(() => expect(screen.getByText("Autumn quotation")).toBeInTheDocument());
    expect(screen.getByText("Customer A · Autumn set · 2 个产品")).toBeInTheDocument();
    expect(screen.getByRole("option", { name: "Quotation deck · PPTX · v1" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /下载文件/ })).toBeInTheDocument();
  });

  it("selects imported products and downloads a standalone HTML quote", async () => {
    const requestBodies: unknown[] = [];
    vi.spyOn(URL, "createObjectURL").mockReturnValue("blob:html-quote");
    vi.spyOn(URL, "revokeObjectURL").mockImplementation(() => undefined);
    vi.spyOn(HTMLAnchorElement.prototype, "click").mockImplementation(() => undefined);
    vi.spyOn(window, "fetch").mockImplementation((input, init) => {
      const url = String(input);
      if (url.endsWith("/generation-tasks/html-quote")) {
        requestBodies.push(JSON.parse(String(init?.body)));
        return Promise.resolve(new Response("<!doctype html><title>Quote</title>", {
          headers: {
            "Content-Type": "text/html",
            "Content-Disposition": 'attachment; filename="handheld.html"',
          },
        }));
      }
      if (url.endsWith("/generation-tasks") || url.endsWith("/customers") || url.endsWith("/product-sets") || url.endsWith("/output-templates") || url.endsWith("/field-definitions")) {
        return Promise.resolve(Response.json({ items: [], total: 0 }));
      }
      if (url.includes("/products?")) {
        return Promise.resolve(Response.json({
          items: [{
            id: "product-1",
            tenant_id: "tenant-1",
            sku: "NT-HH-001",
            product_name: "游戏与手表",
            description: null,
            category: null,
            brand: null,
            status: "active",
            custom_fields: { price: "12500", price_usd: "79.42", currency: "JPY" },
            image_count: 3,
            primary_image_url: null,
            created_at: "2026-09-29T00:00:00Z",
            updated_at: "2026-09-29T00:00:00Z",
          }],
          total: 1,
          page: 1,
          page_size: 100,
        }));
      }
      return Promise.reject(new Error(`Unexpected request: ${url}`));
    });

    render(
      <MemoryRouter>
        <GlobalErrorProvider>
          <GenerationCenterPage />
        </GlobalErrorProvider>
      </MemoryRouter>,
    );

    await waitFor(() => expect(screen.getByText("游戏与手表")).toBeInTheDocument());
    expect(screen.getByText("NT-HH-001 · 3 图")).toBeInTheDocument();
    expect(screen.getByText("$79.42")).toBeInTheDocument();
    fireEvent.click(screen.getByLabelText("HTML 报价币种：日币 · JPY ¥"));
    expect(screen.getByText(/12,500/)).toBeInTheDocument();
    expect(screen.getByText("Editorial Luxury")).toBeInTheDocument();
    expect(screen.getByText("Bold Energy")).toBeInTheDocument();
    fireEvent.click(screen.getByText("Curated Journey"));
    fireEvent.click(screen.getByRole("button", { name: /生成并下载 HTML/ }));
    await waitFor(() => expect(requestBodies).toHaveLength(1));
    expect(requestBodies[0]).toMatchObject({
      title: "HANDHELD ARCHIVE",
      template_key: "journey",
      currency: "USD",
      currencies: ["USD", "JPY"],
      currency_symbols: { USD: "$", JPY: "¥" },
      product_ids: ["product-1"],
    });
  });
});
