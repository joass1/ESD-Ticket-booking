import { useState } from 'react';
import { Elements, CardElement, useStripe, useElements } from '@stripe/react-stripe-js';
import { loadStripe } from '@stripe/stripe-js';
import { Clock, Loader2 } from 'lucide-react';
import { Link } from 'react-router-dom';
import useCountdown from '../../hooks/useCountdown.js';

const stripePromise = loadStripe(
  import.meta.env.VITE_STRIPE_PK || 'pk_test_placeholder'
);

const CARD_STYLE = {
  base: {
    color: '#e5e5e5',
    fontFamily: 'system-ui, sans-serif',
    fontSize: '16px',
    '::placeholder': { color: '#a3a3a3' },
  },
  invalid: { color: '#ef4444' },
};

function PaymentForm({ clientSecret, amount, expiresAt, onPaymentSuccess, onPaymentError }) {
  const stripe = useStripe();
  const elements = useElements();
  const [processing, setProcessing] = useState(false);
  const [error, setError] = useState(null);
  const { formatted, expired } = useCountdown(expiresAt);

  const handleSubmit = async (e) => {
    e.preventDefault();
    if (!stripe || !elements || processing || expired) return;

    setProcessing(true);
    setError(null);

    try {
      const { error: stripeError, paymentIntent } = await stripe.confirmCardPayment(
        clientSecret,
        { payment_method: { card: elements.getElement(CardElement) } }
      );

      if (stripeError) {
        setError(stripeError.message);
        onPaymentError?.(stripeError);
      } else if (paymentIntent.status === 'succeeded') {
        onPaymentSuccess(paymentIntent);
      }
    } catch (err) {
      setError(err.message || 'Payment failed');
      onPaymentError?.(err);
    } finally {
      setProcessing(false);
    }
  };

  return (
    <form onSubmit={handleSubmit} className="space-y-6 max-w-lg mx-auto">
      {/* Countdown timer */}
      <div className="flex items-center justify-center gap-2 text-center">
        <Clock size={18} className={expired ? 'text-seat-taken' : 'text-accent'} />
        <span
          className={`text-2xl font-mono font-bold ${expired ? 'text-seat-taken' : 'text-accent'}`}
        >
          {formatted}
        </span>
        <span className="text-sm text-text-secondary">
          {expired ? 'Payment window expired' : 'remaining'}
        </span>
      </div>

      {expired ? (
        <div className="bg-bg-card rounded-xl border border-seat-taken/30 p-6 text-center space-y-4">
          <p className="text-seat-taken font-medium">Time expired</p>
          <p className="text-text-secondary text-sm">
            Your seat reservation has been released. Please try booking again.
          </p>
          <Link
            to="/"
            className="inline-block px-6 py-2 bg-accent hover:bg-accent-hover text-white rounded-lg text-sm font-medium transition-colors"
          >
            Return to Events
          </Link>
        </div>
      ) : (
        <>
          <div className="bg-bg-card rounded-xl border border-white/10 p-6 space-y-4">
            <h3 className="text-sm font-medium text-text-secondary">Card Details</h3>
            <div className="p-4 bg-bg-primary rounded-lg border border-white/10">
              <CardElement options={{ style: CARD_STYLE }} />
            </div>
          </div>

          {error && (
            <div className="bg-seat-taken/10 border border-seat-taken/30 rounded-lg p-3 text-sm text-seat-taken">
              {error}
            </div>
          )}

          <button
            type="submit"
            disabled={!stripe || processing}
            className="w-full py-3 bg-accent hover:bg-accent-hover disabled:opacity-50 disabled:cursor-not-allowed text-white rounded-lg font-medium transition-colors flex items-center justify-center gap-2"
          >
            {processing ? (
              <>
                <Loader2 size={18} className="animate-spin" />
                Processing...
              </>
            ) : (
              `Pay $${Number(amount).toFixed(2)}`
            )}
          </button>
        </>
      )}
    </form>
  );
}

export default function PaymentStep({ clientSecret, amount, expiresAt, onPaymentSuccess, onPaymentError }) {
  if (!clientSecret) return null;

  return (
    <Elements stripe={stripePromise} options={{ clientSecret }}>
      <PaymentForm
        clientSecret={clientSecret}
        amount={amount}
        expiresAt={expiresAt}
        onPaymentSuccess={onPaymentSuccess}
        onPaymentError={onPaymentError}
      />
    </Elements>
  );
}
