interface StatCardProps {
  label: string;
  value: string | number;
  icon?: string;
  accent?: string;
}

export function StatCard({ label, value, icon, accent }: StatCardProps) {
  return (
    <div className="glass rounded-xl p-4 group hover:border-border-default transition-colors duration-200">
      <div className="flex items-start justify-between mb-2">
        <p className="text-gray-500 text-xs font-medium uppercase tracking-wider">{label}</p>
        {icon && <span className="text-base opacity-60 group-hover:opacity-100 transition-opacity">{icon}</span>}
      </div>
      <p className={`text-2xl font-bold tracking-tight ${accent ?? "text-white"}`}>{value}</p>
    </div>
  );
}
