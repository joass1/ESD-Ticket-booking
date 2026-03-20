import { useEffect, useState, useRef } from 'react';
import { io } from 'socket.io-client';

const TICKET_SERVICE_URL = 'http://localhost:5006';

export default function useSocket(bookingId) {
  const [ticketReady, setTicketReady] = useState(false);
  const [connected, setConnected] = useState(false);
  const socketRef = useRef(null);

  useEffect(() => {
    if (!bookingId) return;

    let cancelled = false;

    // Defer connection to next tick — React StrictMode's synchronous
    // unmount+remount cancels this timeout before a socket is created,
    // preventing the "closed before established" WebSocket error.
    const timerId = setTimeout(() => {
      if (cancelled) return;

      const socket = io(TICKET_SERVICE_URL, {
        transports: ['websocket', 'polling'],
      });
      socketRef.current = socket;

      socket.on('connect', () => {
        setConnected(true);
        socket.emit('join', { booking_id: bookingId });
      });

      socket.on('disconnect', () => {
        if (!cancelled) setConnected(false);
      });

      socket.on('ticket_ready', (data) => {
        if (!cancelled && (data.booking_id === bookingId || data.booking_id == bookingId)) {
          setTicketReady(true);
        }
      });
    }, 0);

    return () => {
      cancelled = true;
      clearTimeout(timerId);
      if (socketRef.current) {
        socketRef.current.disconnect();
        socketRef.current = null;
      }
    };
  }, [bookingId]);

  return { ticketReady, connected };
}
