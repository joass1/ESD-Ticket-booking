import { useEffect, useState, useRef } from 'react';
import { io } from 'socket.io-client';

const TICKET_SERVICE_URL = 'http://localhost:5006';

export default function useSocket(bookingId) {
  const [ticketReady, setTicketReady] = useState(false);
  const [connected, setConnected] = useState(false);
  const socketRef = useRef(null);

  useEffect(() => {
    if (!bookingId) return;

    const socket = io(TICKET_SERVICE_URL, {
      transports: ['websocket', 'polling'],
    });
    socketRef.current = socket;

    socket.on('connect', () => {
      setConnected(true);
      socket.emit('join', { booking_id: bookingId });
    });

    socket.on('disconnect', () => {
      setConnected(false);
    });

    socket.on('ticket_ready', (data) => {
      if (data.booking_id === bookingId || data.booking_id == bookingId) {
        setTicketReady(true);
      }
    });

    return () => {
      socket.disconnect();
      socketRef.current = null;
      setConnected(false);
      setTicketReady(false);
    };
  }, [bookingId]);

  return { ticketReady, connected };
}
