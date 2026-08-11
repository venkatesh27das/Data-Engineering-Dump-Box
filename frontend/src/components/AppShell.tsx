import { useQuery } from "@tanstack/react-query";
import { Boxes, Hammer, ListTodo, Network, Settings } from "lucide-react";
import { NavLink, Outlet } from "react-router-dom";

import { getHealth } from "../services/health";
import { BrandMark } from "./BrandMark";
import { StatusIndicator } from "./StatusIndicator";

const navigation = [
  { to: "/", label: "Build", description: "Set up and launch runs", icon: Hammer, end: true },
  { to: "/queue", label: "Run Queue", description: "Monitor background jobs", icon: ListTodo },
  { to: "/assets", label: "Graph Assets", description: "Review generated assets", icon: Boxes },
  { to: "/graph", label: "Graph Explorer", description: "Visualize in Neo4j", icon: Network },
];

export function AppShell() {
  const health = useQuery({
    queryKey: ["health"],
    queryFn: ({ signal }) => getHealth(signal),
    refetchInterval: 30_000,
  });

  return (
    <div className="app-shell">
      <header className="topbar">
        <div className="brand text-primary">
          <BrandMark />
          <div>
            <div className="brand-title">Knowledge Graph Builder</div>
            <div className="brand-subtitle">Generate graph-ready assets from your data</div>
          </div>
        </div>
        <div className="topbar-actions">
          <StatusIndicator
            isError={health.isError}
            isLoading={health.isLoading}
            label={health.data?.model_provider_name ?? "LM Studio"}
            status={health.data?.model_provider ?? health.data?.lmstudio}
          />
          <StatusIndicator
            isError={health.isError}
            isLoading={health.isLoading}
            label="Neo4j Aura"
            status={health.data?.neo4j}
          />
          <button aria-label="Settings are configured through the environment file" className="settings-button" disabled title="Configure integrations in .env" type="button">
            <Settings aria-hidden="true" size={18} />
            <span>Settings</span>
          </button>
        </div>
      </header>

      <aside className="sidebar">
        <nav aria-label="Primary navigation" className="nav-list">
          {navigation.map(({ to, label, description, icon: Icon, end }) => (
            <NavLink
              className={({ isActive }) => `nav-item ${isActive ? "nav-item-active" : ""}`}
              end={end}
              key={to}
              to={to}
            >
              <Icon aria-hidden="true" className="nav-icon" size={20} strokeWidth={1.8} />
              <span>
                <strong>{label}</strong>
                <small>{description}</small>
              </span>
            </NavLink>
          ))}
        </nav>

        <div className="mode-card">
          <div className="flex items-center gap-2 font-semibold text-ink">
            <span>POC Mode</span>
            <span aria-hidden="true" className="info-dot">i</span>
          </div>
          <p>Local AI • Agentic Pipeline</p>
        </div>
      </aside>

      <main className="main-content">
        <Outlet />
      </main>
    </div>
  );
}
