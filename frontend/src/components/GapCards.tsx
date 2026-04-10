import type { GapItem } from "@/lib/api";

const STYLE: Record<string, string> = {
  oversaturated: "border-rose-500/40 bg-rose-950/40",
  opportunity: "border-emerald-500/40 bg-emerald-950/40",
  stable_hot: "border-sky-500/40 bg-sky-950/40",
  low_priority: "border-slate-600 bg-slate-900/60",
};

export function GapCards({ items }: { items: GapItem[] }) {
  const groups: Record<string, GapItem[]> = {};
  for (const g of items) {
    groups[g.gap_type] = groups[g.gap_type] ?? [];
    groups[g.gap_type].push(g);
  }
  const order = ["oversaturated", "opportunity", "stable_hot", "low_priority"];
  const titles: Record<string, string> = {
    oversaturated: "과포화 가능성",
    opportunity: "기회 영역",
    stable_hot: "안정적 인기",
    low_priority: "비추천/저관심",
  };
  return (
    <div className="grid gap-4 sm:grid-cols-2">
      {order.map((key) => (
        <div
          key={key}
          className={`rounded-xl border p-4 ${STYLE[key] ?? "border-slate-700"}`}
        >
          <h3 className="mb-2 text-sm font-semibold text-slate-200">{titles[key]}</h3>
          <ul className="flex flex-wrap gap-2">
            {(groups[key] ?? []).slice(0, 10).map((x) => (
              <li
                key={x.keyword}
                className="rounded-full bg-slate-950/50 px-2 py-0.5 text-xs text-slate-300"
              >
                {x.keyword}
              </li>
            ))}
            {(groups[key] ?? []).length === 0 && (
              <li className="text-xs text-slate-500">해당 분류 키워드 없음</li>
            )}
          </ul>
        </div>
      ))}
    </div>
  );
}
