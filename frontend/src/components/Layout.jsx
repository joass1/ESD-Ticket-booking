import { useState } from 'react';
import { Link, Outlet, useLocation } from 'react-router-dom';
import { Ticket, CalendarDays, ClipboardList, ChevronDown } from 'lucide-react';

const DEMO_USERS = ['user_001', 'user_002', 'user_003'];

export default function Layout() {
  const [userId, setUserId] = useState(DEMO_USERS[0]);
  const [userMenuOpen, setUserMenuOpen] = useState(false);
  const location = useLocation();

  const navLink = (to, label, Icon) => {
    const active = location.pathname === to || (to === '/' && location.pathname === '/');
    return (
      <Link
        to={to}
        className={`flex items-center gap-1.5 px-3 py-2 rounded-lg text-sm font-medium transition-colors ${
          active
            ? 'bg-accent/20 text-accent'
            : 'text-text-secondary hover:text-text-primary hover:bg-white/5'
        }`}
      >
        <Icon size={16} />
        {label}
      </Link>
    );
  };

  return (
    <div className="min-h-screen bg-bg-primary">
      <nav className="sticky top-0 z-50 bg-bg-card/80 backdrop-blur-md border-b border-white/10">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 h-16 flex items-center justify-between">
          <Link to="/" className="flex items-center gap-2 text-accent font-bold text-xl">
            <Ticket size={24} />
            TicketBook
          </Link>

          <div className="flex items-center gap-2">
            {navLink('/', 'Events', CalendarDays)}
            {navLink('/bookings', 'My Bookings', ClipboardList)}

            <div className="relative ml-4">
              <button
                onClick={() => setUserMenuOpen(!userMenuOpen)}
                className="flex items-center gap-1.5 px-3 py-2 rounded-lg text-sm text-text-secondary hover:text-text-primary hover:bg-white/5 transition-colors"
              >
                <span className="w-6 h-6 rounded-full bg-accent/30 flex items-center justify-center text-xs text-accent font-bold">
                  {userId.slice(-1)}
                </span>
                {userId}
                <ChevronDown size={14} />
              </button>

              {userMenuOpen && (
                <div className="absolute right-0 mt-1 w-40 bg-bg-card border border-white/10 rounded-lg shadow-lg py-1">
                  {DEMO_USERS.map((u) => (
                    <button
                      key={u}
                      onClick={() => { setUserId(u); setUserMenuOpen(false); }}
                      className={`w-full text-left px-4 py-2 text-sm transition-colors ${
                        u === userId
                          ? 'text-accent bg-accent/10'
                          : 'text-text-secondary hover:text-text-primary hover:bg-white/5'
                      }`}
                    >
                      {u}
                    </button>
                  ))}
                </div>
              )}
            </div>
          </div>
        </div>
      </nav>

      <main className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
        <Outlet context={{ userId, setUserId }} />
      </main>
    </div>
  );
}
