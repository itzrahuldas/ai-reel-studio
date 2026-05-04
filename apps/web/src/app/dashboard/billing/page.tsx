"use client";

import { useEffect } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import { useQuery } from "@tanstack/react-query";
import { apiClient, UsageSummary, PlanDefinition } from "@/lib/api-client";

// ── Usage Meter ────────────────────────────────────────────────────────────────

function UsageMeter({
  label,
  used,
  limit,
  icon,
}: {
  label: string;
  used: number;
  limit: number;
  icon: string;
}) {
  const pct = limit > 0 ? Math.min((used / limit) * 100, 100) : 0;
  const isWarning = pct >= 80 && pct < 100;
  const isExceeded = pct >= 100;

  const barColor = isExceeded
    ? "bg-red-500"
    : isWarning
    ? "bg-amber-500"
    : "bg-violet-500";

  return (
    <div className="space-y-2">
      <div className="flex items-center justify-between text-sm">
        <span className="flex items-center gap-2 text-gray-300">
          <span>{icon}</span>
          {label}
        </span>
        <span
          className={`font-mono font-semibold ${
            isExceeded
              ? "text-red-400"
              : isWarning
              ? "text-amber-400"
              : "text-gray-300"
          }`}
        >
          {used} / {limit}
        </span>
      </div>
      <div className="h-2 rounded-full bg-gray-800 overflow-hidden">
        <div
          className={`h-full rounded-full transition-all duration-500 ${barColor}`}
          style={{ width: `${pct}%` }}
        />
      </div>
    </div>
  );
}

// ── Plan Badge ─────────────────────────────────────────────────────────────────

const PLAN_COLORS: Record<string, string> = {
  FREE: "bg-gray-700/60 text-gray-300 border border-gray-600",
  CREATOR: "bg-violet-900/60 text-violet-300 border border-violet-700",
  PRO: "bg-amber-900/60 text-amber-300 border border-amber-700",
};

const PLAN_ICONS: Record<string, string> = {
  FREE: "🆓",
  CREATOR: "✨",
  PRO: "⚡",
};

function PlanBadge({ planKey }: { planKey: string }) {
  return (
    <span
      className={`inline-flex items-center gap-1.5 px-3 py-1 rounded-full text-sm font-semibold ${
        PLAN_COLORS[planKey] ?? PLAN_COLORS.FREE
      }`}
    >
      {PLAN_ICONS[planKey] ?? "🆓"} {planKey}
    </span>
  );
}

// ── Plan Card ──────────────────────────────────────────────────────────────────

function PlanCard({
  plan,
  isCurrent,
}: {
  plan: PlanDefinition;
  isCurrent: boolean;
}) {
  const features = [
    `${plan.ai_generations_per_month} AI generations / mo`,
    `${plan.renders_per_month} renders / mo`,
    `${plan.publishes_per_month} publishes / mo`,
    `${plan.scheduled_publishes_limit} active schedules`,
    plan.watermark_enabled ? "Watermark on video" : "No watermark",
  ];

  return (
    <div
      className={`relative rounded-2xl p-6 border transition-all ${
        isCurrent
          ? "border-violet-500 bg-violet-950/30 shadow-lg shadow-violet-500/10"
          : "border-gray-800 bg-gray-900/50 hover:border-gray-700"
      }`}
    >
      {isCurrent && (
        <div className="absolute -top-3 left-1/2 -translate-x-1/2">
          <span className="bg-violet-600 text-white text-xs font-bold px-3 py-1 rounded-full">
            CURRENT PLAN
          </span>
        </div>
      )}

      <div className="mb-4">
        <PlanBadge planKey={plan.key} />
        <p className="text-xs text-gray-500 mt-2">{plan.name} Plan</p>
      </div>

      <ul className="space-y-2 mb-6">
        {features.map((f, i) => (
          <li key={i} className="flex items-center gap-2 text-sm text-gray-300">
            <span className="text-violet-400 text-xs">✓</span>
            {f}
          </li>
        ))}
      </ul>

      {!isCurrent && (
        <div className="text-center">
          <p className="text-xs text-gray-500">
            Contact us to upgrade — Stripe billing coming soon.
          </p>
        </div>
      )}
    </div>
  );
}

// ── Main Page ──────────────────────────────────────────────────────────────────

