import { fireEvent, render, screen, waitFor, within } from "@testing-library/react";
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

const secondProduct = {
  ...product,
  id: "product-two",
  sku: "PF-002",
  product_name: "Portable Garden Light",
  primary_image_url: null,
  created_at: "2026-09-26T00:00:00Z",
  updated_at: "2026-09-26T00:00:00Z",
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
    processed_content_url: "/api/v1/product-images/image-1/processed-content",
    processed_sha256: "c".repeat(64),
    processed_mime_type: "image/png",
    background_removed: true,
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
    processed_content_url: "/api/v1/product-images/image-2/processed-content",
    processed_sha256: "d".repeat(64),
    processed_mime_type: "image/png",
    background_removed: false,
    created_at: "2026-09-25T00:00:00Z",
  },
];

describe("ProductDetailPage", () => {
  afterEach(() => vi.restoreAllMocks());

  it("distinguishes the primary image and confirms before deleting an image", async () => {
    const fetchMock = vi.spyOn(window, "fetch").mockImplementation((input, init) => {
      const url = String(input);
      if (url.endsWith("/product-images/image-1") && init?.method === "DELETE") {
        return Promise.resolve(new Response(null, { status: 204 }));
      }
      if (url.endsWith("/products/product-id")) {
        return Promise.resolve(Response.json(product));
      }
      if (url.endsWith("/field-definitions")) {
        return Promise.resolve(Response.json({ items: [] }));
      }
      if (url.endsWith("/products/product-id/images")) {
        return Promise.resolve(Response.json({ items: images }));
      }
      if (url.endsWith("/product-dictionaries")) {
        return Promise.resolve(Response.json({ items: [] }));
      }
      if (url.includes("/products?page=1&page_size=100")) {
        return Promise.resolve(Response.json({ items: [product], total: 1, page: 1, page_size: 100 }));
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
    fireEvent.click(screen.getByRole("button", { name: "删除图片 front.png" }));
    expect(screen.getByRole("dialog", { name: "删除图片 front.png" })).toBeInTheDocument();
    expect(screen.getByText(/自动将下一张图片设为主图/)).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "永久删除图片" }));
    await waitFor(() => expect(screen.queryByRole("dialog", { name: "删除图片 front.png" })).not.toBeInTheDocument());
    expect(fetchMock).toHaveBeenCalledWith(
      "/api/v1/product-images/image-1",
      expect.objectContaining({ method: "DELETE" }),
    );
  });

  it("shows save success as a floating toast without changing the paging toolbar", async () => {
    vi.spyOn(window, "fetch").mockImplementation((input, init) => {
      const url = String(input);
      if (url.endsWith("/products/product-id") && init?.method === "PATCH") {
        return Promise.resolve(Response.json(product));
      }
      if (url.endsWith("/products/product-id")) return Promise.resolve(Response.json(product));
      if (url.endsWith("/field-definitions")) return Promise.resolve(Response.json({ items: [] }));
      if (url.endsWith("/products/product-id/images")) return Promise.resolve(Response.json({ items: [] }));
      if (url.endsWith("/product-dictionaries")) return Promise.resolve(Response.json({ items: [] }));
      if (url.includes("/products?page=1&page_size=100")) return Promise.resolve(Response.json({ items: [product], total: 1, page: 1, page_size: 100 }));
      return Promise.reject(new Error("Unexpected request"));
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

    const paging = await screen.findByRole("group", { name: "产品资料翻页" });
    const actionToolbar = paging.parentElement as HTMLElement;
    fireEvent.click(screen.getByRole("button", { name: "保存资料" }));
    const toast = await screen.findByRole("status");
    expect(toast).toHaveTextContent("资料已保存");
    expect(toast).toHaveClass("fixed");
    expect(within(actionToolbar).queryByText("资料已保存")).not.toBeInTheDocument();
    expect(within(paging).getAllByRole("button").map((button) => button.textContent?.trim())).toEqual(["上一个", "下一个"]);
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
      if (url.endsWith("/product-dictionaries")) return Promise.resolve(Response.json({ items: [] }));
      if (url.includes("/products?page=1&page_size=100")) return Promise.resolve(Response.json({ items: [product], total: 1, page: 1, page_size: 100 }));
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

  it("pins the product directory to the right and keeps paging controls in the detail header", async () => {
    vi.spyOn(window, "fetch").mockImplementation((input) => {
      const url = String(input);
      if (url.endsWith("/products/product-id")) return Promise.resolve(Response.json(product));
      if (url.endsWith("/products/product-two")) return Promise.resolve(Response.json(secondProduct));
      if (url.endsWith("/products/product-id/images") || url.endsWith("/products/product-two/images")) return Promise.resolve(Response.json({ items: [] }));
      if (url.endsWith("/field-definitions") || url.endsWith("/product-dictionaries")) return Promise.resolve(Response.json({ items: [] }));
      if (url.includes("/products?page=1&page_size=100")) return Promise.resolve(Response.json({ items: [secondProduct, product], total: 2, page: 1, page_size: 100 }));
      return Promise.reject(new Error(`Unexpected request: ${url}`));
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

    await waitFor(() => expect(screen.getByText("当前第 2 个，共 2 个")).toBeInTheDocument());
    const directory = screen.getByTestId("product-directory-panel");
    const paging = screen.getByRole("group", { name: "产品资料翻页" });
    expect(directory).toHaveClass("xl:fixed", "xl:right-0", "xl:w-[320px]");
    expect(screen.getByTestId("product-directory-scroll")).toHaveClass("overflow-y-auto");
    expect(within(directory).getAllByRole("link").map((link) => link.textContent)).toEqual([
      "Portable Garden LightPF-002",
      "Outdoor Wall LightPF-001",
    ]);
    expect(screen.getByRole("link", { name: /Portable Garden Light/ })).toBeInTheDocument();
    expect(within(directory).queryByRole("button", { name: "上一个" })).not.toBeInTheDocument();
    expect(within(directory).queryByRole("button", { name: "下一个" })).not.toBeInTheDocument();
    expect(within(paging).getByRole("button", { name: "下一个" })).toBeDisabled();
    fireEvent.click(within(paging).getByRole("button", { name: "上一个" }));
    await waitFor(() => expect(screen.getByRole("heading", { name: "Portable Garden Light" })).toBeInTheDocument());
    expect(within(paging).getByRole("button", { name: "上一个" })).toBeDisabled();
    expect(within(paging).getByRole("button", { name: "下一个" })).toBeEnabled();
    fireEvent.click(screen.getByRole("button", { name: "向右收缩产品列表" }));
    expect(screen.getByRole("button", { name: "展开产品列表" })).toBeInTheDocument();
    expect(directory).toHaveClass("xl:w-12");
  });
});
