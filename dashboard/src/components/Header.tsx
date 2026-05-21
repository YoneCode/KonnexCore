import type { JSX } from "react";
import { Link, NavLink } from "react-router-dom";
import { cn } from "../lib/cn";

const navItems = [
  { to: "/", label: "Home" },
  { to: "/rootid", label: "RootID" },
  { to: "/detverify", label: "DetVerify" },
  { to: "/honeynet", label: "Honeynet" },
  { to: "/full-stack", label: "Full Stack" },
];

export function Header(): JSX.Element {
  return (
    <header className="sticky top-0 z-30 border-b border-rule bg-paper/85 backdrop-blur-sm">
      <div className="mx-auto flex max-w-[1200px] items-center justify-between gap-8 px-6 py-4">
        <Link
          to="/"
          className="flex items-center gap-3 font-display text-title font-medium tracking-tight text-ink"
        >
          <span className="block size-2 rounded-full bg-signal" aria-hidden />
          KonnexCore
        </Link>
        <nav className="flex items-center gap-6">
          {navItems.map((item) => (
            <NavLink
              key={item.to}
              to={item.to}
              end={item.to === "/"}
              className={({ isActive }) =>
                cn(
                  "font-mono text-label uppercase tracking-wide transition-colors",
                  isActive ? "text-ink" : "text-subtext hover:text-ink",
                )
              }
            >
              {item.label}
            </NavLink>
          ))}
        </nav>
        <a
          href="https://github.com/YoneCode/KonnexCore"
          className="hidden font-mono text-label uppercase tracking-wider text-subtext hover:text-ink md:inline"
          target="_blank"
          rel="noreferrer noopener"
        >
          GitHub ↗
        </a>
      </div>
    </header>
  );
}
