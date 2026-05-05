"use client";

import Link from "next/link";
import { useEffect } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { ArrowRight, CheckCircle2 } from "lucide-react";
import { apiClient } from "@/lib/api-client";

export default function BillingSuccessPage() {
  const queryClient = useQueryClient();
  const { data: usage } = useQuery({
    queryKey: ["usage-summary"],
    queryFn: () => apiClient.getUsageSummary(),
    staleTime: 10_000,
  });

  useEffect(() => {
    queryClient.invalidateQueries({ queryKey: ["usage-summary"] });
    queryClient.invalidateQueries({ queryKey: ["billing-plans"] });
  }, [queryClient]);

  return (
    <div className="mx-auto max-w-xl p-8">
      <div className="card text-center">
        <CheckCircle2 className="mx-auto mb-4 h-12 w-12 text-emerald-300" />
        <h1 className="text-2xl font-bold text-white">Billing Updated</h1>
        <p className="mt-2 text-sm text-gray-400">
          Current plan: {usage?.current_plan ?? usage?.plan.key ?? "Refreshing"}
        </p>
        <div className="mt-6 flex justify-center">
          <Link href="/dashboard/billing" className="btn-primary">
            Back to Billing
            <ArrowRight className="h-4 w-4" />
          </Link>
        </div>
      </div>
    </div>
  );
}
