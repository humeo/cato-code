export default function DashboardLayout({ children }: { children: React.ReactNode }) {
  return (
    <div className="max-w-6xl mx-auto p-4 sm:p-6 lg:p-8">
      <header className="glass rounded-xl px-5 py-4 mb-8 flex items-center gap-4">
        <img src="/logo.svg" alt="CatoCode" className="w-10 h-10 rounded-lg flex-shrink-0" />
        <div className="min-w-0">
          <h1 className="text-lg font-bold text-white tracking-tight">
            Cato<span className="text-accent-light">Code</span>
          </h1>
          <p className="text-gray-500 text-xs">Autonomous Code Maintenance</p>
        </div>
        <div className="ml-auto flex items-center gap-3">
          <div className="flex items-center gap-2">
            <div className="w-2 h-2 rounded-full bg-emerald-400 animate-pulse" />
            <span className="text-xs text-gray-500 hidden sm:inline">Online</span>
          </div>
        </div>
      </header>
      {children}
    </div>
  );
}
