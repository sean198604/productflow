import { Component, type ErrorInfo, type ReactNode } from "react";

type Props = { children: ReactNode };
type State = { hasError: boolean };

export class AppErrorBoundary extends Component<Props, State> {
  state: State = { hasError: false };

  static getDerivedStateFromError(): State {
    return { hasError: true };
  }

  componentDidCatch(error: Error, info: ErrorInfo) {
    console.error("Uncaught application error", error, info);
  }

  render() {
    if (this.state.hasError) {
      return (
        <main className="grid min-h-screen place-items-center p-6">
          <section className="max-w-md rounded-2xl border border-slate-200 bg-white p-8 shadow-sm">
            <p className="text-sm font-medium text-blue-600">ProductFlow</p>
            <h1 className="mt-2 text-xl font-semibold text-slate-900">页面暂时无法显示</h1>
            <p className="mt-3 text-sm leading-6 text-slate-600">
              应用遇到了未预期的问题。请刷新页面；如果问题持续，请联系管理员。
            </p>
          </section>
        </main>
      );
    }

    return this.props.children;
  }
}

