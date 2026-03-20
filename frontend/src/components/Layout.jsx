import { useState } from 'react';
import { Outlet } from 'react-router-dom';
import Header from '@/components/ui/header-2';

const DEMO_USERS = ['user_001', 'user_002', 'user_003', 'admin'];

export default function Layout() {
  const [userId, setUserId] = useState(DEMO_USERS[0]);

  return (
    <div className="min-h-screen bg-bg-primary">
      <Header userId={userId} setUserId={setUserId} />
      <main className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
        <Outlet context={{ userId, setUserId }} />
      </main>
    </div>
  );
}
