"use client";

import { sidebarItems } from "@/lib/sample-data";

type AdminSidebarProps = {
  activeTab: string;
  onSelectTab: (tabId: string) => void;
};

export function AdminSidebar({ activeTab, onSelectTab }: AdminSidebarProps) {
  return (
    <aside className="sidebar">
      <div className="sidebar-brand">
        <p className="eyebrow">RevGenie</p>
        <h1>Admin Console</h1>
      </div>

      <nav className="sidebar-nav" aria-label="Admin sections">
        {sidebarItems.map((item) => (
          <button
            key={item.id}
            type="button"
            className={activeTab === item.id ? "nav-item nav-item-active" : "nav-item"}
            aria-current={activeTab === item.id ? "page" : undefined}
            onClick={() => onSelectTab(item.id)}
          >
            <span>{item.label}</span>
            <small>{item.description}</small>
          </button>
        ))}
      </nav>
    </aside>
  );
}
