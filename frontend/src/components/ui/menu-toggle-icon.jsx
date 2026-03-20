import { cn } from "@/lib/utils";

export function MenuToggleIcon({ isOpen }) {
  return (
    <div className="relative h-5 w-5 flex flex-col justify-center items-center">
      <span
        className={cn(
          "absolute h-0.5 w-4 bg-current transition-all duration-300",
          isOpen ? "translate-y-0 rotate-45" : "-translate-y-1.5"
        )}
      />
      <span
        className={cn(
          "absolute h-0.5 w-4 bg-current transition-all duration-300",
          isOpen ? "opacity-0" : "opacity-100"
        )}
      />
      <span
        className={cn(
          "absolute h-0.5 w-4 bg-current transition-all duration-300",
          isOpen ? "translate-y-0 -rotate-45" : "translate-y-1.5"
        )}
      />
    </div>
  );
}
