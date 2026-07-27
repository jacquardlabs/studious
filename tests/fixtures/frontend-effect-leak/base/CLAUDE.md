# CLAUDE.md

React 18 + TypeScript dashboard. Function components and hooks only.

Every effect that opens a subscription, timer, or listener returns a cleanup
function — panels mount and unmount constantly in a session that is never
reloaded, so anything left running accumulates for the life of the tab.
