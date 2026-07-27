type Listener = (price: number) => void;

export type Subscription = { unsubscribe: () => void };

/** Thin wrapper over the desk's price socket. */
export const priceFeed = {
  subscribe(symbol: string, onPrice: Listener): Subscription {
    const socket = new WebSocket(`wss://feed.internal/prices/${symbol}`);
    socket.onmessage = (event) => onPrice(Number(event.data));
    return { unsubscribe: () => socket.close() };
  },
};
