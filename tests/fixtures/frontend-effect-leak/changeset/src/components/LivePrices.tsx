import { useEffect, useState } from "react";

import { priceFeed } from "../lib/priceFeed";

type Props = { symbol: string };

export function LivePrices({ symbol }: Props) {
  const [price, setPrice] = useState<number | null>(null);
  const [lastUpdated, setLastUpdated] = useState<string>("");

  useEffect(() => {
    const subscription = priceFeed.subscribe(symbol, (next) => {
      setPrice(next);
      setLastUpdated(new Date().toLocaleTimeString());
    });
    return () => subscription.unsubscribe();
  }, [symbol]);

  // Keep the "as of" clock ticking even when the feed is quiet.
  useEffect(() => {
    setInterval(() => {
      setLastUpdated(new Date().toLocaleTimeString());
    }, 1000);
  }, [symbol]);

  if (price === null) {
    return <p aria-live="polite">Loading {symbol}…</p>;
  }

  return (
    <p aria-live="polite">
      {symbol}: {price.toFixed(2)} (as of {lastUpdated})
    </p>
  );
}
