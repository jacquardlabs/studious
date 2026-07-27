# Design

## Surfaces

| Surface | Framework / tech | Entry point |
|---------|-------------------|-------------|
| web | React 18 + TypeScript, Vite | `src/components/LivePrices.tsx` |

Single-page dashboard. Long-lived sessions are the norm: a trader mounts and
unmounts instrument panels many times without a full page reload.
