"use client";

import React, { createContext, useContext, useEffect, useCallback, ReactNode, useSyncExternalStore } from "react";

type Theme = "light" | "dark";

interface ThemeContextType {
    theme: Theme;
    setTheme: (theme: Theme) => void;
    toggleTheme: () => void;
}

const ThemeContext = createContext<ThemeContextType | undefined>(undefined);

const THEME_EVENT = "ukip-theme-change";
const DEFAULT_THEME: Theme = "light";

function applyTheme(theme: Theme) {
    document.documentElement.classList.toggle("dark", theme === "dark");
}

function subscribeTheme(onStoreChange: () => void): () => void {
    if (typeof window === "undefined") {
        return () => {};
    }
    const handleChange = () => onStoreChange();
    window.addEventListener("storage", handleChange);
    window.addEventListener(THEME_EVENT, handleChange);
    return () => {
        window.removeEventListener("storage", handleChange);
        window.removeEventListener(THEME_EVENT, handleChange);
    };
}

function getThemeSnapshot(): Theme {
    if (typeof window === "undefined") {
        return DEFAULT_THEME;
    }
    const saved = localStorage.getItem("app_theme") as Theme | null;
    if (saved === "light" || saved === "dark") {
        return saved;
    }
    return DEFAULT_THEME;
}

export function ThemeProvider({ children }: { children: ReactNode }) {
    const theme: Theme = useSyncExternalStore<Theme>(
        subscribeTheme,
        getThemeSnapshot,
        () => DEFAULT_THEME,
    );

    useEffect(() => {
        applyTheme(theme);
    }, [theme]);

    const setTheme = useCallback((newTheme: Theme) => {
        localStorage.setItem("app_theme", newTheme);
        window.dispatchEvent(new Event(THEME_EVENT));
    }, []);

    const toggleTheme = useCallback(() => {
        const next = theme === "dark" ? "light" : "dark";
        localStorage.setItem("app_theme", next);
        window.dispatchEvent(new Event(THEME_EVENT));
    }, [theme]);

    return (
        <ThemeContext.Provider value={{ theme, setTheme, toggleTheme }}>
            {children}
        </ThemeContext.Provider>
    );
}

export function useTheme() {
    const context = useContext(ThemeContext);
    if (context === undefined) {
        throw new Error("useTheme must be used within a ThemeProvider");
    }
    return context;
}
