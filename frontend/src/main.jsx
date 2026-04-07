import { StrictMode } from 'react';
import { createRoot } from 'react-dom/client';
import { createBrowserRouter, RouterProvider } from 'react-router-dom';
import './index.css';
import Layout from './components/Layout.jsx';
import EventsPage from './pages/EventsPage.jsx';
import NotFoundPage from './pages/NotFoundPage.jsx';
import EventDetailPage from './pages/EventDetailPage.jsx';
import WaitlistPage from './pages/WaitlistPage.jsx';
import BookingHistoryPage from './pages/BookingHistoryPage.jsx';
import BookingPage from './pages/BookingPage.jsx';
import CreateEventPage from './pages/CreateEventPage.jsx';
import ScannerPage from './pages/ScannerPage.jsx';

const router = createBrowserRouter([
  {
    path: '/',
    element: <Layout />,
    errorElement: <NotFoundPage />,
    children: [
      { index: true, element: <EventsPage /> },
      { path: 'events/create', element: <CreateEventPage /> },
      { path: 'events/:eventId', element: <EventDetailPage /> },
      { path: 'events/:eventId/book', element: <BookingPage /> },
      { path: 'events/:eventId/waitlist', element: <WaitlistPage /> },
      { path: 'bookings', element: <BookingHistoryPage /> },
      { path: 'scanner', element: <ScannerPage /> },
    ],
  },
]);

createRoot(document.getElementById('root')).render(
  <StrictMode>
    <RouterProvider router={router} />
  </StrictMode>
);
