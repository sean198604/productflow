import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { AuthProvider } from "../auth/AuthProvider";
import { GlobalErrorProvider } from "../components/errors/GlobalErrorProvider";
import type { ImportJob } from "../types/imports";
import { ImportsPage, suggestedMapping } from "./ImportsPage";

const analyzedJob: ImportJob = {
  id: "job-id",
  tenant_id: "tenant-id",
  import_template_id: null,
  source_file_id: "file-id",
  source_filename: "products.xlsx",
  source_sha256: "a".repeat(64),
  status: "analyzed",
  analysis: {
    workbook_filename: "products.xlsx",
    workbook_sha256: "a".repeat(64),
    markitdown: { status: "ok" },
    sheets: [
      {
        name: "Products",
        max_row: 2,
        max_column: 2,
        merged_cells: [],
        headers: [
          { column: "A", column_index: 1, value: "SKU" },
          { column: "B", column_index: 2, value: "Product Name" },
        ],
        sample_rows: [],
        images: [],
        suggested_mapping: [
          { source: "A", source_header: "SKU", target: "sku", transform: "trim", required: true, confidence: 1, method: "header_alias" },
          { source: "B", source_header: "Product Name", target: "product_name", transform: "trim", required: true, confidence: 1, method: "header_alias" },
        ],
      },
    ],
  },
  mapping_snapshot: null,
  duplicate_strategy: null,
  total_rows: 0,
  valid_rows: 0,
  imported_rows: 0,
  skipped_rows: 0,
  conflict_rows: 0,
  error_message: null,
  rows: [],
  images: [],
  completed_at: null,
  created_at: "2026-09-26T00:00:00Z",
  updated_at: "2026-09-26T00:00:00Z",
};

const previewJob: ImportJob = {
  ...analyzedJob,
  status: "preview_ready",
  total_rows: 1,
  valid_rows: 1,
  mapping_snapshot: {
    version: "1.0",
    sheet_names: ["Products"],
    header_row: 1,
    data_start_row: 2,
    fields: [
      { source: "A", target: "sku", transform: "trim", default_value: null, required: true, validation: {}, formatter: null },
      { source: "B", target: "product_name", transform: "trim", default_value: null, required: true, validation: {}, formatter: null },
    ],
  },
  rows: [
    {
      id: "row-id",
      source_sheet: "Products",
      source_row: 2,
      source_data: { A: "PF-001", B: "Garden Light" },
      mapped_data: { sku: "PF-001", product_name: "Garden Light" },
      status: "valid",
      action: "create",
      errors: [],
      product_id: null,
    },
  ],
};

