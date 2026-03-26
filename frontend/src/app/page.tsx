const API_BASE = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

export default function HomePage() {
  return (
    <main className="mx-auto flex min-h-screen max-w-6xl flex-col justify-center px-6 py-16">
      <div className="grid gap-10 lg:grid-cols-[1.15fr_0.85fr] lg:items-center">
        <section className="space-y-6">
          <div className="inline-flex items-center gap-2 rounded-full border border-cyan-400/20 bg-cyan-400/10 px-3 py-1 text-[11px] uppercase tracking-[0.28em] text-cyan-200">
            Personal Repo Maintenance Bot
          </div>
          <div className="space-y-4">
            <h1 className="max-w-3xl text-5xl font-semibold tracking-tight text-white md:text-6xl">
              Read the issue. Reply with evidence. Fix it. Run it. Prove it.
            </h1>
            <p className="max-w-2xl text-base leading-8 text-gray-400">
              CatoCode turns GitHub issues into observable maintenance sessions. It analyzes,
              responds, patches code, runs verification, and shows the full activity trail:
              model runs, steps, timing, cost, and proof-of-work.
            </p>
          </div>
          <div className="flex flex-wrap items-center gap-3">
            <a
              href={`${API_BASE}/auth/github`}
              className="rounded-full border border-cyan-400/25 bg-cyan-400/10 px-5 py-3 text-sm font-medium text-cyan-100 transition hover:bg-cyan-400/20"
            >
              Connect GitHub
            </a>
            <a
              href="/dashboard"
              className="rounded-full border border-white/10 bg-white/5 px-5 py-3 text-sm font-medium text-gray-200 transition hover:bg-white/10"
            >
              Open Dashboard
            </a>
          </div>
          <div className="grid gap-3 pt-3 md:grid-cols-3">
            {[
              {
                title: "Issue to Fix",
                body: "Issue opened -> analyze_issue -> /approve -> fix_issue on the same runtime session.",
              },
              {
                title: "Runtime Visibility",
                body: "See setup, repo memory review, session worktrees, logs, steps, retries, and costs.",
              },
              {
                title: "Three Entry Points",
                body: "Connect GitHub, install the App, then choose the repositories you want to watch from the dashboard.",
              },
            ].map((item) => (
              <div key={item.title} className="glass rounded-2xl border border-white/8 p-4">
                <p className="text-xs uppercase tracking-[0.22em] text-gray-500">{item.title}</p>
                <p className="mt-3 text-sm leading-6 text-gray-300">{item.body}</p>
              </div>
            ))}
          </div>
        </section>

        <section className="glass rounded-[28px] border border-white/8 p-6">
          <div className="rounded-[22px] border border-white/8 bg-black/20 p-5">
            <div className="flex items-center justify-between border-b border-white/8 pb-4">
              <div>
                <p className="text-xs uppercase tracking-[0.24em] text-gray-500">Onboarding</p>
                <h2 className="mt-2 text-2xl font-semibold text-white">Make a repository ready</h2>
              </div>
              <div className="rounded-full border border-blue-400/20 bg-blue-400/10 px-3 py-1 text-[11px] text-blue-200">
                setup -&gt; ready
              </div>
            </div>

            <div className="mt-5 space-y-3">
              {[
                "Install the GitHub App or connect an existing installation.",
                "Choose a visible repository in the dashboard and click Watch.",
                "Worker container clones the repo, initializes CLAUDE.md, runs `cg index`, and health checks.",
                "The dashboard shows each step, then the repo becomes ready for analyze/fix sessions.",
              ].map((line, index) => (
                <div key={line} className="flex gap-3 rounded-2xl border border-white/6 bg-white/[0.03] px-4 py-3">
                  <div className="flex h-7 w-7 items-center justify-center rounded-full bg-white/8 text-xs text-gray-200">
                    0{index + 1}
                  </div>
                  <p className="text-sm leading-6 text-gray-300">{line}</p>
                </div>
              ))}
            </div>
          </div>
        </section>
      </div>
    </main>
  );
}
