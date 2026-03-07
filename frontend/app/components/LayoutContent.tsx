"use client";

import { useEffect } from "react";
import { usePathname, useRouter } from "next/navigation";
import { useSidebar } from "./SidebarProvider";
import Sidebar from "./Sidebar";
import Header from "./Header";
import { useAuth } from "../contexts/AuthContext";

export default function LayoutContent({ children }: { children: React.ReactNode }) {
  const { collapsed } = useSidebar();
  const { isAuthenticated } = useAuth();
  const pathname = usePathname();
  const router = useRouter();

  const isLoginPage = pathname === "/login";

  useEffect(() => {
    if (!isAuthenticated && !isLoginPage) {
      router.replace("/login");
    }
  }, [isAuthenticated, isLoginPage, router]);

  // Login page renders without the shell (no sidebar / header)
  if (isLoginPage) {
    return <>{children}</>;
  }

  // Brief blank while the redirect above takes effect
  if (!isAuthenticated) {
    return null;
  }

  return (
    <div className="flex min-h-screen">
      <Sidebar />
      <div
        className={`flex flex-1 flex-col transition-all duration-300 ${
          collapsed ? "ml-20" : "ml-64"
        }`}
      >
        <Header />
        <main className="flex-1 bg-gray-50 p-6 transition-all duration-300 dark:bg-gray-950">
          <div
            className={`mx-auto transition-all duration-300 ${
              collapsed ? "max-w-none px-4" : "max-w-7xl"
            }`}
          >
            {children}
          </div>
        </main>
      </div>
    </div>
  );
}
