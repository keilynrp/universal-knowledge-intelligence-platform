type IconName =
  | "award"
  | "calendar"
  | "chart"
  | "check"
  | "database"
  | "file"
  | "globe"
  | "institution"
  | "network"
  | "refresh"
  | "search"
  | "spark"
  | "target"
  | "users";

const ICON_PATHS: Record<IconName, string> = {
  award: "M12 15.5 8.5 19l.8-4.7A6 6 0 1 1 14.7 14.3l.8 4.7L12 15.5ZM12 12a3 3 0 1 0 0-6 3 3 0 0 0 0 6Z",
  calendar: "M7 3v3M17 3v3M4 9h16M6 5h12a2 2 0 0 1 2 2v11a2 2 0 0 1-2 2H6a2 2 0 0 1-2-2V7a2 2 0 0 1 2-2Z",
  chart: "M5 19V9M12 19V5M19 19v-7",
  check: "m5 12 4 4L19 6",
  database: "M5 7c0-2 3.1-3.5 7-3.5S19 5 19 7s-3.1 3.5-7 3.5S5 9 5 7Zm0 0v5c0 2 3.1 3.5 7 3.5s7-1.5 7-3.5V7M5 12v5c0 2 3.1 3.5 7 3.5s7-1.5 7-3.5v-5",
  file: "M7 3h7l4 4v14H7V3Zm7 0v5h5M9.5 13h5M9.5 17h7",
  globe: "M12 21a9 9 0 1 0 0-18 9 9 0 0 0 0 18ZM3.6 9h16.8M3.6 15h16.8M12 3c2.2 2.3 3.4 5.3 3.4 9s-1.2 6.7-3.4 9c-2.2-2.3-3.4-5.3-3.4-9S9.8 5.3 12 3Z",
  institution: "M4 10h16M5 20h14M7 10v8M12 10v8M17 10v8M12 3l8 5H4l8-5Z",
  network: "M12 12 6.5 8.5M12 12l5.5-3.5M12 12v6M6.5 8.5a2.5 2.5 0 1 0 0-5 2.5 2.5 0 0 0 0 5Zm11 0a2.5 2.5 0 1 0 0-5 2.5 2.5 0 0 0 0 5ZM12 21a2.5 2.5 0 1 0 0-5 2.5 2.5 0 0 0 0 5Z",
  refresh: "M4.5 12a7.5 7.5 0 0 1 12.7-5.4M19.5 12a7.5 7.5 0 0 1-12.7 5.4M17.5 4.5v4h-4M6.5 19.5v-4h4",
  search: "m21 21-4.4-4.4M10.8 18a7.2 7.2 0 1 1 0-14.4 7.2 7.2 0 0 1 0 14.4Z",
  spark: "M12 3v3M12 18v3M4.9 4.9 7 7M17 17l2.1 2.1M3 12h3M18 12h3M4.9 19.1 7 17M17 7l2.1-2.1M12 8l1.2 2.8L16 12l-2.8 1.2L12 16l-1.2-2.8L8 12l2.8-1.2L12 8Z",
  target: "M12 21a9 9 0 1 0 0-18 9 9 0 0 0 0 18Zm0-4.5a4.5 4.5 0 1 0 0-9 4.5 4.5 0 0 0 0 9Zm0-3a1.5 1.5 0 1 0 0-3 1.5 1.5 0 0 0 0 3Z",
  users: "M16 19v-1.2c0-1.7-1.8-3.1-4-3.1s-4 1.4-4 3.1V19M12 12a3.5 3.5 0 1 0 0-7 3.5 3.5 0 0 0 0 7Zm6.5 6.8v-.9c0-1.3-1.1-2.4-2.7-2.9M15.8 5.4a3 3 0 0 1 0 5.2",
};

interface ResearchIconProps {
  name: IconName;
  className?: string;
}

export default function ResearchIcon({ name, className = "h-4 w-4" }: ResearchIconProps) {
  return (
    <svg className={className} aria-hidden="true" fill="none" stroke="currentColor" viewBox="0 0 24 24">
      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.8} d={ICON_PATHS[name]} />
    </svg>
  );
}
