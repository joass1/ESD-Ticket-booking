import { useEffect, useRef, useState } from 'react';
import { useOutletContext } from 'react-router-dom';
import { Camera, CheckCircle, XCircle, Keyboard } from 'lucide-react';
import { Html5Qrcode } from 'html5-qrcode';
import { api } from '../api/client.js';

export default function ScannerPage() {
  const { userId } = useOutletContext();
  const [scanning, setScanning] = useState(false);
  const [result, setResult] = useState(null);
  const [processing, setProcessing] = useState(false);
  const [manualInput, setManualInput] = useState('');
  const [showManual, setShowManual] = useState(false);
  const scannerRef = useRef(null);
  const html5QrRef = useRef(null);

  const isAdmin = userId === 'admin';

  const startScanner = async () => {
    setResult(null);
    setScanning(true);

    const html5Qr = new Html5Qrcode('qr-reader');
    html5QrRef.current = html5Qr;

    try {
      await html5Qr.start(
        { facingMode: 'environment' },
        { fps: 10, qrbox: { width: 250, height: 250 } },
        async (decodedText) => {
          await html5Qr.stop().catch(() => {});
          html5QrRef.current = null;
          setScanning(false);
          await validateTicket(decodedText);
        },
        () => {}
      );
    } catch {
      setScanning(false);
      setShowManual(true);
    }
  };

  const stopScanner = async () => {
    if (html5QrRef.current) {
      await html5QrRef.current.stop().catch(() => {});
      html5QrRef.current = null;
    }
    setScanning(false);
  };

  const validateTicket = async (qrData) => {
    setProcessing(true);
    setResult(null);
    try {
      const data = await api('/api/tickets/validate', {
        method: 'POST',
        body: JSON.stringify({ qr_data: qrData }),
      });

      // Fetch event name and seat details in parallel
      const [eventData, seatsData] = await Promise.all([
        api(`/api/event/${data.event_id}`).catch(() => null),
        api(`/api/seats/event/${data.event_id}`).catch(() => []),
      ]);

      const allSeats = Array.isArray(seatsData) ? seatsData : [];
      const seat = allSeats.find((s) => s.seat_id === data.seat_id);

      setResult({
        type: 'success',
        message: 'Ticket validated!',
        data: {
          ...data,
          event_name: eventData?.name || `Event #${data.event_id}`,
          section_name: seat?.section_name || 'Unknown',
          seat_number: seat?.seat_number || `Seat #${data.seat_id}`,
        },
      });
    } catch (err) {
      setResult({
        type: 'error',
        message: err.message || 'Validation failed',
      });
    } finally {
      setProcessing(false);
    }
  };

  const handleManualSubmit = (e) => {
    e.preventDefault();
    if (manualInput.trim()) {
      validateTicket(manualInput.trim());
      setManualInput('');
    }
  };

  useEffect(() => {
    return () => {
      if (html5QrRef.current) {
        html5QrRef.current.stop().catch(() => {});
      }
    };
  }, []);

  if (!isAdmin) {
    return (
      <div className="max-w-lg mx-auto text-center py-12 space-y-4">
        <p className="text-primary font-medium">Admin access required</p>
        <p className="text-text-secondary text-sm">Switch to the admin account to scan tickets.</p>
      </div>
    );
  }

  return (
    <div className="max-w-lg mx-auto space-y-6">
      <div className="bg-bg-card rounded-xl border border-white/10 p-5">
        <h1 className="text-2xl font-bold text-text-primary">Ticket Scanner</h1>
        <p className="text-text-secondary text-sm mt-1">Scan QR codes to validate entry</p>
      </div>

      {/* Scanner viewport */}
      <div className="bg-bg-card rounded-xl border border-white/10 overflow-hidden">
        <div id="qr-reader" ref={scannerRef} className={scanning ? '' : 'hidden'} />

        {!scanning && !result && !showManual && (
          <div className="p-12 text-center space-y-4">
            <div className="w-20 h-20 mx-auto rounded-full bg-primary/20 flex items-center justify-center">
              <Camera size={36} className="text-primary" />
            </div>
            <p className="text-text-secondary text-sm">Point camera at a ticket QR code</p>
          </div>
        )}
      </div>

      {/* Manual input fallback */}
      {showManual && !scanning && (
        <form onSubmit={handleManualSubmit} className="bg-bg-card rounded-xl border border-white/10 p-5 space-y-3">
          <div className="flex items-center gap-2 text-text-secondary text-sm">
            <Keyboard size={16} />
            <span>Camera unavailable — enter QR code manually</span>
          </div>
          <div className="flex gap-2">
            <input
              type="text"
              value={manualInput}
              onChange={(e) => setManualInput(e.target.value)}
              placeholder="e.g. 2:a1b2c3d4e5f6g7h8"
              className="flex-1 bg-bg-primary text-text-primary placeholder-text-secondary border border-white/10 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-1 focus:ring-primary"
            />
            <button
              type="submit"
              disabled={!manualInput.trim() || processing}
              className="px-4 py-2 bg-primary hover:bg-primary/80 disabled:opacity-50 text-black font-semibold rounded-lg text-sm transition-colors"
            >
              Validate
            </button>
          </div>
        </form>
      )}

      {/* Result display */}
      {result && (
        <div
          className={`rounded-xl border p-6 space-y-3 ${
            result.type === 'success'
              ? 'bg-green-500/10 border-green-500/30'
              : 'bg-red-500/10 border-red-500/30'
          }`}
        >
          <div className="flex items-center gap-3">
            {result.type === 'success' ? (
              <CheckCircle size={28} className="text-green-400" />
            ) : (
              <XCircle size={28} className="text-red-400" />
            )}
            <p className={`text-lg font-semibold ${result.type === 'success' ? 'text-green-400' : 'text-red-400'}`}>
              {result.message}
            </p>
          </div>
          {result.data && (
            <div className="text-sm text-text-primary space-y-2 pl-10">
              <p><span className="text-text-secondary">Event:</span> {result.data.event_name}</p>
              <p><span className="text-text-secondary">Section:</span> {result.data.section_name}</p>
              <p><span className="text-text-secondary">Seat:</span> {result.data.seat_number}</p>
              <p><span className="text-text-secondary">Booking:</span> #{result.data.booking_id}</p>
              <p><span className="text-text-secondary">User:</span> {result.data.user_id}</p>
            </div>
          )}
        </div>
      )}

      {/* Controls */}
      <div className="flex gap-3">
        {!scanning ? (
          <>
            <button
              onClick={startScanner}
              disabled={processing}
              className="flex-1 py-3 bg-primary hover:bg-primary/80 disabled:opacity-50 text-black font-semibold rounded-lg transition-colors"
            >
              {result ? 'Scan Next' : 'Start Scanner'}
            </button>
            {!showManual && (
              <button
                onClick={() => setShowManual(true)}
                className="px-4 py-3 border border-white/10 text-text-secondary hover:text-text-primary rounded-lg transition-colors"
              >
                <Keyboard size={20} />
              </button>
            )}
          </>
        ) : (
          <button
            onClick={stopScanner}
            className="flex-1 py-3 bg-red-500 hover:bg-red-600 text-white font-semibold rounded-lg transition-colors"
          >
            Stop Scanner
          </button>
        )}
      </div>

      {processing && (
        <p className="text-center text-text-secondary text-sm animate-pulse">Validating ticket...</p>
      )}
    </div>
  );
}
