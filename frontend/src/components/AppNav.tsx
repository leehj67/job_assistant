import Link from "next/link";

const links = [
  { href: "/", label: "대시보드" },
  { href: "/consultant", label: "컨설턴트 보드" },
  { href: "/academy", label: "교육기관 인사이트" },
  { href: "/jobseeker", label: "취준생 인사이트" },
];

export function AppNav() {
  return (
    <header className="border-b border-slate-800 bg-slate-950/80 backdrop-blur">
      <div className="mx-auto flex max-w-6xl items-center justify-between gap-4 px-4 py-3">
        <Link href="/" className="text-lg font-semibold tracking-tight text-white">
          일햇음청년 <span className="text-sky-400">제조기</span>
        </Link>
        <nav className="flex flex-wrap gap-3 text-sm">
          {links.map((l) => (
            <Link
              key={l.href}
              href={l.href}
              className="rounded-md px-2 py-1 text-slate-300 hover:bg-slate-800 hover:text-white"
            >
              {l.label}
            </Link>
          ))}
        </nav>
      </div>
    </header>
  );
}
