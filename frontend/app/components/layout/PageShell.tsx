import type { HTMLAttributes } from "react";

interface PageShellProps extends HTMLAttributes<HTMLElement> {
  constrained?: boolean;
}

export default function PageShell({ constrained = true, className = "", children, ...props }: PageShellProps) {
  return (
    <main className={`flex-1 p-4 lg:p-6 ${className}`} {...props}>
      <div className={`mx-auto transition-[max-width] duration-300 ease-out ${constrained ? "max-w-7xl 2xl:max-w-[1600px] min-[2560px]:max-w-[2200px] min-[3840px]:max-w-[3200px]" : "max-w-none"}`}>
        {children}
      </div>
    </main>
  );
}

