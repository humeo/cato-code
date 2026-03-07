import type { Repo } from "@/lib/types";

interface RepoListProps {
  repos: Repo[];
}

export function RepoList({ repos }: RepoListProps) {
  if (!repos.length) {
    return (
      <div className="flex flex-col items-center justify-center py-8 text-gray-600">
        <span className="text-2xl mb-2">📭</span>
        <p className="text-sm">No repositories yet.</p>
      </div>
    );
  }

  return (
    <div className="space-y-1">
      {repos.map((r) => {
        const shortName = r.repo_url.replace("https://github.com/", "");
        return (
          <div
            key={r.id}
            className="flex items-center gap-3 py-2.5 px-3 -mx-3 rounded-lg hover:bg-white/[0.02] transition-colors text-sm group"
          >
            <span
              className={`w-2 h-2 rounded-full flex-shrink-0 ${
                r.watch ? "bg-emerald-400" : "bg-gray-600"
              }`}
            />
            <a
              href={r.repo_url}
              target="_blank"
              rel="noreferrer"
              className="text-gray-300 hover:text-white truncate transition-colors font-medium"
            >
              {shortName}
            </a>
            <span
              className={`ml-auto text-xs px-2 py-0.5 rounded-full flex-shrink-0 ${
                r.watch
                  ? "text-emerald-400 bg-emerald-400/10"
                  : "text-gray-500 bg-gray-500/10"
              }`}
            >
              {r.watch ? "watching" : "paused"}
            </span>
          </div>
        );
      })}
    </div>
  );
}
