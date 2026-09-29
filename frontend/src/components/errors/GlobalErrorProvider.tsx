import {
  createContext,
  type ReactNode,
  useCallback,
  useContext,
  useMemo,
  useState,
} from "react";
import { X } from "lucide-react";

type ErrorContextValue = {
  reportError: (message: string) => void;
};

const ErrorContext = createContext<ErrorContextValue | null>(null);

export function GlobalErrorProvider({ children }: { children: ReactNode }) {
  const [message, setMessage] = useState<string | null>(null);
  const reportError = useCallback((nextMessage: string) => setMessage(nextMessage), []);
  const value = useMemo(() => ({ reportError }), [reportError]);

  return (
    <ErrorContext.Provider value={value}>
      {message ? (
        <div
          role="alert"
          className="fixed inset-x-4 top-4 z-50 mx-auto flex max-w-2xl items-center justify-between gap-4 rounded-xl border border-red-200 bg-white px-4 py-3 text-sm text-red-700 shadow-lg"
        >
          <span>{message}</span>
          <button
            type="button"
            aria-label="关闭错误提示"
            className="rounded-md p-1 hover:bg-red-50"
            onClick={() => setMessage(null)}
          >
            <X aria-hidden="true" className="size-4" />
          </button>
        </div>
      ) : null}
      {children}
    </ErrorContext.Provider>
  );
}

export function useGlobalError() {
  const value = useContext(ErrorContext);
  if (!value) {
    throw new Error("useGlobalError must be used inside GlobalErrorProvider");
  }
  return value;
}

