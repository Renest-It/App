# Feed states (E4.0 / SCRUM-49)

The design reference for the paginated home feed's states. E4.3 (SCRUM-52) builds them. There was intentionally no further design time: what's below plus the existing E2.0/E3.0 Figma designs is the reference.

## What was delivered

**Figma** ([ReNest Figma Layout](https://www.figma.com/design/A6AfPG7rrC3e2G8cc1SGxa/ReNest-Figma-Layout)), on the "E2.0 — Listing Mockups" page, below the existing frames:

- [E4.0 — Feed states · Components](https://www.figma.com/design/A6AfPG7rrC3e2G8cc1SGxa/ReNest-Figma-Layout?node-id=124-2):
  - `FeedCard` (Viewport=Mobile/Desktop): an instance of the E3.0 `ListingCard` (Status=Active) with the status badge, activity line and management actions hidden.
  - `FeedCard skeleton` (Viewport=Mobile/Desktop): the same outer size as `FeedCard`.
  - `Button / Secondary` (State=Default/Hover/Focus, with a `Label` text property): used for "Load more" and "Retry".
  - `Feed footer` (State=Load more / Loading more / Error / End of feed × Viewport): the single bottom slot from decision 1. It's 128px tall on mobile and 80px on desktop in every state.
- [E4.0 — Feed states · Screens](https://www.figma.com/design/A6AfPG7rrC3e2G8cc1SGxa/ReNest-Figma-Layout?node-id=125-30), each row with mobile, desktop and an annotation:
  1. First load: 8 skeleton cards.
  2. Empty feed, plus a dashed placeholder for E5's "no results for this filter".
  3. A full page of 20 cards, then "Load more".

**Not drawn as full screens** (built in E4.3 from the components): loading more, the load-more error, "Load more" in its focus state, and end of feed after a short last page. Each is the row 3 screen with the matching `Feed footer` state under the grid. While a page is loading or has failed, the loaded cards stay where they are.

## Final wording

| State | Text |
|---|---|
| Load more button | "Load more" |
| Loading more | "Loading more…" |
| Load-more error | "Couldn't load more listings." + button "Retry" |
| End of feed | "You've seen everything — check back soon for new listings." |
| Empty feed (unchanged) | "No listings yet" / "Be the first to sell something — tap Sell to get started." |
| First-load error (unchanged) | "Couldn't load listings" / "Check your connection and try again." + "Retry" |

## Notes for E4.3 and later tickets

- **The Figma card and the coded card don't match, and this predates E4.** Figma's card (E2.0 and E3.0) has a 1px `border` stroke, `radius-md`, a white surface and 12px padding around the text. `ListingCard.tsx` has no border or padding. The Figma grid gap is 16px both ways, while `ListPage`'s `GRID` uses `gap-x-3 gap-y-5` (12px / 20px). E4.3 shouldn't restyle the card just for pagination. Keep the current card and gaps, and make the skeleton match whatever the card actually renders (decision 7 below). Whether to align the code with Figma is a separate decision for the design owner.
- **The Figma mobile frames are 390px wide**, matching E3.0. E4.4 still checks for no sideways scroll at 360px on a real phone.
- **Code mapping:** `Feed footer` maps to a small component under the grid that switches on `useFeed()`'s state: has more and idle → `Button variant="secondary"`, loading → `LoaderCircle` + text, error → `Alert` + secondary Retry, `next_cursor === null` → end-of-feed line. Focus uses `Button`'s existing `focus-visible` ring, so it needs no new styles.
- **Figma plan limits** (Starter): 3 pages per file, all of them already in use, and a cap on MCP tool calls, which this ticket hit. Future design work goes in sections on existing pages, or the plan needs upgrading.
- **The Figma file has no variables or styles.** E2.0, E3.0 and E4.0 all use raw hex values that equal the E1.1 tokens. If the team ever wants Figma tokens linked to `@theme`, that's its own ticket.

## Design decisions

**1. The bottom of the feed is one slot that shows exactly one state at a time.**
Below the last row of cards there's a single area. It shows one of four things: the "Load more" button (more pages exist, nothing loading), the loading-more indicator (a request is in flight), the inline error (the last request failed), or the end-of-feed message (`next_cursor` is `null`). The slot keeps roughly the same height (about the 48px button height plus vertical padding) in every state, so swapping states doesn't shift the cards above.
*Alternative considered:* separate areas that each appear and disappear independently. Rejected because two of them could show at once, such as an error above a Load more button, and E4.3 would have to work out the precedence itself.

**2. While a page is loading, the indicator replaces the button: a spinner and "Loading more…" in muted text, not more skeleton cards.**
It reuses the same `LoaderCircle` spinner as `Button`'s `loading` state, in `text-text-muted` at `text-sm`, centered. Auto-load and a button press both show this same indicator, because both go through `useFeed()`.
*Alternatives considered:*
- Appending a row of skeleton cards. Rejected: SCRUM-49 says the indicator must look different from the first-load skeleton, and skeleton rows below real cards look like content that's about to appear in that exact spot.
- Keeping the button and putting it in its `loading` state. Rejected: when the next page auto-loads, a spinning button the user never pressed suggests they did something.

**3. "Load more" uses the `secondary` variant, at its natural width and centered.**
It uses `w-auto min-w-40`, the same sizing as the existing Retry button. On this screen, `primary` (filled accent) is for the main action, which is Sell. "Load more" is a fallback for people who can't, or don't, trigger auto-load, so it shouldn't compete with Sell. The frames also show its focus state (`outline-accent`, the existing focus ring), because E4.4 checks that the focus outline is visible.
*Alternative considered:* `primary`. Rejected because a full-accent button at the bottom of every page of the feed is too loud for a secondary path.

**4. The end-of-feed state is one quiet line of text, not a `CenterState`.**
It's centered `text-sm text-text-muted`, with a short `border-border` rule on each side, and reads "You've seen everything — check back soon for new listings." It sits in the bottom slot, below the cards.
*Alternative considered:* a `CenterState` with an icon. Rejected because an icon and heading under a full grid read like an empty or error state. Reaching the end is normal and shouldn't draw attention.

**5. The empty feed keeps the existing "No listings yet" `CenterState`.**
The text stays as it is in `ListPage` today: "No listings yet" / "Be the first to sell something — tap Sell to get started." It has no bottom slot and no Load more button. It's already written for "nothing on the platform at all". E5's "no results for this filter" will have its own wording and will point to clearing the filter, not to Sell. The frame shows the two side by side, with a note that E5 owns the second one, so they don't get merged later.

**6. The load-more error is an inline `Alert` (error variant) with a Retry button, in the bottom slot.**
Cards that already loaded stay visible above it. The `Alert` reads "Couldn't load more listings." It sits next to, or above, a `secondary` Retry button: next to it on desktop, above it on mobile. Retry calls the same `useFeed()` fetch again. This keeps the whole-page danger `CenterState` for a failed first load only.
*Alternative considered:* a toast. Rejected because the app has no toast component, which would be new UI, and a toast disappears while the retry needs to stay where the user is looking.

**7. The first-load skeleton is 8 cards with the same outer size as a feed card.**
Eight cards fill the first screen at every breakpoint (4 rows on mobile, 2 on desktop). Rendering all 20 of the first page would only add placeholders below the fold. Each skeleton has a photo block plus a title bar and a price/category row, `animate-pulse` in code. What matters is that each skeleton is exactly the size of the card that replaces it. In Figma that's the bordered card (171×204 mobile, 266×276 desktop). In code it's whatever `ListingCard` renders, so if E4.3 changes the card, the skeleton has to change with it.

**8. No new tokens.**
Every value used already exists: `surface`, `border`, `text`, `text-muted`, `accent`, `accent-soft`, `success`, the `danger-*` set, `radius-md` / `radius-sm`, and `text-sm` / `text-body`. **New tokens: none.**
