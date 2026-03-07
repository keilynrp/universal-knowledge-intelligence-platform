"use client";

import { createContext, useContext, useState, useCallback, ReactNode } from "react";

type ToastVariant = "success" | "error" | "warning" | "info";

interface ToastItem {
    id: number;
    message: string;
    variant: ToastVariant;
}

interface ToastContextValue {
    toast: (message: string, variant?: ToastVariant) => void;
}

const ToastContext = createContext<ToastContextValue>({ toast: () => {} });

export function useToast() {
    return useContext(ToastContext);
}

const STYLES: Record<ToastVariant, string> = {
    success: "border-green-200 bg-green-50 text-green-800 dark:border-green-700/50 dark:bg-green-900/30 dark:text-green-300",
    error:   "border-red-200 bg-red-50 text-red-800 dark:border-red-700/50 dark:bg-red-900/30 dark:text-red-300",
    warning: "border-yellow-200 bg-yellow-50 text-yellow-800 dark:border-yellow-700/50 dark:bg-yellow-900/30 dark:text-yellow-300",
    info:    "border-blue-200 bg-blue-50 text-blue-800 dark:border-blue-700/50 dark:bg-blue-900/30 dark:text-blue-300",
};

const ICON_STYLES: Record<ToastVariant, string> = {
    success: "bg-green-100 text-green-600 dark:bg-green-800 dark:text-green-300",
    error:   "bg-red-100 text-red-600 dark:bg-red-800 dark:text-red-300",
    warning: "bg-yellow-100 text-yellow-600 dark:bg-yellow-800 dark:text-yellow-300",
    info:    "bg-blue-100 text-blue-600 dark:bg-blue-800 dark:text-blue-300",
};

const ICONS: Record<ToastVariant, string> = {
    success: "✓",
    error:   "✕",
    warning: "⚠",
    info:    "i",
};

let nextId = 0;
const DURATION = 4500;

export function ToastProvider({ children }: { children: ReactNode }) {
    const [toasts, setToasts] = useState<ToastItem[]>([]);

    const toast = useCallback((message: string, variant: ToastVariant = "info") => {
        const id = ++nextId;
        setToasts(prev => [...prev, { id, message, variant }]);
        setTimeout(() => setToasts(prev => prev.filter(t => t.id !== id)), DURATION);
    }, []);

    const dismiss = useCallback((id: number) => {
        setToasts(prev => prev.filter(t => t.id !== id));
    }, []);

    return (
        <ToastContext.Provider value={{ toast }}>
            {children}
            <div
                aria-live="polite"
                aria-label="Notifications"
                className="fixed bottom-5 right-5 z-[200] flex flex-col gap-2 pointer-events-none"
            >
                {toasts.map(t => (
                    <div
                        key={t.id}
                        className={`flex items-start gap-3 rounded-xl border px-4 py-3 shadow-lg pointer-events-auto toast-enter ${STYLES[t.variant]}`}
                        style={{ minWidth: 280, maxWidth: 420 }}
                    >
                        <span className={`flex h-6 w-6 shrink-0 items-center justify-center rounded-full text-xs font-bold ${ICON_STYLES[t.variant]}`}>
                            {ICONS[t.variant]}
                        </span>
                        <p className="flex-1 text-sm font-medium leading-snug">{t.message}</p>
                        <button
                            onClick={() => dismiss(t.id)}
                            className="shrink-0 rounded p-0.5 opacity-50 hover:opacity-100 transition-opacity"
                            aria-label="Dismiss"
                        >
                            <svg className="h-3.5 w-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
                            </svg>
                        </button>
                    </div>
                ))}
            </div>
        </ToastContext.Provider>
    );
}
