import { getMe } from "@/lib/api";
import { redirect } from "next/navigation";

const API_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

function GitHubIcon({ className }: { className?: string }) {
  return (
    <svg className={className} viewBox="0 0 24 24" fill="currentColor">
      <path d="M12 0C5.37 0 0 5.37 0 12c0 5.31 3.435 9.795 8.205 11.385.6.105.825-.255.825-.57 0-.285-.015-1.23-.015-2.235-3.015.555-3.795-.735-4.035-1.41-.135-.345-.72-1.41-1.23-1.695-.42-.225-1.02-.78-.015-.795.945-.015 1.62.87 1.845 1.23 1.08 1.815 2.805 1.305 3.495.99.105-.78.42-1.305.765-1.605-2.67-.3-5.46-1.335-5.46-5.925 0-1.305.465-2.385 1.23-3.225-.12-.3-.54-1.53.12-3.18 0 0 1.005-.315 3.3 1.23.96-.27 1.98-.405 3-.405s2.04.135 3 .405c2.295-1.56 3.3-1.23 3.3-1.23.66 1.65.24 2.88.12 3.18.765.84 1.23 1.905 1.23 3.225 0 4.605-2.805 5.625-5.475 5.925.435.375.81 1.095.81 2.22 0 1.605-.015 2.895-.015 3.3 0 .315.225.69.825.57A12.02 12.02 0 0024 12c0-6.63-5.37-12-12-12z" />
    </svg>
  );
}

function CatLogo() {
  return (
    <div className="relative inline-flex items-center justify-center w-20 h-20 rounded-2xl bg-gradient-to-br from-accent to-purple-500 glow-accent">
      <span className="text-4xl leading-none select-none">🐱</span>
    </div>
  );
}

export default async function HomePage() {
  const user = await getMe();

  if (user) {
    redirect("/dashboard");
  }

  return (
    <main className="flex min-h-screen flex-col items-center justify-center p-8">
      <div className="max-w-md w-full space-y-10">
        {/* Hero */}
        <div className="text-center space-y-5">
          <CatLogo />
          <div>
            <h1 className="text-4xl font-bold tracking-tight text-white">
              Cato<span className="text-gradient">Code</span>
            </h1>
            <p className="text-gray-400 mt-2 text-lg leading-relaxed">
              Autonomous AI-powered GitHub repository maintenance
            </p>
          </div>
        </div>

        {/* Features */}
        <div className="glass rounded-xl p-5 space-y-3">
          {[
            { icon: "🔍", text: "Automatically reviews every PR with detailed feedback" },
            { icon: "💡", text: "Analyzes issues and proposes solutions before fixing" },
            { icon: "🛡️", text: "Proactive codebase patrol for bugs and security issues" },
            { icon: "📋", text: "Proof-of-Work evidence for every change" },
          ].map((f) => (
            <div key={f.text} className="flex items-start gap-3 text-sm text-gray-300">
              <span className="text-base mt-0.5 flex-shrink-0">{f.icon}</span>
              <span>{f.text}</span>
            </div>
          ))}
        </div>

        {/* Login */}
        <div className="space-y-4">
          <a
            href={`${API_URL}/auth/github`}
            className="flex items-center justify-center gap-3 w-full bg-white text-gray-900 font-semibold py-3.5 px-6 rounded-xl hover:bg-gray-100 transition-all duration-200 hover:scale-[1.02] active:scale-[0.98]"
          >
            <GitHubIcon className="w-5 h-5" />
            Sign in with GitHub
          </a>
          <p className="text-center text-xs text-gray-600">
            By signing in you agree to our Terms of Service.
          </p>
        </div>
      </div>
    </main>
  );
}
