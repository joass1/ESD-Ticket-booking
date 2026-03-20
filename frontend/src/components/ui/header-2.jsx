import { useState, useEffect, useRef } from "react";
import { Link, useLocation } from "react-router-dom";
import {
  Ticket,
  CalendarDays,
  ClipboardList,
  ChevronDown,
} from "lucide-react";
import { cn } from "@/lib/utils";
import { Button } from "@/components/ui/button";
import { MenuToggleIcon } from "@/components/ui/menu-toggle-icon";
import { useScroll } from "@/components/ui/use-scroll";

const DEMO_USERS = ["user_001", "user_002", "user_003", "admin"];

const NAV_ITEMS = [
  { to: "/", label: "Events", Icon: CalendarDays },
  { to: "/bookings", label: "My Bookings", Icon: ClipboardList },
];

function NavLink({ to, label, Icon, active, onClick }) {
  return (
    <Link
      to={to}
      onClick={onClick}
      className={cn(
        "flex items-center gap-1.5 px-3 py-2 rounded-lg text-sm font-medium transition-colors",
        active
          ? "bg-accent/20 text-accent"
          : "text-text-secondary hover:text-text-primary hover:bg-white/5"
      )}
    >
      <Icon size={16} />
      {label}
    </Link>
  );
}

function UserSelector({ userId, setUserId, onSelect, fullWidth = false }) {
  const [open, setOpen] = useState(false);
  const ref = useRef(null);

  useEffect(() => {
    function handleClickOutside(e) {
      if (ref.current && !ref.current.contains(e.target)) {
        setOpen(false);
      }
    }
    document.addEventListener("mousedown", handleClickOutside);
    return () => document.removeEventListener("mousedown", handleClickOutside);
  }, []);

  const lastSegment = userId.split("_").pop();

  return (
    <div ref={ref} className={cn("relative", fullWidth && "w-full")}>
      <button
        onClick={() => setOpen(!open)}
        className={cn(
          "flex items-center gap-1.5 px-3 py-2 rounded-lg text-sm text-text-secondary hover:text-text-primary hover:bg-white/5 transition-colors",
          fullWidth && "w-full"
        )}
      >
        <span className="w-6 h-6 rounded-full bg-accent/30 flex items-center justify-center text-xs text-accent font-bold shrink-0">
          {lastSegment.charAt(0).toUpperCase()}
        </span>
        <span className="truncate">{userId}</span>
        <ChevronDown
          size={14}
          className={cn(
            "shrink-0 transition-transform duration-200",
            open && "rotate-180"
          )}
        />
      </button>

      {open && (
        <div
          className={cn(
            "absolute mt-1 bg-bg-card border border-white/10 rounded-lg shadow-lg py-1 z-50",
            fullWidth ? "left-0 right-0" : "right-0 w-40"
          )}
        >
          {DEMO_USERS.map((u) => (
            <button
              key={u}
              onClick={() => {
                setUserId(u);
                setOpen(false);
                onSelect?.();
              }}
              className={cn(
                "w-full text-left px-4 py-2 text-sm transition-colors",
                u === userId
                  ? "text-accent bg-accent/10"
                  : "text-text-secondary hover:text-text-primary hover:bg-white/5"
              )}
            >
              {u}
            </button>
          ))}
        </div>
      )}
    </div>
  );
}

export default function Header({ userId, setUserId }) {
  const [mobileOpen, setMobileOpen] = useState(false);
  const location = useLocation();
  const { scrolled } = useScroll(10);

  // Close mobile menu on route change
  useEffect(() => {
    setMobileOpen(false);
  }, [location.pathname]);

  const isActive = (to) => {
    if (to === "/") return location.pathname === "/";
    return location.pathname.startsWith(to);
  };

  return (
    <header
      className={cn(
        "sticky top-0 z-50 w-full transition-all duration-300",
        scrolled
          ? "bg-bg-card/90 backdrop-blur-md shadow-lg border-b border-white/10"
          : "bg-bg-card/80 backdrop-blur-md border-b border-white/10"
      )}
    >
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
        <div className="flex h-16 items-center justify-between">
          {/* Logo */}
          <Link
            to="/"
            className="flex items-center gap-2 text-primary font-bold text-xl"
          >
            <Ticket size={24} />
            TicketBook
          </Link>

          {/* Desktop nav */}
          <div className="hidden md:flex items-center gap-2">
            {NAV_ITEMS.map((item) => (
              <NavLink
                key={item.to}
                to={item.to}
                label={item.label}
                Icon={item.Icon}
                active={isActive(item.to)}
              />
            ))}
            <div className="ml-4">
              <UserSelector userId={userId} setUserId={setUserId} />
            </div>
          </div>

          {/* Mobile toggle */}
          <Button
            variant="ghost"
            size="icon"
            className="md:hidden"
            onClick={() => setMobileOpen(!mobileOpen)}
            aria-label="Toggle menu"
          >
            <MenuToggleIcon isOpen={mobileOpen} />
          </Button>
        </div>
      </div>

      {/* Mobile menu */}
      <div
        className={cn(
          "md:hidden overflow-hidden transition-all duration-300 ease-in-out",
          mobileOpen ? "max-h-96 opacity-100" : "max-h-0 opacity-0"
        )}
      >
        <div className="px-4 pb-4 pt-2 space-y-1 border-t border-white/10">
          {NAV_ITEMS.map((item) => (
            <NavLink
              key={item.to}
              to={item.to}
              label={item.label}
              Icon={item.Icon}
              active={isActive(item.to)}
              onClick={() => setMobileOpen(false)}
            />
          ))}
          <div className="pt-2 border-t border-white/10">
            <p className="px-3 py-1 text-xs text-text-secondary font-medium uppercase tracking-wider">
              Switch User
            </p>
            <UserSelector
              userId={userId}
              setUserId={setUserId}
              onSelect={() => setMobileOpen(false)}
              fullWidth
            />
          </div>
        </div>
      </div>
    </header>
  );
}
