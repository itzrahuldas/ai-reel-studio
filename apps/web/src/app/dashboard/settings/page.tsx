"use client";
import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { apiClient, User } from "@/lib/api-client";

export default function SettingsPage() {
  const router = useRouter();
  const [user, setUser] = useState<User | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    apiClient.me()
      .then(setUser)
      .catch((err) => {
        console.error("Not authenticated:", err);
        router.push("/login");
      })
      .finally(() => setLoading(false));
  }, [router]);

  const handleLogout = async () => {
    try {
      await apiClient.logout();
    } catch (e) {
      console.error(e);
    } finally {
      router.push("/login");
    }
  };

  if (loading) {
    return <div className="p-8 text-white">Loading profile...</div>;
  }

  return (
    <div className="p-8 max-w-2xl mx-auto">
      <h1 className="text-2xl font-bold text-white mb-6">Settings</h1>
      
      <div className="card mb-8">
        <h2 className="text-lg font-semibold text-white mb-4">Profile Information</h2>
        <div className="space-y-4 text-gray-300">
          <div>
            <span className="block text-sm text-gray-500">Name</span>
            <span className="font-medium">{user?.full_name || "N/A"}</span>
          </div>
          <div>
            <span className="block text-sm text-gray-500">Email</span>
            <span className="font-medium">{user?.email}</span>
          </div>
          <div>
            <span className="block text-sm text-gray-500">User ID</span>
            <span className="font-mono text-xs">{user?.id}</span>
          </div>
        </div>
      </div>

      <div className="card mb-8">
        <h2 className="text-lg font-semibold text-white mb-4">Authentication</h2>
        <p className="text-sm text-gray-400 mb-4">You are currently logged in securely.</p>
        <button onClick={handleLogout} className="btn-secondary text-red-400 border-red-900 hover:bg-red-950">
          Log Out
        </button>
      </div>
    </div>
  );
}
