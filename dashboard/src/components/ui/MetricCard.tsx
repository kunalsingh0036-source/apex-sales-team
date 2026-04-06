interface MetricCardProps {
  label: string;
  value: string | number;
  subtext?: string;
  accent?: string;
}

export default function MetricCard({
  label,
  value,
  subtext,
  accent = "text-crimson-dark",
}: MetricCardProps) {
  return (
    <div className="bg-white rounded-xl p-6 border border-rich-creme shadow-sm min-w-0 overflow-hidden">
      <p className="font-label text-[11px] tracking-[0.14em] text-mid-warm uppercase mb-2">
        {label}
      </p>
      <p className={`font-display text-3xl font-bold truncate ${accent}`}>
        {value}
      </p>
      {subtext && (
        <p className="text-sm text-mid-warm mt-1">{subtext}</p>
      )}
    </div>
  );
}
