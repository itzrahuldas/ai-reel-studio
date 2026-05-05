import Link from "next/link";
import { ArrowLeft, CreditCard } from "lucide-react";

export default function BillingCancelPage() {
  return (
    <div className="mx-auto max-w-xl p-8">
      <div className="card text-center">
        <CreditCard className="mx-auto mb-4 h-12 w-12 text-gray-300" />
        <h1 className="text-2xl font-bold text-white">Checkout Cancelled</h1>
        <p className="mt-2 text-sm text-gray-400">
          No billing changes were made.
        </p>
        <div className="mt-6 flex justify-center">
          <Link href="/dashboard/billing" className="btn-secondary">
            <ArrowLeft className="h-4 w-4" />
            Back to Billing
          </Link>
        </div>
      </div>
    </div>
  );
}
