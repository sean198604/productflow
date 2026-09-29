import { render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { afterEach, describe, expect, it, vi } from "vitest";

import { GlobalErrorProvider } from "../components/errors/GlobalErrorProvider";
import { ProductsPage } from "./ProductsPage";

describe("ProductsPage", () => {
  afterEach(() => {
    vi.restoreAllMocks();
  });

  it("renders products returned by the tenant-scoped API", async () => {
    vi.spyOn(window, "fetch").mockResolvedValue(
      new Response(
        JSON.stringify({
          items: [
            {
              id: "product-id",
              tenant_id: "tenant-id",
              sku: "PF-001",
              product_name: "Outdoor Wall Light",
              description: null,
              category: "Lighting",
              brand: "ProductFlow",
              status: "active",
              custom_fields: {},
              image_count: 0,
              primary_image_url: null,
              created_at: "2026-09-25T00:00:00Z",
              updated_at: "2026-09-25T00:00:00Z",
            },
          ],
          total: 1,
          page: 1,
          page_size: 20,
        }),
        { status: 200, headers: { "Content-Type": "application/json" } },
      ),
    );

    render(
      <MemoryRouter>
        <GlobalErrorProvider>
          <ProductsPage />
        </GlobalErrorProvider>
      </MemoryRouter>,
    );

    await waitFor(() => expect(screen.getByText("Outdoor Wall Light")).toBeInTheDocument());
    expect(screen.getByText("PF-001")).toBeInTheDocument();
    expect(screen.getByText("共 1 个产品")).toBeInTheDocument();
  });
});
