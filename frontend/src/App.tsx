import { Navigate, Route, Routes } from "react-router-dom";
import { BrowserRouter } from "react-router-dom";

import { AuthProvider } from "./auth/AuthProvider";
import { PlatformAdminRoute } from "./auth/PlatformAdminRoute";
import { ProtectedRoute } from "./auth/ProtectedRoute";
import { AppLayout } from "./layouts/AppLayout";
import { AdminPage } from "./pages/AdminPage";
import { CustomersPage } from "./pages/CustomersPage";
import { DashboardPage } from "./pages/DashboardPage";
import { FieldDefinitionsPage } from "./pages/FieldDefinitionsPage";
import { GenerationCenterPage } from "./pages/GenerationCenterPage";
import { ImageLibraryPage } from "./pages/ImageLibraryPage";
import { ImportsPage } from "./pages/ImportsPage";
import { LoginPage } from "./pages/LoginPage";
import { NotFoundPage } from "./pages/NotFoundPage";
import { ProductDetailPage } from "./pages/ProductDetailPage";
import { ProductSetsPage } from "./pages/ProductSetsPage";
import { ProductsPage } from "./pages/ProductsPage";
import { TemplateCenterPage } from "./pages/TemplateCenterPage";
import { TemplateDetailPage } from "./pages/TemplateDetailPage";

export function App() {
  return (
    <BrowserRouter>
      <AuthProvider>
        <Routes>
          <Route path="/login" element={<LoginPage />} />
          <Route element={<ProtectedRoute />}>
            <Route element={<AppLayout />}>
              <Route path="/dashboard" element={<DashboardPage />} />
              <Route path="/products" element={<ProductsPage />} />
              <Route path="/products/:productId" element={<ProductDetailPage />} />
              <Route path="/product-sets" element={<ProductSetsPage />} />
              <Route path="/customers" element={<CustomersPage />} />
              <Route path="/imports" element={<ImportsPage />} />
              <Route path="/images" element={<ImageLibraryPage />} />
              <Route path="/fields" element={<FieldDefinitionsPage />} />
              <Route path="/templates" element={<TemplateCenterPage />} />
              <Route path="/templates/:templateId" element={<TemplateDetailPage />} />
              <Route path="/generation" element={<GenerationCenterPage />} />
              <Route element={<PlatformAdminRoute />}>
                <Route path="/admin" element={<AdminPage />} />
              </Route>
            </Route>
          </Route>
          <Route path="/" element={<Navigate to="/dashboard" replace />} />
          <Route path="*" element={<NotFoundPage />} />
        </Routes>
      </AuthProvider>
    </BrowserRouter>
  );
}
