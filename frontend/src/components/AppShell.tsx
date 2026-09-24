import { House, MessageCircle, Plus, User, type LucideIcon } from "lucide-react";
import { Link, NavLink, Outlet } from "react-router";
import birdUrl from "../assets/renest-bird.svg";

// The frame around every in-app page: a left rail on desktop, a bottom tab bar on phones.
// It's the element of the "/" route in router.tsx, so every in-app page is a child route.
// E1.6's route protection wraps this one route rather than each page.

type NavItemConfig = { label: string; icon: LucideIcon } & (
  | { to: string; href?: never }
  // External link, opened in a new tab (never shown as the current page).
  | { href: string; to?: never }
);

// One list feeds both the rail and the tab bar, so they can't drift apart.
const NAV_ITEMS: NavItemConfig[] = [
  { label: "Home", icon: House, to: "/" },
  // No in-app inbox: buyers and sellers talk over Creighton email.
  { label: "Messages", icon: MessageCircle, href: "https://outlook.office.com/mail" },
  { label: "Sell", icon: Plus, to: "/sell" },
  { label: "Account", icon: User, to: "/account" },
];

type NavLayout = "rail" | "tab";

const focusRing =
  "focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-accent";

function NavItemContent({
  item,
  layout,
  active,
}: {
  item: NavItemConfig;
  layout: NavLayout;
  active: boolean;
}) {
  const Icon = item.icon;
  const color = active ? "text-accent" : "text-text-muted";

  if (layout === "rail") {
    return (
      <>
        <Icon aria-hidden className="size-6" />
        <span className={`font-mono text-nav font-medium ${color}`}>{item.label}</span>
      </>
    );
  }
  return (
    <>
      {/* The active tab's icon sits in a tinted pill (Figma 11:87). */}
      <span
        className={`flex h-8 w-10 items-center justify-center rounded-md ${active ? "bg-accent-soft" : ""}`}
      >
        <Icon aria-hidden className="size-6" />
      </span>
      <span
        className={`font-mono text-nav-sm leading-3 ${active ? "font-semibold" : "font-medium"} ${color}`}
      >
        {item.label}
      </span>
    </>
  );
}

function NavItem({ item, layout }: { item: NavItemConfig; layout: NavLayout }) {
  const shape =
    layout === "rail"
      ? "size-16 justify-center rounded-md" // 64×64
      : "min-h-11 w-16 justify-center"; // 64 wide, ~48 tall
  const base = `flex flex-col items-center gap-1 ${shape} ${focusRing}`;

  if (item.href !== undefined) {
    return (
      <a
        href={item.href}
        target="_blank"
        rel="noopener noreferrer"
        className={`${base} text-text-muted`}
      >
        <NavItemContent item={item} layout={layout} active={false} />
        <span className="sr-only">(opens in a new tab)</span>
      </a>
    );
  }

  return (
    // NavLink sets aria-current="page" on the active item. `end` keeps Home from also
    // matching every other path under "/".
    <NavLink
      to={item.to!}
      end={item.to === "/"}
      className={({ isActive }) =>
        `${base} ${isActive ? "text-accent" : "text-text-muted"} ` +
        (layout === "rail" && isActive ? "bg-accent-soft" : "")
      }
    >
      {({ isActive }) => <NavItemContent item={item} layout={layout} active={isActive} />}
    </NavLink>
  );
}

function NavRail() {
  return (
    <nav
      aria-label="Main"
      className="fixed inset-y-0 left-0 hidden w-22 flex-col items-center justify-between border-r border-border bg-surface py-6 lg:flex"
    >
      <div className="flex flex-col items-center gap-10">
        <Link
          to="/"
          aria-label="ReNest home"
          className={`flex size-12 items-center justify-center rounded-full border-2 border-accent bg-surface ${focusRing}`}
        >
          <img src={birdUrl} alt="" width={24} height={24} />
        </Link>
        <ul className="flex flex-col items-center gap-4">
          {NAV_ITEMS.map((item) => (
            <li key={item.label}>
              <NavItem item={item} layout="rail" />
            </li>
          ))}
        </ul>
      </div>
      <p className="flex flex-col items-center gap-1 text-center">
        <span aria-hidden className="text-caption font-semibold text-accent">
          CU
        </span>
        <span aria-hidden className="font-mono text-nav font-medium text-text-placeholder">
          Verified
        </span>
        <span className="sr-only">Creighton University verified</span>
      </p>
    </nav>
  );
}

function TabBar() {
  return (
    <nav
      aria-label="Main"
      // Bottom padding clears the iPhone home indicator (needs viewport-fit=cover in index.html).
      className="fixed inset-x-0 bottom-0 z-10 border-t border-border bg-surface px-4 pt-3 pb-[max(0.75rem,env(safe-area-inset-bottom))] lg:hidden"
    >
      <ul className="flex items-center justify-between">
        {NAV_ITEMS.map((item) => (
          <li key={item.label}>
            <NavItem item={item} layout="tab" />
          </li>
        ))}
      </ul>
    </nav>
  );
}

export function AppShell() {
  return (
    <div className="min-h-dvh bg-bg">
      <NavRail />
      <main
        // Mobile bottom padding >= the tab bar's height (12 top + 48 item + 1 border, plus the
        // bottom safe area), so nothing hides behind it.
        className="px-4 pt-5 pb-[calc(4rem+max(0.75rem,env(safe-area-inset-bottom)))] lg:pt-6 lg:pr-8 lg:pb-6 lg:pl-30"
      >
        <Outlet />
      </main>
      {/* After <main> so keyboard users reach the page content before the tab bar. */}
      <TabBar />
    </div>
  );
}
