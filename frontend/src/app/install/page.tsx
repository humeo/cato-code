import { getInstallUrl } from "@/lib/api";

export default async function InstallPage() {
  const installUrl = await getInstallUrl();

  return (
    <main className="flex min-h-screen flex-col items-center justify-center p-8">
      <div className="max-w-lg w-full space-y-8">
        <div className="text-center space-y-4">
          <div className="inline-flex items-center justify-center w-16 h-16 rounded-2xl bg-gradient-to-br from-emerald-500 to-teal-600 glow-green">
            <span className="text-3xl">⚙️</span>
          </div>
          <h1 className="text-3xl font-bold text-white tracking-tight">Install GitHub App</h1>
          <p className="text-gray-400 leading-relaxed">
            Install CatoCode on your GitHub account or organization to automatically
            watch repositories and start reviewing PRs and triaging issues.
          </p>
        </div>

        <div className="glass rounded-xl p-5 space-y-3">
          <p className="text-gray-300 text-sm font-semibold mb-3">What happens after installation:</p>
          {[
            { icon: "📂", text: "Selected repositories are automatically watched" },
            { icon: "🔍", text: "New pull requests trigger code reviews" },
            { icon: "💡", text: "New issues trigger analysis and solution proposals" },
            { icon: "🛡️", text: "Scheduled patrols scan for bugs and security issues" },
          ].map((item) => (
            <div key={item.text} className="flex items-start gap-3 text-sm text-gray-400">
              <span className="text-base flex-shrink-0">{item.icon}</span>
              <span>{item.text}</span>
            </div>
          ))}
        </div>

        <div className="space-y-4">
          {installUrl ? (
            <>
              <a
                href={installUrl}
                target="_blank"
                rel="noreferrer"
                className="flex items-center justify-center gap-2 w-full bg-emerald-600 hover:bg-emerald-500 text-white font-semibold py-3.5 px-6 rounded-xl transition-all duration-200 hover:scale-[1.02] active:scale-[0.98] glow-green"
              >
                Install on GitHub
                <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                  <path strokeLinecap="round" strokeLinejoin="round" d="M10 6H6a2 2 0 00-2 2v10a2 2 0 002 2h10a2 2 0 002-2v-4M14 4h6m0 0v6m0-6L10 14" />
                </svg>
              </a>
              <p className="text-center text-xs text-gray-600">
                Opens in a new tab. Come back here after installation.
              </p>
            </>
          ) : (
            <div className="bg-red-950/50 border border-red-800/50 rounded-xl p-4 text-center">
              <p className="text-red-400 text-sm">Failed to generate install URL. Check backend config.</p>
            </div>
          )}

          <a
            href="/dashboard"
            className="flex items-center justify-center gap-1 text-sm text-gray-500 hover:text-gray-300 transition-colors"
          >
            <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
              <path strokeLinecap="round" strokeLinejoin="round" d="M11 17l-5-5m0 0l5-5m-5 5h12" />
            </svg>
            Back to dashboard
          </a>
        </div>
      </div>
    </main>
  );
}
