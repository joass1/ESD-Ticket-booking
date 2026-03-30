import { useEffect, useState } from 'react';
import { useParams, useSearchParams, useOutletContext, useNavigate } from 'react-router-dom';
import { Loader2 } from 'lucide-react';
import { api } from '../api/client.js';
import StepIndicator from '../components/BookingWizard/StepIndicator.jsx';
import ReviewStep from '../components/BookingWizard/ReviewStep.jsx';
import PaymentStep from '../components/BookingWizard/PaymentStep.jsx';
import ConfirmationStep from '../components/BookingWizard/ConfirmationStep.jsx';

const STEPS = ['Select Seat', 'Review', 'Payment', 'Confirmation'];

const PROCESSING_MESSAGES = [
  'Reserving your seat...',
  'Processing payment...',
  'Confirming booking...',
  'Generating your ticket...',
];

export default function BookingPage() {
  const { eventId } = useParams();
  const [searchParams] = useSearchParams();
  const { userId } = useOutletContext();
  const navigate = useNavigate();

  const isAdmin = userId === 'admin';
  const seatId = searchParams.get('seatId');
  const sectionId = searchParams.get('sectionId');

  const [currentStep, setCurrentStep] = useState(1); // Start at Review (seat already selected)
  const [event, setEvent] = useState(null);
  const [seat, setSeat] = useState(null);
  const [section, setSection] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  // Saga state
  const [sagaData, setSagaData] = useState(null); // { saga_id, booking_id, client_secret, amount, expires_at }
  const [processing, setProcessing] = useState(false);
  const [processingMsg, setProcessingMsg] = useState('');

  // Fetch event and seat details
  useEffect(() => {
    const fetchDetails = async () => {
      setLoading(true);
      setError(null);
      try {
        const [eventData, seatsData] = await Promise.all([
          api(`/api/event/${eventId}`),
          api(`/api/seats/event/${eventId}`),
        ]);
        setEvent(eventData);

        // Guard: reject booking for cancelled events
        if (eventData.status === 'cancelled') {
          setError('This event has been cancelled and is no longer accepting bookings.');
          setLoading(false);
          return;
        }

        const allSeats = Array.isArray(seatsData) ? seatsData : [];
        const foundSeat = allSeats.find((s) => String(s.seat_id) === String(seatId));
        setSeat(foundSeat || null);

        // Derive section info from seat data
        if (foundSeat) {
          const sectionSeats = allSeats.filter(
            (s) => String(s.section_id) === String(sectionId || foundSeat.section_id)
          );
          if (sectionSeats.length > 0) {
            setSection({
              section_id: foundSeat.section_id,
              name: foundSeat.section_name || `Section ${foundSeat.section_id}`,
              price: foundSeat.price,
            });
          }
        }
      } catch (err) {
        setError(err.message || 'Failed to load booking details');
      } finally {
        setLoading(false);
      }
    };

    if (eventId && seatId) fetchDetails();
  }, [eventId, seatId, sectionId]);

  // Initiate saga (Review -> Payment)
  const handleReviewConfirm = async (email, phone) => {
    setProcessing(true);
    setProcessingMsg(PROCESSING_MESSAGES[0]);
    setError(null);

    try {
      const data = await api('/api/orchestrator/bookings/initiate', {
        method: 'POST',
        body: JSON.stringify({
          user_id: userId,
          event_id: Number(eventId),
          seat_id: Number(seatId),
          email,
          phone,
        }),
      });

      setSagaData(data);
      setCurrentStep(2);
    } catch (err) {
      setError(err.message || 'Failed to initiate booking');
    } finally {
      setProcessing(false);
      setProcessingMsg('');
    }
  };

  // Confirm booking after Stripe payment
  const handlePaymentSuccess = async (paymentIntent) => {
    setProcessing(true);
    setProcessingMsg(PROCESSING_MESSAGES[2]);
    setError(null);

    try {
      await api('/api/orchestrator/bookings/confirm', {
        method: 'POST',
        body: JSON.stringify({
          saga_id: sagaData.saga_id,
          payment_intent_id: paymentIntent.id,
        }),
      });

      setProcessingMsg(PROCESSING_MESSAGES[3]);
      // Brief delay for UX then show confirmation
      setTimeout(() => {
        setCurrentStep(3);
        setProcessing(false);
        setProcessingMsg('');
      }, 1000);
    } catch (err) {
      setError(err.message || 'Failed to confirm booking');
      setProcessing(false);
      setProcessingMsg('');
    }
  };

  const handlePaymentError = (stripeError) => {
    // Error is displayed by PaymentStep itself; just log
    console.error('Payment error:', stripeError?.message);
  };

  const handleBack = () => {
    navigate(`/events/${eventId}`);
  };

  // Block admin users from accessing the booking page
  if (isAdmin) {
    return (
      <div className="max-w-lg mx-auto text-center py-12 space-y-4">
        <p className="text-yellow-400 font-medium">Admin accounts cannot purchase tickets</p>
        <p className="text-text-secondary text-sm">Switch to a customer account to book seats.</p>
        <button
          onClick={handleBack}
          className="px-6 py-2 bg-accent hover:bg-accent-hover text-white rounded-lg text-sm font-medium transition-colors"
        >
          Back to Event
        </button>
      </div>
    );
  }

  if (loading) {
    return (
      <div className="flex justify-center py-16">
        <Loader2 size={32} className="animate-spin text-accent" />
      </div>
    );
  }

  if (error && !sagaData) {
    return (
      <div className="max-w-lg mx-auto text-center py-12 space-y-4">
        <p className="text-seat-taken">{error}</p>
        <button
          onClick={handleBack}
          className="px-6 py-2 bg-accent hover:bg-accent-hover text-white rounded-lg text-sm font-medium transition-colors"
        >
          Back to Event
        </button>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <StepIndicator steps={STEPS} currentStep={currentStep} />

      {/* Processing overlay */}
      {processing && (
        <div className="fixed inset-0 z-50 bg-bg-primary/80 backdrop-blur-sm flex items-center justify-center">
          <div className="bg-bg-card rounded-xl border border-white/10 p-8 text-center space-y-4">
            <Loader2 size={40} className="animate-spin text-accent mx-auto" />
            <p className="text-text-primary font-medium">{processingMsg}</p>
          </div>
        </div>
      )}

      {/* Error banner (during payment steps) */}
      {error && sagaData && (
        <div className="max-w-lg mx-auto bg-seat-taken/10 border border-seat-taken/30 rounded-lg p-3 text-sm text-seat-taken text-center">
          {error}
        </div>
      )}

      {/* Step content */}
      {currentStep === 1 && (
        <ReviewStep
          event={event}
          seat={seat}
          section={section}
          onConfirm={handleReviewConfirm}
          onBack={handleBack}
        />
      )}

      {currentStep === 2 && sagaData && (
        <PaymentStep
          clientSecret={sagaData.client_secret}
          amount={sagaData.amount}
          expiresAt={sagaData.expires_at}
          onPaymentSuccess={handlePaymentSuccess}
          onPaymentError={handlePaymentError}
        />
      )}

      {currentStep === 3 && sagaData && (
        <ConfirmationStep bookingId={sagaData.booking_id} />
      )}
    </div>
  );
}
