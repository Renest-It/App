// The one place cents become a display string. Nothing else should do this
// math inline — that's how the same off-by-a-decimal bug gets written three
// times (see T0.11's ticket notes).
export function formatPriceCents(cents: number, currency: string): string {  return (cents / 100).toLocaleString("en-US", {
    style: "currency",
    currency: "USD",
  });
}
