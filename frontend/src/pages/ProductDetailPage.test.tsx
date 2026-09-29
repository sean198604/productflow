import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { afterEach, describe, expect, it, vi } from "vitest";

import { GlobalErrorProvider } from "../components/errors/GlobalErrorProvider";
import { ProductDetailPage } from "./ProductDetailPage";

const product = {
  id: "product-id",
  tenant_id: "tenant-id",
  sku: "PF-001",
  product_name: "Outdoor Wall Light",
  description: null,
  category: "Lighting",
  brand: "ProductFlow",
  status: "active",
  custom_fields: {},
  image_count: 2,
  primary_image_url: "/api/v1/product-images/image-1/content",
  created_at: "2026-09-25T00:00:00Z",
  updated_at: "2026-09-25T00:00:00Z",
};

const images = [
  {
    id: "image-1",
    product_id: "product-id",
    product_sku: "PF-001",
    product_name: "Outdoor Wall Light",
    image_type: "main",
    sort_order: 0,
    is_primary: true,
    original_filename: "front.png",
    safe_filename: "front.png",
    sha256: "a".repeat(64),
    mime_type: "image/png",
    size_bytes: 1200,
    width: 800,
    height: 800,
    match_method: "manual",
    match_confidence: 1,
    match_source: "upload",
    content_url: "/api/v1/product-images/image-1/content",
    created_at: "2026-09-25T00:00:00Z",
  },
  {
    id: "image-2",
    product_id: "product-id",
    product_sku: "PF-001",
    product_name: "Outdoor Wall Light",
    image_type: "main",
    sort_order: 1,
    is_primary: false,
    original_filename: "side.png",
    safe_filename: "side.png",
    sha256: "b".repeat(64),
    mime_type: "image/png",
    size_bytes: 1100,
    width: 800,
    height: 800,
    match_method: "manual",
    match_confidence: 1,
    match_source: "upload",
    content_url: "/api/v1/product-images/image-2/content",
    created_at: "2026-09-25T00:00:00Z",
  },
];

describe("ProductDetailPage", () => {
  afterEach(() => vi.restoreAllMocks());

  it("distinguishes the actual primary image from other product images", async () => {
    vi.spyOn(window, "fetch").mockImplementation((input) => {
      const url = String(input);
      if (url.endsWith("/products/product-id")) {
        return Promise.resolve(Response.json(product));
      }
      if (url.endsWith("/field-definitions")) {
        return Promise.resolve(Response.json({ items: [] }));
      }
      if (url.endsWith("/products/product-id/images")) {
        return Promise.resolve(Response.json({ items: images }));
      }
      return Promise.reject(new Error("Image content is not needed for this UI test."));
    });

    render(
      <MemoryRouter initialEntries={["/products/product-id"]}>
        <GlobalErrorProvider>
          <Routes>
            <Route path="/products/:productId" element={<ProductDetailPage />} />
          </Routes>
        </GlobalErrorProvider>
      </MemoryRouter>,
    );

    await waitFor(() => expect(screen.getByText("当前主图")).toBeInTheDocument());
    expect(screen.getAllByText("产品图")).toHaveLength(2);
    expect(screen.getAllByText("主图")).toHaveLength(1);
    expect(screen.getByRole("button", { name: "设为主图" })).toBeInTheDocument();
  });

  it("requires confirmation before permanently deleting a product", async () => {
    const fetchMock = vi.spyOn(window, "fetch").mockImplementation((input, init) => {
      const url = String(input);
      if (url.endsWith("/products/product-id") && init?.method === "DELETE") {
        return Promise.resolve(new Response(null, { status: 204 }));
      }
      if (url.endsWith("/products/product-id")) return Promise.resolve(Response.json(product));
      if (url.endsWith("/field-definitions")) return Promise.resolve(Response.json({ items: [] }));
      if (url.endsWith("/products/product-id/images")) return Promise.resolve(Response.json({ items: [] }));
      return Promise.reject(new Error("Unexpected request"));
    });

    render(
      <MemoryRouter initialEntries={["/products/product-id"]}>
        <GlobalErrorProvider>
          <Routes>
            <Route path="/products/:productId" element={<ProductDetailPage />} />
            <Route path="/products" element={<div>产品列表</div>} />
          </Routes>
        </GlobalErrorProvider>
      </MemoryRouter>,
    );

    fireEvent.click(await screen.findByRole("button", { name: "删除产品" }));
    expect(screen.getByRole("dialog", { name: "删除产品 PF-001" })).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "永久删除产品" }));
    await waitFor(() => expect(screen.getByText("产品列表")).toBeInTheDocument());
    expect(fetchMock).toHaveBeenCalledWith(
      "/api/v1/products/product-id",
      expect.objectContaining({ method: "DELETE" }),
    );
  });
});
