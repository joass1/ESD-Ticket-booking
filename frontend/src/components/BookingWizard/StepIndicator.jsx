import { Check } from 'lucide-react';

const STEPS = ['Select Seat', 'Review', 'Payment', 'Confirmation'];

export default function StepIndicator({ steps = STEPS, currentStep = 0 }) {
  return (
    <div className="flex items-center justify-center gap-0 w-full max-w-2xl mx-auto mb-8">
      {steps.map((label, i) => {
        const isCompleted = i < currentStep;
        const isCurrent = i === currentStep;

        return (
          <div key={label} className="flex items-center flex-1 last:flex-none">
            {/* Step circle + label */}
            <div className="flex flex-col items-center">
              <div
                className={`flex items-center justify-center rounded-full font-bold text-sm transition-all ${
                  isCompleted
                    ? 'w-9 h-9 bg-accent text-white'
                    : isCurrent
                      ? 'w-10 h-10 bg-accent text-white ring-2 ring-accent/40 ring-offset-2 ring-offset-bg-primary'
                      : 'w-9 h-9 bg-white/10 text-text-secondary'
                }`}
              >
                {isCompleted ? <Check size={16} /> : i + 1}
              </div>
              <span
                className={`mt-2 text-xs whitespace-nowrap ${
                  isCurrent
                    ? 'text-accent font-semibold'
                    : isCompleted
                      ? 'text-text-primary'
                      : 'text-text-secondary'
                }`}
              >
                {label}
              </span>
            </div>

            {/* Connector line */}
            {i < steps.length - 1 && (
              <div
                className={`flex-1 h-0.5 mx-2 mt-[-1.25rem] ${
                  i < currentStep ? 'bg-accent' : 'bg-white/10'
                }`}
              />
            )}
          </div>
        );
      })}
    </div>
  );
}
