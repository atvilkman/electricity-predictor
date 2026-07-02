"use client";
import { useState, ReactNode } from "react";

type Tab = { id: string; label: string; content: ReactNode };

export default function Tabs({ tabs }: { tabs: Tab[] }) {
  const [active, setActive] = useState(tabs[0].id);
  return (
    <div className="space-y-6">
      <div className="border-b border-gray-200">
        <nav className="flex gap-6">
          {tabs.map(t => (
            <button
              key={t.id}
              onClick={() => setActive(t.id)}
              className={`pb-3 text-sm font-medium border-b-2 -mb-px transition-colors ${
                active === t.id
                  ? "border-blue-600 text-blue-600"
                  : "border-transparent text-gray-500 hover:text-gray-700"
              }`}
            >
              {t.label}
            </button>
          ))}
        </nav>
      </div>
      <div>{tabs.find(t => t.id === active)?.content}</div>
    </div>
  );
}