export default function BillingPage() {
  const router = useRouter();

  useEffect(() => {
    if (!localStorage.getItem("access_token")) {
      router.replace("/login");
    }
  }, [router]);

  const { data: usage, isLoading: usageLoading, isError: usageError } = useQuery({
    queryKey: ["usage-summary"],
    queryFn: () => apiClient.getUsageSummary(),
    staleTime: 30_000,
  });

  const { data: plans, isLoading: plansLoading } = useQuery({
    queryKey: ["billing-plans"],
    queryFn: () => apiClient.getPlans(),
    staleTime: 5 * 60_000,
  });

  const isLoading = usageLoading || plansLoading;
  const currentPlanKey = usage?.plan.key ?? "FREE";

  // Format period range
  const periodRange = usage
    ? `${new Date(usage.period_start).toLocaleDateString("en-IN", {
        day: "numeric",
        month: "short",
      })} – ${new Date(usage.period_end).toLocaleDateString("en-IN", {
        day: "numeric",
        month: "short",
        year: "numeric",
      })}`
    : null;

  return (
    <div className="p-8 max-w-4xl mx-auto">
      {/* Header */}
      <div className="mb-8">
        <h1 className="text-2xl font-bold text-white">Billing &amp; Usage</h1>
        <p className="text-gray-400 mt-1">
          Monitor your monthly usage and manage your plan.
        </p>
      </div>

      {usageError && (
        <div className="p-4 rounded-xl bg-red-950/50 border border-red-800/50 text-red-300 text-sm mb-6">
          Failed to load usage data. Please refresh the page.
        </div>
      )}

      {/* Current Usage Card */}
      <section className="mb-8">
        <div className="card">
          <div className="flex items-center justify-between mb-6">
            <div>
              <h2 className="text-lg font-semibold text-white">
                Current Period Usage
              </h2>
              {periodRange && (
                <p className="text-sm text-gray-500 mt-0.5">{periodRange}</p>
              )}
            </div>
            {usage && <PlanBadge planKey={usage.plan.key} />}
          </div>

          {isLoading ? (
            <div className="space-y-4 animate-pulse">
              {[1, 2, 3, 4].map((i) => (
                <div key={i} className="space-y-2">
                  <div className="h-4 bg-gray-800 rounded w-32" />
                  <div className="h-2 bg-gray-800 rounded" />
                </div>
              ))}
            </div>
          ) : usage ? (
            <div className="space-y-5">
              <UsageMeter
                label="AI Generations"
                used={usage.ai_generations_used}
                limit={usage.ai_generations_limit}
                icon="🤖"
              />
              <UsageMeter
                label="Renders"
                used={usage.renders_used}
                limit={usage.renders_limit}
                icon="🎬"
              />
              <UsageMeter
                label="Publishes"
                used={usage.publishes_used}
                limit={usage.publishes_limit}
                icon="📤"
              />
              <UsageMeter
                label="Active Scheduled Publishes"
                used={usage.active_scheduled_publishes}
                limit={usage.scheduled_publishes_limit}
                icon="⏰"
              />

              {usage.plan.watermark_enabled && (
                <div className="flex items-center gap-2 pt-2 border-t border-gray-800 text-sm text-amber-400">
                  <span>💧</span>
                  <span>
                    Watermark is enabled on your plan.{" "}
                    <span className="text-gray-500">
                      Upgrade to Creator or Pro to remove it.
                    </span>
                  </span>
                </div>
              )}
            </div>
          ) : null}
        </div>
      </section>

      {/* Plan Comparison */}
      <section>
        <h2 className="text-lg font-semibold text-white mb-4">Available Plans</h2>

        {plansLoading ? (
          <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
            {[1, 2, 3].map((i) => (
              <div
                key={i}
                className="h-64 bg-gray-900 rounded-2xl animate-pulse border border-gray-800"
              />
            ))}
          </div>
        ) : plans ? (
          <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
            {plans.map((plan) => (
              <PlanCard
                key={plan.key}
                plan={plan}
                isCurrent={plan.key === currentPlanKey}
              />
            ))}
          </div>
        ) : null}

        <p className="text-xs text-gray-600 text-center mt-6">
          Stripe billing integration coming soon. Contact{" "}
          <a
            href="mailto:billing@ai-reel-studio.com"
            className="text-violet-500 hover:underline"
          >
            billing@ai-reel-studio.com
          </a>{" "}
          to upgrade manually.
        </p>
      </section>
    </div>
  );
}
