import { getMe } from "@/lib/api";
import { redirect } from "next/navigation";
import { UserNav } from "@/components/UserNav";

export default async function DashboardLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  const user = await getMe();

  if (!user) {
    redirect("/");
  }

  return (
    <div className="max-w-6xl mx-auto p-4 sm:p-6 lg:p-8">
      {/* Header */}
      <header className="glass rounded-xl px-5 py-4 mb-8 flex items-center gap-4">
        <div className="flex items-center justify-center w-10 h-10 rounded-lg bg-gradient-to-br from-accent to-purple-500 flex-shrink-0">
          <span className="text-xl leading-none">🐱</span>
        </div>
        <div className="min-w-0">
          <h1 className="text-lg font-bold text-white tracking-tight">
            Cato<span className="text-accent-light">Code</span>
          </h1>
          <p className="text-gray-500 text-xs">Autonomous Code Maintenance</p>
        </div>
        <div className="ml-auto flex items-center gap-4">
          <div className="flex items-center gap-2">
            <div className="w-2 h-2 rounded-full bg-emerald-400 animate-pulse" />
            <span className="text-xs text-gray-500 hidden sm:inline">Online</span>
          </div>
          <div className="w-px h-6 bg-border-subtle" />
          <UserNav user={user} />
        </div>
      </header>

      {children}
    </div>
  );
}
