import { useState, useEffect, useRef } from 'react';
import { Link, useLocation } from 'react-router-dom';
import {
  Ticket,
  CalendarDays,
  ClipboardList,
  ChevronDown,
  ScanLine,
} from 'lucide-react';
import { cn } from '@/lib/utils';
import { Button, buttonVariants } from '@/components/ui/button';
import { MenuToggleIcon } from '@/components/ui/menu-toggle-icon';
import { useScroll } from '@/components/ui/use-scroll';

const DEMO_USERS = ['user_001', 'user_002', 'user_003', 'admin'];

const NAV_ITEMS = [
  { to: '/', label: 'Events', Icon: CalendarDays },
  { to: '/bookings', label: 'My Bookings', Icon: ClipboardList },
  { to: '/scanner', label: 'Scanner', Icon: ScanLine, adminOnly: true },
];

function UserSelector({ userId, setUserId, onSelect, fullWidth = false }) {
  const [open, setOpen] = useState(false);
  const ref = useRef(null);

  useEffect(() => {
    function handleClickOutside(e) {
      if (ref.current && !ref.current.contains(e.target)) setOpen(false);
    }
    document.addEventListener('mousedown', handleClickOutside);
    return () => document.removeEventListener('mousedown', handleClickOutside);
  }, []);

  return (
    <div ref={ref} className={cn('relative', fullWidth && 'w-full')}>
      <button
        onClick={() => setOpen(!open)}
        className={cn(
          'flex items-center gap-1.5 px-3 py-2 rounded-lg text-sm text-muted-foreground hover:text-foreground hover:bg-white/5 transition-colors',
          fullWidth && 'w-full',
        )}
      >
        <span className="w-6 h-6 rounded-full bg-primary/20 flex items-center justify-center text-xs text-primary font-bold shrink-0">
          {userId.slice(-1).toUpperCase()}
        </span>
        <span className="truncate">{userId}</span>
        <ChevronDown
          size={14}
          className={cn(
            'shrink-0 transition-transform duration-200',
            open && 'rotate-180',
          )}
        />
      </button>

      {open && (
        <div
          className={cn(
            'absolute mt-1 bg-card border border-border rounded-lg shadow-lg py-1 z-50',
            fullWidth ? 'left-0 right-0' : 'right-0 w-40',
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
                'w-full text-left px-4 py-2 text-sm transition-colors',
                u === userId
                  ? 'text-primary bg-primary/10'
                  : 'text-muted-foreground hover:text-foreground hover:bg-white/5',
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
  const [open, setOpen] = useState(false);
  const scrolled = useScroll(10);
  const location = useLocation();

  // Close mobile menu on route change
  useEffect(() => {
    setOpen(false);
  }, [location.pathname]);

  // Lock body scroll when mobile menu is open
  useEffect(() => {
    if (open) {
      document.body.style.overflow = 'hidden';
    } else {
      document.body.style.overflow = '';
    }
    return () => {
      document.body.style.overflow = '';
    };
  }, [open]);

  const isActive = (to) => {
    if (to === '/') return location.pathname === '/';
    return location.pathname.startsWith(to);
  };

  return (
    <header
      className={cn(
        'sticky top-0 z-50 mx-auto w-full max-w-5xl border-b border-transparent md:rounded-md md:border md:transition-all md:duration-300 md:ease-out',
        {
          'bg-background/95 supports-[backdrop-filter]:bg-background/50 border-border backdrop-blur-lg md:top-4 md:max-w-4xl md:shadow-lg':
            scrolled && !open,
          'bg-background/90': open,
          'bg-background': !scrolled && !open,
        },
      )}
    >
      <nav
        className={cn(
          'flex h-14 w-full items-center justify-between px-4 md:h-12 md:transition-all md:duration-300 md:ease-out',
          {
            'md:px-2': scrolled,
          },
        )}
      >
        {/* Logo */}
        <Link
          to="/"
          className="flex items-center gap-2 text-primary font-bold text-lg"
        >
          <Ticket size={22} />
          TicketBook
        </Link>

        {/* Desktop nav */}
        <div className="hidden items-center gap-1 md:flex">
          {NAV_ITEMS.filter((item) => !item.adminOnly || userId === 'admin').map((item) => (
            <Link
              key={item.to}
              to={item.to}
              className={cn(
                buttonVariants({ variant: 'ghost' }),
                'gap-1.5',
                isActive(item.to)
                  ? 'bg-primary/10 text-primary'
                  : 'text-foreground',
              )}
            >
              <item.Icon size={16} />
              {item.label}
            </Link>
          ))}
          <div className="ml-2">
            <UserSelector userId={userId} setUserId={setUserId} />
          </div>
        </div>

        {/* Mobile toggle */}
        <Button
          size="icon"
          variant="outline"
          onClick={() => setOpen(!open)}
          className="md:hidden"
        >
          <MenuToggleIcon open={open} className="size-5" duration={300} />
        </Button>
      </nav>

      {/* Mobile menu */}
      <div
        className={cn(
          'bg-background/95 backdrop-blur-lg fixed top-14 right-0 bottom-0 left-0 z-50 flex flex-col overflow-hidden border-t border-border md:hidden',
          open ? 'block' : 'hidden',
        )}
      >
        <div
          data-slot={open ? 'open' : 'closed'}
          className={cn(
            'data-[slot=open]:animate-in data-[slot=open]:fade-in-0 data-[slot=open]:zoom-in-95 ease-out',
            'flex h-full w-full flex-col justify-between gap-y-2 p-4',
          )}
        >
          <div className="grid gap-y-1">
            {NAV_ITEMS.filter((item) => !item.adminOnly || userId === 'admin').map((item) => (
              <Link
                key={item.to}
                to={item.to}
                onClick={() => setOpen(false)}
                className={cn(
                  buttonVariants({ variant: 'ghost', className: 'justify-start gap-2' }),
                  isActive(item.to)
                    ? 'bg-primary/10 text-primary'
                    : 'text-foreground',
                )}
              >
                <item.Icon size={16} />
                {item.label}
              </Link>
            ))}
            <div className="mt-2 pt-2 border-t border-border">
              <p className="px-3 py-1 text-xs text-muted-foreground font-medium uppercase tracking-wider">
                Switch User
              </p>
              <UserSelector
                userId={userId}
                setUserId={setUserId}
                onSelect={() => setOpen(false)}
                fullWidth
              />
            </div>
          </div>
        </div>
      </div>
    </header>
  );
}
