export default function ConsultantLoading() {
  return (
    <div className="space-y-4 py-4">
      <div className="h-8 w-48 animate-pulse rounded bg-slate-800" />
      <div className="h-64 animate-pulse rounded-xl bg-slate-800/60" />
      <p className="text-sm text-slate-500">컨설턴트 보드를 불러오는 중…</p>
    </div>
  );
}
