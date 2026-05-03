import Link from "next/link";
import { ReactNode } from "react";

export default function DashboardLayout({ children }: { children: ReactNode }) {
  return (
    <div className="min-h-screen flex bg-gray-950">
      <aside className="w-64 bg-gray-900 border-r border-gray-800 flex flex-col p-4">
        <div className="flex items-center gap-3 mb-8 px-2">
          <span className="text-2xl">??</span>
          <span className="text-lg font-bold text-white">Reel Studio</span>
        </div>
        <nav className="flex flex-col gap-1">
          {[
            { href: "/dashboard", label: "Dashboard", icon: "?" },
            { href: "/dashboard/create", label: "Create Reel", icon: "+" },
            { href: "/dashboard/integrations", label: "Integrations", icon: "?" },
            { href: "/dashboard/settings", label: "Settings", icon: "?" },
          ].map((item) => (
            <Link key={item.href} href={item.href}
              className="flex items-center gap-3 px-3 py-2.5 rounded-lg text-gray-400 hover:text-white hover:bg-gray-800 transition-colors text-sm">
              <span>{item.icon}</span><span>{item.label}</span>
            </Link>
          ))}
        </nav>
      </aside>
      <main className="flex-1 overflow-auto">{children}</main>
    </div>
  );
}
