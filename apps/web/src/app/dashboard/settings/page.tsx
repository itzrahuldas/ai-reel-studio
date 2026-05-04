"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import { useQuery } from "@tanstack/react-query";
import { apiClient, User, UsageSummary } from "@/lib/api-client";

// ── Sub-components ────────────────────────────────────────────────────────────

function SectionHeader({ icon, title, subtitle }: { icon: string; title: string; subtitle?: string }) {
  return (
    <div className="flex items-center gap-3 mb-5">
      <div className="w-9 h-9 rounded-lg bg-violet-950/60 border border-violet-800/40 flex items-center justify-center text-lg flex-shrink-0">
        {icon}
      </div>
      <div>
        <h2 className="text-base font-semibold text-white leading-tight">{title}</h2>
        {subtitle && <p className="text-xs text-gray-500 mt-0.5">{subtitle}</p>}
      </div>
    </div>
  );
}

function InfoRow({ label, value, mono = false }: { label: string; value: string | undefined; mono?: boolean }) {
  return (
    <div className="flex items-center justify-between py-3 border-b border-gray-800/60 last:border-0">
      <span className="text-sm text-gray-500">{label}</span>
      <span className={`text-sm font-medium text-gray-200 ${mono ? "font-mono text-xs text-gray-400" : ""}`}>
        {value ?? "—"}
      </span>
    </div>
  );
}

function MiniMeter({ label, used, limit }: { label: string; used: number; limit: number }) {
  const pct = limit > 0 ? Math.min((used / limit) * 100, 100) : 0;
  const isWarning = pct >= 80;

  return (
    <div className="flex items-center gap-3">
      <div className="flex-1 min-w-0">
        <div className="flex justify-between text-xs mb-1">
          <span className="text-gray-500 truncate">{label}</span>
          <span className={`font-mono flex-shrink-0 ml-2 ${isWarning ? "text-amber-400" : "text-gray-500"}`}>
            {used}/{limit}
          </span>
        </div>
        <div className="h-1.5 bg-gray-800 rounded-full overflow-hidden">
          <div
            className={`h-full rounded-full transition-all duration-500 ${isWarning ? "bg-amber-500" : "bg-violet-500"}`}
            style={{ width: `${pct}%` }}
          />
        </div>
      </div>
    </div>
  );
}

// ── Plan badge ────────────────────────────────────────────────────────────────

const PLAN_STYLES: Record<string, string> = {
  FREE:    "text-gray-300 bg-gray-800/80 border border-gray-700",
  CREATOR: "text-violet-300 bg-violet-900/40 border border-violet-700/60",
  PRO:     "text-amber-300 bg-amber-900/40 border border-amber-700/60",
};
const PLAN_ICONS: Record<string, string> = { FREE: "🆓", CREATOR: "✨", PRO: "⚡" };

function PlanChip({ planKey }: { planKey: string }) {
  return (
    <span className={`inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full text-xs font-semibold ${PLAN_STYLES[planKey] ?? PLAN_STYLES.FREE}`}>
      {PLAN_ICONS[planKey] ?? "🆓"} {planKey}
    </span>
  );
}

// ── Confirm dialog state ──────────────────────────────────────────────────────

function LogoutConfirm({ onConfirm, onCancel }: { onConfirm: () => void; onCancel: () => void }) {
  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/70 backdrop-blur-sm">
      <div className="bg-gray-900 border border-gray-800 rounded-2xl p-6 max-w-sm w-full mx-4 shadow-2xl">
        <div className="text-3xl mb-3 text-center">👋</div>
        <h3 className="text-white font-semibold text-center mb-1">Log out of Reel Studio?</h3>
        <p className="text-gray-400 text-sm text-center mb-6">You&apos;ll need to sign in again to access your reels.</p>
        <div className="flex gap-3">
          <button
            onClick={onCancel}
            className="btn-secondary flex-1 justify-center"
          >
            Cancel
          </button>
          <button
            onClick={onConfirm}
            className="flex-1 inline-flex items-center justify-center gap-2 px-4 py-2 rounded-lg font-medium bg-red-900/60 text-red-300 border border-red-800 hover:bg-red-900 transition-all duration-200"
          >
            Log Out
          </button>
        </div>
      </div>
    </div>
  );
}

// ── Page ──────────────────────────────────────────────────────────────────────

