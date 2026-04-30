import type { HTMLAttributes } from "react";

type GridColumns = "auto" | "two" | "three" | "four";

interface ContentGridProps extends HTMLAttributes<HTMLDivElement> {
  columns?: GridColumns;
}

const columnsClass: Record<GridColumns, string> = {
  auto: "grid-cols-1",
  two: "grid-cols-1 lg:grid-cols-2",
  three: "grid-cols-1 md:grid-cols-2 xl:grid-cols-3",
  four: "grid-cols-1 sm:grid-cols-2 xl:grid-cols-4",
};

export default function ContentGrid({ columns = "auto", className = "", ...props }: ContentGridProps) {
  return <div className={`grid gap-4 ${columnsClass[columns]} ${className}`} {...props} />;
}

