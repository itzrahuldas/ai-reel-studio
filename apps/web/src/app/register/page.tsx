"use client";
import { useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { apiClient } from "@/lib/api-client";
import type { ApiError } from "@/lib/api-client";

export default function RegisterPage() {
  const router = useRouter();
  const [email, setEmail] = useState("");
  const [fullName, setFullName] = useState("");
  const [password, setPassword] = useState("");
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const onSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setIsLoading(true);
    setError(null);
    try {
      const data = await apiClient.register(email, password, fullName);
      localStorage.setItem("access_token", data.access_token);
      router.push("/dashboard");
    } catch (err: unknown) {
      setError((err as ApiError)?.message ?? "Failed to register.");
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <div className="min-h-screen flex items-center justify-center px-4 bg-gray-950">
      <div className="w-full max-w-md">
        <div className="text-center mb-8">
          <h1 className="text-3xl font-bold text-white mb-2">Create Account</h1>
          <p className="text-gray-400">Get started with AI Reel Studio</p>
        </div>
        <div className="card">
          {error && (
            <div className="mb-4 p-3 bg-red-900/30 border border-red-800 rounded text-red-400 text-sm">
              {error}
            </div>
          )}
          <form onSubmit={onSubmit} className="space-y-5">
            <div>
              <label htmlFor="fullName" className="block text-sm font-medium text-gray-300 mb-1">Full Name</label>
              <input id="fullName" type="text" value={fullName} onChange={e => setFullName(e.target.value)} className="input" placeholder="Jane Doe" required />
            </div>
            <div>
              <label htmlFor="email" className="block text-sm font-medium text-gray-300 mb-1">Email</label>
              <input id="email" type="email" value={email} onChange={e => setEmail(e.target.value)} className="input" placeholder="you@example.com" required />
            </div>
            <div>
              <label htmlFor="password" className="block text-sm font-medium text-gray-300 mb-1">Password</label>
              <input id="password" type="password" value={password} onChange={e => setPassword(e.target.value)} className="input" placeholder="Min 8 characters" minLength={8} required />
            </div>
            <button id="register-submit" type="submit" disabled={isLoading} className="btn-primary w-full justify-center py-3">
              {isLoading ? "Creating account..." : "Sign Up"}
            </button>
          </form>
          <p className="text-center text-sm text-gray-400 mt-6">
            Already have an account? <Link href="/login" className="text-violet-400 hover:text-violet-300">Sign in</Link>
          </p>
        </div>
      </div>
    </div>
  );
}
