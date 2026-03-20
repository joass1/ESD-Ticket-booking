import { useState, useEffect } from "react";

export function useScroll(threshold = 0) {
  const [scrollState, setScrollState] = useState({
    scrolled: false,
    scrollDirection: "down",
    scrollY: 0,
  });

  useEffect(() => {
    let lastScrollY = window.scrollY;

    const handleScroll = () => {
      const currentScrollY = window.scrollY;
      setScrollState({
        scrolled: currentScrollY > threshold,
        scrollDirection: currentScrollY > lastScrollY ? "down" : "up",
        scrollY: currentScrollY,
      });
      lastScrollY = currentScrollY;
    };

    window.addEventListener("scroll", handleScroll, { passive: true });
    handleScroll();

    return () => window.removeEventListener("scroll", handleScroll);
  }, [threshold]);

  return scrollState;
}
