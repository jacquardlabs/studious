import { useEffect, useState } from "react";

import { priceFeed } from "../lib/priceFeed";

type Props = { symbol: string };

export function LivePrices({ symbol }: Props) {
  const [price, setPrice] = useState<number | null>(null);

  useEffect(() => {
    const subscription = priceFeed.subscribe(symbol, setPrice);
    return () => subscription.unsubscribe();
  }, [symbol]);

  if (price === null) {
    return <p aria-live="polite">Loading {symbol}…</p>;
  }

  return (
    <p aria-live="polite">
      {symbol}: {price.toFixed(2)}
    </p>
  );
}
