# 0002 — No Payments; Transactions Are an In-Person Handoff

## Status

Accepted

## Context

ReNest connects a student leaving campus with an item to sell to a student
who wants to buy it. At some point that transaction needs to actually
happen — money changes hands and the item changes hands. We need to decide
whether the platform processes that payment itself (integrating a payments
provider, holding funds, mediating disputes) or stays out of the money
entirely and leaves the exchange to the two parties.

## Decision

ReNest does not process payments. The "Sold" step in the Post → Find →
Contact → Sold workflow records that a listing's status changed to sold; it
does not move any money. Buyer and seller arrange price, payment method
(typically cash), and a meeting place themselves, entirely outside the
platform. ReNest's role ends at connecting the two parties and letting them
mark the outcome.

## Alternatives Considered

**Integrated payments (e.g., Stripe Connect or similar).** Rejected for the
MVP. Processing payments on behalf of users means the platform becomes a
party to the transaction, not just a directory: it has to handle
chargebacks and refunds, decide what happens when a buyer claims an item
never arrived or wasn't as described, and carry PCI compliance obligations
for handling card data. That is a materially different product — and a
materially different liability profile — than a campus listings board, and
none of the MVP's core value (finding items, contacting sellers) depends on
it. For a peer-to-peer exchange between two people on the same campus who
can simply meet in person, integrated payments solve a problem ReNest
doesn't have.

## Consequences

- ReNest has no PCI scope: it never touches card numbers or other payment
  instrument data, because it never touches payment data at all.
- ReNest has no dispute-handling responsibility — if a buyer and seller
  disagree about an in-person exchange, that is between them, not something
  the platform mediates or refunds.
- ReNest carries no liability for failed trades (a no-show, an item not as
  described, etc.); marking a listing "sold" is a status update, not a
  transaction record or a receipt.
- Because there is no payment record, ReNest also has no transaction
  history, receipts, or seller ratings derived from payment confirmation —
  any future trust/safety feature would need a different signal than
  "payment succeeded."
