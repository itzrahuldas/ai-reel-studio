import Link from "next/link";

export default function LandingPage() {
  return (
    <main className="min-h-screen bg-gray-950">
      {/* Hero */}
      <section className="relative overflow-hidden px-6 py-24 text-center">
        <div className="absolute inset-0 bg-gradient-to-br from-violet-900/20 via-gray-950 to-indigo-900/20 pointer-events-none" />
        <div className="relative max-w-4xl mx-auto">
          <div className="inline-flex items-center gap-2 px-4 py-1.5 rounded-full bg-violet-500/10 border border-violet-500/20 text-violet-400 text-sm font-medium mb-8">
            <span className="w-2 h-2 rounded-full bg-violet-400 animate-pulse" />
            AI-Powered Reel Generation
          </div>
          <h1 className="text-5xl md:text-7xl font-bold mb-6 bg-gradient-to-r from-white via-gray-200 to-gray-400 bg-clip-text text-transparent leading-tight">
            Turn Any Idea Into<br />an Instagram Reel
          </h1>
          <p className="text-xl text-gray-400 mb-10 max-w-2xl mx-auto leading-relaxed">
            Give us your business idea + one image. We generate the script,
            storyboard, voiceover, subtitles, and a vertical 9:16 video —
            ready to publish to Instagram.
          </p>
          <div className="flex flex-col sm:flex-row gap-4 justify-center">
            <Link href="/dashboard/create" className="btn-primary text-lg px-8 py-3">
              Create Your Reel ?
            </Link>
            <Link href="/login" className="btn-secondary text-lg px-8 py-3">
              Sign In
            </Link>
          </div>
        </div>
      </section>

      {/* Features */}
      <section className="max-w-6xl mx-auto px-6 py-20 grid md:grid-cols-3 gap-8">
        {[
          { icon: "??", title: "AI Script & Storyboard", desc: "LLM generates hook, scene-by-scene script, and visual directions tailored to your brand." },
          { icon: "???", title: "Voiceover & Subtitles", desc: "AI text-to-speech produces natural voiceovers with timed subtitle lines automatically." },
          { icon: "??", title: "Publish to Instagram", desc: "Approve your reel and publish directly to Instagram Reels via the official Meta Graph API." },
        ].map((f) => (
          <div key={f.title} className="card hover:border-violet-700/50 transition-colors">
            <div className="text-4xl mb-4">{f.icon}</div>
            <h3 className="text-xl font-semibold mb-2 text-white">{f.title}</h3>
            <p className="text-gray-400 leading-relaxed">{f.desc}</p>
          </div>
        ))}
      </section>

      {/* Footer */}
      <footer className="text-center py-10 text-gray-600 text-sm border-t border-gray-900">
        © {new Date().getFullYear()} AI Reel Studio. Built with Next.js 15 + FastAPI.
      </footer>
    </main>
  );
}
