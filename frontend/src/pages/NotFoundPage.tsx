import { Link } from "react-router-dom";

export function NotFoundPage() {
  return (
    <main className="grid min-h-screen place-items-center p-6 text-center">
      <div>
        <p className="text-sm font-medium text-blue-600">404</p>
        <h1 className="mt-2 text-2xl font-semibold text-slate-950">页面不存在</h1>
        <Link to="/dashboard" className="mt-5 inline-block text-sm font-medium text-blue-600">
          返回系统概览
        </Link>
      </div>
    </main>
  );
}