export default function SettingsPage() {
  const router = useRouter();
  const [user, setUser] = useState<User | null>(null);
  const [loading, setLoading] = useState(true);
  const [showLogoutConfirm, setShowLogoutConfirm] = useState(false);
  const [isLoggingOut, setIsLoggingOut] = useState(false);
  const [copied, setCopied] = useState(false);

  useEffect(() => {
    if (!localStorage.getItem("access_token")) {
      router.replace("/login");
      return;
    }
    apiClient
      .me()
      .then(setUser)
      .catch(() => router.replace("/login"))
      .finally(() => setLoading(false));
  }, [router]);

  // Billing usage (best-effort — won't break the page if it fails)
  const { data: usage } = useQuery<UsageSummary>({
    queryKey: ["usage-summary"],
    queryFn: () => apiClient.getUsageSummary(),
    enabled: !loading && !!user,
    staleTime: 60_000,
  });

  const handleLogout = async () => {
    setIsLoggingOut(true);
    try {
      await apiClient.logout();
    } catch {
      // Clear token regardless
      if (typeof window !== "undefined") localStorage.removeItem("access_token");
    } finally {
      router.replace("/login");
    }
  };

  const copyUserId = () => {
    if (user?.id) {
      navigator.clipboard.writeText(user.id);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    }
  };

  const memberSince = user?.created_at
    ? new Date(user.created_at).toLocaleDateString("en-IN", {
        day: "numeric",
        month: "long",
        year: "numeric",
      })
    : undefined;

  if (loading) {
    return (
      <div className="p-8 max-w-2xl mx-auto">
        <div className="h-8 w-32 bg-gray-800 rounded animate-pulse mb-8" />
        {[1, 2, 3].map((i) => (
          <div key={i} className="card mb-4 animate-pulse">
            <div className="h-5 w-40 bg-gray-800 rounded mb-4" />
            <div className="space-y-3">
              <div className="h-4 bg-gray-800 rounded" />
              <div className="h-4 bg-gray-800 rounded w-3/4" />
            </div>
          </div>
        ))}
      </div>
    );
  }

  return (
    <>
      {showLogoutConfirm && (
        <LogoutConfirm
          onConfirm={handleLogout}
          onCancel={() => setShowLogoutConfirm(false)}
        />
      )}

      <div className="p-8 max-w-2xl mx-auto">
        {/* Page header */}
        <div className="mb-8">
          <h1 className="text-2xl font-bold text-white">Settings</h1>
          <p className="text-gray-400 mt-1 text-sm">Manage your account and workspace preferences.</p>
        </div>

        {/* ── Profile ──────────────────────────────────────────────────── */}
        <div className="card mb-4">
          <SectionHeader icon="👤" title="Profile" subtitle="Your account details" />
          <div>
            <InfoRow label="Display Name" value={user?.full_name ?? undefined} />
            <InfoRow label="Email Address" value={user?.email} />
            <InfoRow label="Member Since" value={memberSince} />
            <div className="flex items-center justify-between py-3">
              <span className="text-sm text-gray-500">User ID</span>
              <button
                onClick={copyUserId}
                title="Copy to clipboard"
                className="flex items-center gap-2 group"
              >
                <span className="font-mono text-xs text-gray-500 group-hover:text-gray-300 transition-colors">
                  {user?.id?.slice(0, 8)}…
                </span>
                <span className="text-xs text-gray-600 group-hover:text-violet-400 transition-colors">
                  {copied ? "✓ Copied" : "Copy"}
                </span>
              </button>
            </div>
          </div>
        </div>

        {/* ── Plan & Usage snapshot ─────────────────────────────────────── */}
        <div className="card mb-4">
          <div className="flex items-start justify-between mb-5">
            <SectionHeader
              icon="💳"
              title="Plan & Usage"
              subtitle="Your current billing period"
            />
            {usage && (
              <PlanChip planKey={usage.plan.key} />
            )}
          </div>

          {usage ? (
            <div className="space-y-3 mb-5">
              <MiniMeter
                label="AI Generations"
                used={usage.ai_generations_used}
                limit={usage.ai_generations_limit}
              />
              <MiniMeter
                label="Renders"
                used={usage.renders_used}
                limit={usage.renders_limit}
              />
              <MiniMeter
                label="Publishes"
                used={usage.publishes_used}
                limit={usage.publishes_limit}
              />
            </div>
          ) : (
            <div className="space-y-3 mb-5 animate-pulse">
              {[1, 2, 3].map((i) => (
                <div key={i} className="h-6 bg-gray-800 rounded" />
              ))}
            </div>
          )}

          <Link
            href="/dashboard/billing"
            id="settings-view-billing-link"
            className="inline-flex items-center gap-2 text-sm text-violet-400 hover:text-violet-300 transition-colors font-medium"
          >
            View full usage &amp; plans →
          </Link>
        </div>

        {/* ── Security ─────────────────────────────────────────────────── */}
        <div className="card mb-4">
          <SectionHeader icon="🔐" title="Security" subtitle="Session and access management" />
          <div className="flex items-center justify-between">
            <div>
              <p className="text-sm text-gray-300 font-medium">Current Session</p>
              <p className="text-xs text-gray-500 mt-0.5">
                Authenticated via JWT · expires in ~60 min
              </p>
            </div>
            <span className="flex items-center gap-1.5 text-xs text-emerald-400 bg-emerald-950/50 border border-emerald-900/50 px-2.5 py-1 rounded-full">
              <span className="w-1.5 h-1.5 bg-emerald-400 rounded-full animate-pulse" />
              Active
            </span>
          </div>
        </div>

        {/* ── Danger zone ───────────────────────────────────────────────── */}
        <div className="rounded-xl border border-red-900/40 bg-red-950/10 p-6">
          <SectionHeader icon="⚠️" title="Danger Zone" subtitle="Irreversible actions" />
          <div className="flex items-center justify-between">
            <div>
              <p className="text-sm text-gray-300 font-medium">Log Out</p>
              <p className="text-xs text-gray-500 mt-0.5">
                End your session and return to the login screen.
              </p>
            </div>
            <button
              id="logout-btn"
              onClick={() => setShowLogoutConfirm(true)}
              disabled={isLoggingOut}
              className="inline-flex items-center gap-2 px-4 py-2 rounded-lg text-sm font-medium
                text-red-300 bg-red-950/60 border border-red-900/60
                hover:bg-red-900/60 hover:border-red-700 transition-all duration-200
                disabled:opacity-50 disabled:cursor-not-allowed"
            >
              {isLoggingOut ? "Logging out…" : "Log Out"}
            </button>
          </div>
        </div>

        {/* Footer */}
        <p className="text-center text-xs text-gray-700 mt-8">
          AI Reel Studio · v0.1.0 · &copy; {new Date().getFullYear()}
        </p>
      </div>
    </>
  );
}
