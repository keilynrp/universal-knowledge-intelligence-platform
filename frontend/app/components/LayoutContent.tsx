"use client";

import { useEffect } from "react";
import { usePathname, useRouter } from "next/navigation";
import { useSidebar } from "./SidebarProvider";
import Sidebar from "./Sidebar";
import Header from "./Header";
import { useAuth } from "../contexts/AuthContext";
import { AppShell, PageShell } from "./layout";

export default function LayoutContent({ children }: { children: React.ReactNode }) {
  const { collapsed } = useSidebar();
  const { isAuthenticated, hydrated } = useAuth();
  const pathname = usePathname();
  const router = useRouter();

  const isLoginPage = pathname === "/login";
  const isPublicCatalogRoute = pathname.startsWith("/catalogs/") && pathname !== "/catalogs";

  useEffect(() => {
    if (!hydrated) return;
    if (!isAuthenticated && !isLoginPage && !isPublicCatalogRoute) {
      router.replace("/login");
    }
  }, [hydrated, isAuthenticated, isLoginPage, isPublicCatalogRoute, router]);

  // Block ALL rendering until auth state is resolved from localStorage.
  // Server renders null, client hydration also renders null (hydrated starts false),
  // so the DOM matches — zero hydration mismatch possible.
  if (!hydrated) {
    return null;
  }

  // Login page renders without the shell (no sidebar / header)
  if (isLoginPage) {
    return <>{children}</>;
  }

  if (isPublicCatalogRoute && !isAuthenticated) {
    return <>{children}</>;
  }

  // Brief blank while the redirect above takes effect
  if (!isAuthenticated) {
    return null;
  }

  return (
    <AppShell sidebar={<Sidebar />} header={<Header />} collapsed={collapsed}>
      <PageShell constrained={!collapsed}>{children}</PageShell>
    </AppShell>
  );
}
