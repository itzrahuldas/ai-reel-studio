"use client";
export default function IntegrationsPage() {
  return (
    <div className="p-8 max-w-2xl mx-auto">
      <h1 className="text-2xl font-bold text-white mb-2">Integrations</h1>
      <p className="text-gray-400 mb-8">Connect your Instagram Business Account to publish Reels.</p>
      <div className="card flex items-center justify-between">
        <div className="flex items-center gap-4">
          <span className="text-3xl">??</span>
          <div>
            <h3 className="font-semibold text-white">Instagram</h3>
            <p className="text-sm text-gray-400">Not connected</p>
          </div>
        </div>
        <button id="connect-instagram" className="btn-primary"
          onClick={() => alert("TODO: call apiClient.connectInstagram()")}>
          Connect
        </button>
      </div>
      <div className="mt-6 p-4 bg-yellow-900/20 border border-yellow-800/40 rounded-lg text-sm text-yellow-400">
        <strong>Note:</strong> You need an Instagram Business or Creator account linked to a Facebook Page.
        Personal accounts are not supported by the Meta Graph API.
      </div>
    </div>
  );
}
