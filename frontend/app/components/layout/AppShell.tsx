import type { ReactNode } from "react";

interface AppShellProps {
  sidebar: ReactNode;
  header: ReactNode;
  children: ReactNode;
  collapsed?: boolean;
}

export default function AppShell({ sidebar, header, children, collapsed = false }: AppShellProps) {
  return (
    <div className="ukip-app-shell flex min-h-screen overflow-x-clip">
      {sidebar}
      <div
        className={`flex min-w-0 flex-1 flex-col transition-[margin,width] duration-300 ease-out ${
          collapsed
            ? "lg:ml-16 lg:w-[calc(100%-4rem)]"
            : "lg:ml-64 lg:w-[calc(100%-16rem)]"
        }`}
      >
        {header}
        {children}
      </div>
    </div>
  );
}
