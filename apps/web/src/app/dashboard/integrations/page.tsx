"use client";

import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { apiClient } from "@/lib/api-client";
import { useSearchParams, useRouter } from "next/navigation";
import { useEffect, useState } from "react";

export default function IntegrationsPage() {
  const queryClient = useQueryClient();
  const searchParams = useSearchParams();
  const router = useRouter();
  
  const [isDevelopment, setIsDevelopment] = useState(false);

  useEffect(() => {
    if (process.env.NODE_ENV === "development") {
      setIsDevelopment(true);
    }
  }, []);

  useEffect(() => {
    const connected = searchParams.get("connected");
    const error = searchParams.get("error");
    if (connected === "instagram") {
      alert("Instagram account connected successfully!");
      router.replace("/dashboard/integrations");
    } else if (error === "instagram_oauth_failed") {
      alert("Failed to connect Instagram account.");
      router.replace("/dashboard/integrations");
    }
  }, [searchParams, router]);

  const { data, isLoading, error: queryError } = useQuery({
    queryKey: ["instagram-status"],
    queryFn: () => apiClient.getInstagramStatus(),
  });

  const connectMutation = useMutation({
    mutationFn: () => apiClient.startInstagramConnect(),
    onSuccess: (data) => {
      window.location.href = data.authorization_url;
    },
    onError: (err: any) => {
      alert(err.message || "Failed to start connection");
    },
  });

  const mockConnectMutation = useMutation({
    mutationFn: () => apiClient.mockInstagramConnect(),
    onSuccess: () => {
      alert("Mock account connected");
      queryClient.invalidateQueries({ queryKey: ["instagram-status"] });
    },
    onError: (err: any) => {
      alert(err.message || "Failed mock connection");
    },
  });

  const disconnectMutation = useMutation({
    mutationFn: (id: string) => apiClient.disconnectInstagramAccount(id),
    onSuccess: () => {
      alert("Account disconnected");
      queryClient.invalidateQueries({ queryKey: ["instagram-status"] });
    },
  });

  const reconnectMutation = useMutation({
    mutationFn: () => apiClient.reconnectInstagramAccount(),
    onSuccess: (data) => {
      window.location.href = data.authorization_url;
    },
  });

  return (
    <div className="p-8 max-w-2xl mx-auto space-y-6">
      <div>
        <h1 className="text-2xl font-bold text-white mb-2">Integrations</h1>
        <p className="text-gray-400">Connect your Instagram Business Account to publish Reels.</p>
      </div>

      {isLoading ? (
        <div className="card text-center text-gray-400 py-8">Loading status...</div>
      ) : queryError ? (
        <div className="card border-red-500/50 text-red-400">
          Failed to load integrations status.
        </div>
      ) : (
        <div className="space-y-4">
          <div className="card">
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-4">
                <div className="w-12 h-12 rounded-full bg-gradient-to-tr from-yellow-500 via-pink-500 to-purple-600 flex items-center justify-center text-white text-xl font-bold">
                  IG
                </div>
                <div>
                  <h3 className="font-semibold text-white">Instagram</h3>
                  <p className="text-sm text-gray-400">
                    {data?.connected ? "Connected" : "Not connected"}
                  </p>
                </div>
              </div>
              {!data?.connected && (
                <div className="flex gap-2">
                  {isDevelopment && (
                    <button
                      className="btn-secondary"
                      onClick={() => mockConnectMutation.mutate()}
                      disabled={mockConnectMutation.isPending}
                    >
                      {mockConnectMutation.isPending ? "Connecting..." : "Mock Connect"}
                    </button>
                  )}
                  <button
                    className="btn-primary"
                    onClick={() => connectMutation.mutate()}
                    disabled={connectMutation.isPending}
                  >
                    {connectMutation.isPending ? "Redirecting..." : "Connect"}
                  </button>
                </div>
              )}
            </div>

            {data?.connected && data.accounts && data.accounts.length > 0 && (
              <div className="mt-6 space-y-4">
                {data.accounts.map((acc) => (
                  <div key={acc.id} className="p-4 bg-gray-800 rounded-lg border border-gray-700 flex items-center justify-between">
                    <div>
                      <p className="text-white font-medium">@{acc.username}</p>
                      <p className="text-xs text-gray-400">
                        {acc.account_type} • Page: {acc.page_name || "Unknown"}
                      </p>
                      {acc.status === "reconnect_required" || acc.status === "error" ? (
                        <p className="text-xs text-red-400 mt-1">Connection error. Please reconnect.</p>
                      ) : null}
                    </div>
                    <div className="flex gap-2">
                      <button
                        className="btn-secondary text-sm px-3 py-1"
                        onClick={() => reconnectMutation.mutate()}
                      >
                        Reconnect
                      </button>
                      <button
                        className="btn-secondary text-red-400 border-red-500/30 hover:bg-red-500/10 text-sm px-3 py-1"
                        onClick={() => disconnectMutation.mutate(acc.id)}
                        disabled={disconnectMutation.isPending}
                      >
                        Disconnect
                      </button>
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>

          <div className="p-4 bg-yellow-900/20 border border-yellow-800/40 rounded-lg text-sm text-yellow-400">
            <strong>Note:</strong> You need an Instagram Business or Creator account linked to a Facebook Page.
            Personal accounts are not supported by the Meta Graph API.
          </div>
        </div>
      )}
    </div>
  );
}
