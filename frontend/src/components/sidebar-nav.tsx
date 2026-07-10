"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useEffect, useState } from "react";
import { api } from "@/lib/api";
import { cn } from "@/lib/utils";
import { MessageSquare, Upload, Search, Settings, Bot, Terminal } from "lucide-react";

const navItems = [
  { icon: MessageSquare, label: "Enterprise RAG", href: "/chat" },
  { icon: Bot, label: "Multi-Tenant Sharding", href: "/sharding" },
  { icon: Search, label: "Debugger", href: "/search" },
  { icon: Terminal, label: "PageRank", href: "/pagerank" },
  { icon: Upload, label: "Upload", href: "/upload" },
  { icon: Settings, label: "Settings", href: "/settings" },
];

export function SidebarNav() {
  const pathname = usePathname();
  const [healthStatus, setHealthStatus] = useState<{status: string, [key: string]: unknown} | null>(null);

  useEffect(() => {
    let mounted = true;
    const fetchHealth = async () => {
      try {
        const res = await api.health();
        if (mounted) setHealthStatus(res);
      } catch {
        if (mounted) setHealthStatus({ status: "unhealthy", error: true });
      }
    };
    fetchHealth();
    const interval = setInterval(fetchHealth, 30000);
    return () => {
      mounted = false;
      clearInterval(interval);
    };
  }, []);

  const isHealthy = healthStatus?.status === "healthy";
  const statusColor = !healthStatus ? "bg-amber-500" : isHealthy ? "bg-green-500" : "bg-red-500";
  const statusText = !healthStatus ? "Checking services..." : isHealthy ? "All services operational. GPU inference ready." : "System performance degraded. Some services offline.";

  return (
    <aside className="w-16 md:w-64 border-r border-border bg-background flex flex-col transition-all duration-300">
      <div className="p-6 flex items-center gap-3">
        <div className="w-8 h-8 bg-primary rounded-lg flex items-center justify-center">
          <Terminal className="w-5 h-5 text-primary-foreground" />
        </div>
        <span className="font-bold hidden md:block">RAG Monorepo</span>
      </div>

      <nav className="flex-1 px-3 space-y-1">
        {navItems.map((item) => {
          const isActive = pathname === item.href;
          return (
            <Link
              key={item.href}
              href={item.href}
              className={cn(
                "flex items-center gap-3 px-3 py-2.5 rounded-xl transition-all group",
                isActive 
                  ? "bg-primary text-primary-foreground shadow-md shadow-primary/20" 
                  : "text-muted-foreground hover:bg-muted hover:text-foreground"
              )}
            >
              <item.icon className={cn(
                "w-5 h-5 transition-transform group-hover:scale-110",
                isActive ? "text-primary-foreground" : "text-muted-foreground"
              )} />
              <span className="font-medium hidden md:block">{item.label}</span>
            </Link>
          );
        })}
      </nav>

      <div className="p-4 border-t border-border mt-auto">
        <div className="bg-muted/50 rounded-2xl p-4 hidden md:block">
          <div className="flex items-center gap-2 mb-2">
            <div className={cn("w-2 h-2 rounded-full animate-pulse", statusColor)} />
            <span className="text-[10px] font-medium uppercase tracking-wider text-muted-foreground">System Status</span>
          </div>
          <p className="text-[11px] text-muted-foreground leading-relaxed">
            {statusText}
          </p>
        </div>
      </div>
    </aside>
  );
}
