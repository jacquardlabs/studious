# reportkit

Plain-text operational reports for on-call engineers.

## Usage

```python
from app.report import render_summary

render_summary(rows)
```

## Public API

### `render_summary(rows, date_format="iso")`

Renders `rows` as a plain-text summary.

`date_format` selects the date style. It defaults to `"iso"` (`2026-07-26`).
Pass `date_format="us"` for `07/26/2026`.
