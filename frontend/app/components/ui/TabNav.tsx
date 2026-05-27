"use client";

interface Tab {
  id: string;
  label: string;
  badge?: string | number;
}

interface TabNavProps {
  tabs: Tab[];
  activeTab: string;
  onTabChange: (tabId: string) => void;
}

export default function TabNav({ tabs, activeTab, onTabChange }: TabNavProps) {
  return (
    <div className="overflow-x-auto border-b border-gray-200 dark:border-gray-800">
      <nav className="-mb-px flex min-w-max gap-2 sm:gap-4" role="tablist" aria-label="Section tabs">
        {tabs.map((tab) => {
          const isActive = tab.id === activeTab;
          return (
            <button
              type="button"
              key={tab.id}
              role="tab"
              aria-selected={isActive}
              onClick={() => onTabChange(tab.id)}
              className={`shrink-0 border-b-2 px-2 pb-3 text-sm font-medium transition-colors ${
                isActive
                  ? "border-blue-600 text-blue-600 dark:border-blue-400 dark:text-blue-400"
                  : "border-transparent text-gray-500 hover:border-gray-300 hover:text-gray-700 dark:text-gray-400 dark:hover:border-gray-600 dark:hover:text-gray-300"
              }`}
            >
              {tab.label}
              {tab.badge !== undefined && (
                <span className="ml-1.5 rounded-full bg-gray-100 px-2 py-0.5 text-xs font-medium text-gray-600 dark:bg-gray-800 dark:text-gray-400">
                  {tab.badge}
                </span>
              )}
            </button>
          );
        })}
      </nav>
    </div>
  );
}