describe("ImportsPage", () => {
  beforeEach(() => window.sessionStorage.clear());
  afterEach(() => vi.restoreAllMocks());

  it("defaults to the product sheet and skips a leading instruction row", () => {
    const job: ImportJob = {
      ...analyzedJob,
      analysis: {
        ...analyzedJob.analysis,
        sheets: [
          {
            ...analyzedJob.analysis.sheets[0],
            name: "产品资料",
            max_row: 3,
            sample_rows: [
              { row: 2, cells: { B: "第2行为说明行，导入时应忽略" }, formats: {} },
              { row: 3, cells: { A: "NT-HH-001", B: "游戏与手表" }, formats: {} },
            ],
          },
          {
            ...analyzedJob.analysis.sheets[0],
            name: "图片来源",
            max_row: 4,
            sample_rows: [
              { row: 2, cells: { A: "NT-HH-001", B: "游戏与手表" }, formats: {} },
              { row: 3, cells: { A: "NT-HH-001", B: "游戏与手表" }, formats: {} },
              { row: 4, cells: { A: "NT-HH-001", B: "游戏与手表" }, formats: {} },
            ],
          },
        ],
      },
    };
    const mapping = suggestedMapping(job, [
      { id: "field-sku", code: "sku", label: "SKU", data_type: "text", scope: "customer", is_system: true, is_core: true, is_required: true, options: {}, sort_order: 1, status: "active" },
      { id: "field-name", code: "product_name", label: "产品名称", data_type: "text", scope: "customer", is_system: true, is_core: true, is_required: true, options: {}, sort_order: 2, status: "active" },
    ]);

    expect(mapping.sheet_names).toEqual(["产品资料"]);
    expect(mapping.data_start_row).toBe(3);
  });

  it("completes the upload, mapping, preview, and confirmation workflow", async () => {
    vi.spyOn(window, "fetch").mockImplementation(async (input, options) => {
      const url = String(input);
      if (url.endsWith("/import-templates")) return jsonResponse({ items: [], total: 0 });
      if (url.endsWith("/field-definitions")) {
        return jsonResponse({
          items: [
            { id: "field-sku", code: "sku", label: "SKU", data_type: "text", scope: "customer", is_system: true, is_core: true, is_required: true, options: {}, sort_order: 1, status: "active" },
            { id: "field-name", code: "product_name", label: "产品名称", data_type: "text", scope: "customer", is_system: true, is_core: true, is_required: true, options: {}, sort_order: 2, status: "active" },
          ],
        });
      }
      if (url.endsWith("/import-jobs") && (!options?.method || options.method === "GET")) return jsonResponse({ items: [], total: 0 });
      if (url.endsWith("/import-jobs/analyze")) return jsonResponse(analyzedJob, 201);
      if (url.endsWith("/import-jobs/job-id/preview")) return jsonResponse(previewJob);
      if (url.endsWith("/import-jobs/job-id/confirm")) {
        return jsonResponse({ ...previewJob, status: "completed", imported_rows: 1, completed_at: "2026-09-26T00:01:00Z" });
      }
      throw new Error(`Unexpected request: ${url}`);
    });

    render(
      <MemoryRouter>
        <AuthProvider>
          <GlobalErrorProvider>
            <ImportsPage />
          </GlobalErrorProvider>
        </AuthProvider>
      </MemoryRouter>,
    );

    await waitFor(() => expect(screen.getByText("上传供应商 Excel")).toBeInTheDocument());
    const fileInput = document.querySelector<HTMLInputElement>('input[type="file"]');
    expect(fileInput).not.toBeNull();
    fireEvent.change(fileInput!, { target: { files: [new File(["xlsx"], "products.xlsx")] } });
    fireEvent.click(screen.getByRole("button", { name: "开始分析" }));

    await waitFor(() => expect(screen.getByRole("button", { name: "生成导入预览" })).toBeInTheDocument());
    expect(screen.getByRole("option", { name: "A · SKU", selected: true })).toBeInTheDocument();
    expect(screen.getByRole("option", { name: "B · Product Name", selected: true })).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "生成导入预览" }));

    await waitFor(() => expect(screen.getByText("Garden Light")).toBeInTheDocument());
    expect(screen.getByText("PF-001")).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "确认并写入产品库" }));

    await waitFor(() => expect(screen.getByText("导入任务已完成")).toBeInTheDocument());
    expect(screen.getByText("成功写入")).toBeInTheDocument();
  });

  it("rejects files above 50 MB before sending the upload", async () => {
    const fetchMock = vi.spyOn(window, "fetch").mockImplementation(async (input) => {
      const url = String(input);
      if (url.endsWith("/import-templates")) return jsonResponse({ items: [], total: 0 });
      if (url.endsWith("/field-definitions")) return jsonResponse({ items: [] });
      if (url.endsWith("/import-jobs")) return jsonResponse({ items: [], total: 0 });
      throw new Error(`Unexpected request: ${url}`);
    });

    render(
      <MemoryRouter>
        <AuthProvider>
          <GlobalErrorProvider>
            <ImportsPage />
          </GlobalErrorProvider>
        </AuthProvider>
      </MemoryRouter>,
    );

    await waitFor(() => expect(screen.getByText("上传供应商 Excel")).toBeInTheDocument());
    const oversized = new File(["xlsx"], "oversized.xlsx");
    Object.defineProperty(oversized, "size", { value: 50 * 1024 * 1024 + 1 });
    const fileInput = document.querySelector<HTMLInputElement>('input[type="file"]');
    fireEvent.change(fileInput!, { target: { files: [oversized] } });
    fireEvent.click(screen.getByRole("button", { name: "开始分析" }));

    expect(await screen.findByRole("alert")).toHaveTextContent("Excel 文件不能超过 50 MB。");
    expect(
      fetchMock.mock.calls.some(([input]) => String(input).endsWith("/import-jobs/analyze")),
    ).toBe(false);
  });
});

function jsonResponse(payload: unknown, status = 200) {
  return Promise.resolve(
    new Response(JSON.stringify(payload), {
      status,
      headers: { "Content-Type": "application/json" },
    }),
  );
}
