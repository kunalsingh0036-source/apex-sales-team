"use client";

export default function Header({ title }: { title: string }) {
  return (
    <header className="flex flex-col md:flex-row md:items-center justify-between mb-6 md:mb-10 pb-4 md:pb-6 border-b border-rich-creme/60">
      <h2 className="font-display text-xl md:text-3xl font-bold text-crimson-dark">
        {title}
      </h2>
      <div className="flex items-center gap-4">
        <div className="font-label text-xs md:text-sm tracking-wider text-mid-warm uppercase">
          {new Date().toLocaleDateString("en-IN", {
            weekday: "long",
            year: "numeric",
            month: "long",
            day: "numeric",
          })}
        </div>
      </div>
    </header>
  );
}
