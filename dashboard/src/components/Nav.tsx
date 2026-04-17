import Link from "next/link";

const links = [
  { href: "/funnel", label: "Funnel" },
  { href: "/hooks", label: "Hooks" },
  { href: "/closers", label: "Closers" },
  { href: "/compliance", label: "Compliance" },
];

export function Nav() {
  return (
    <nav className="border-b bg-white">
      <div className="mx-auto flex max-w-6xl items-center gap-6 px-6 py-4">
        <Link href="/" className="font-semibold">CRM</Link>
        {links.map((l) => (
          <Link key={l.href} href={l.href} className="text-sm text-slate-600 hover:text-slate-900">
            {l.label}
          </Link>
        ))}
      </div>
    </nav>
  );
}
