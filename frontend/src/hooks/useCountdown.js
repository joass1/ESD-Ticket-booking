import { useState, useEffect } from 'react';

export default function useCountdown(expiresAt) {
  const [remaining, setRemaining] = useState(() => calcRemaining(expiresAt));

  useEffect(() => {
    if (!expiresAt) return;
    setRemaining(calcRemaining(expiresAt));
    const id = setInterval(() => {
      const r = calcRemaining(expiresAt);
      setRemaining(r);
      if (r <= 0) clearInterval(id);
    }, 1000);
    return () => clearInterval(id);
  }, [expiresAt]);

  const totalSeconds = Math.max(0, remaining);
  const minutes = Math.floor(totalSeconds / 60);
  const seconds = totalSeconds % 60;
  const expired = totalSeconds <= 0;
  const formatted = `${String(minutes).padStart(2, '0')}:${String(seconds).padStart(2, '0')}`;

  return { minutes, seconds, expired, formatted };
}

function calcRemaining(expiresAt) {
  if (!expiresAt) return 0;
  return Math.floor((new Date(expiresAt).getTime() - Date.now()) / 1000);
}
