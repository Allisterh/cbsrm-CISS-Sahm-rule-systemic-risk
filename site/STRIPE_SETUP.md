# Stripe checkout for the Desk tier

The site is a **static** site, so the cleanest, safest Stripe integration is a
**Payment Link** — Stripe hosts the checkout page, **no secret keys ever live in
this repo or in the browser**, and it works on the current Netlify setup with
zero server code. (A server-side option is noted at the bottom if you ever want
embedded/dynamic checkout.)

## Recommended price (set in the site)

**Desk — `from $48,000 / yr` (or $4,000/mo).** Optionally add a one-time
**$15k–$25k onboarding/setup fee**. Rationale: an SF custom build of this system
runs ~$150k–$300k; institutional risk-analytics subscriptions land $36k–$120k/yr
(Bloomberg ≈ $28k/seat). $48k/yr is a credible anchor that leaves headroom for the
"Institution" (custom, $100k+) tier.

## How to turn on checkout (≈5 minutes, in your Stripe dashboard)

1. **Stripe → Product catalog → + Add product.**
   - Name: `CBSRM Desk` · Description: *Hosted CBSRM systemic-risk API, dashboards & data feeds — annual license.*
2. **Add a price:**
   - **Recurring**, **Yearly**, amount **$48,000.00** (USD). *(Optionally add a second monthly price of $4,000.)*
   - Save.
3. **Create a Payment Link** (Stripe → Payment Links → + New, or from the product's "···" menu → Create payment link):
   - Pick the `CBSRM Desk` yearly price.
   - Under options you may enable **"Collect customer's business name / address"** and **"Allow promotion codes."**
   - For invoicing-style buyers, also enable **"Customers can pay with bank transfer / invoice"** if available on your account.
   - **Create** → copy the URL (looks like `https://buy.stripe.com/xxxxxxxx`).
4. **Paste the link into the site:** in `site/index.html`, find the line
   ```js
   var DESK_STRIPE_LINK = "";
   ```
   and put your link between the quotes:
   ```js
   var DESK_STRIPE_LINK = "https://buy.stripe.com/xxxxxxxx";
   ```
   Commit + push → Netlify auto-deploys. The Desk **"Get started"** button now
   reads **"Subscribe → $48k/yr"** and opens Stripe checkout. *(Or send me the
   link and I'll wire + push it for you.)*

That's it — no API keys, no functions, no PCI surface on your side.

## Notes
- **Test first:** create the link in **Test mode**, verify the flow, then redo it
  in **Live mode** and paste the live link.
- **Taxes/VAT:** enable **Stripe Tax** on the product if you need automatic tax.
- **High-ticket reality:** many institutions will still want an invoice/contract —
  keep the **"or book a briefing"** path (the `#contact` email) alongside checkout.

## Optional: server-side Checkout (only if you outgrow Payment Links)
If you later want an embedded/dynamic checkout (custom metadata, seat counts,
proration), add a Netlify Function (`netlify/functions/create-checkout.js`) that
creates a Stripe Checkout Session using `STRIPE_SECRET_KEY` (stored as a **Netlify
environment variable**, never in the repo) + the price ID. Ask and I'll scaffold it.
