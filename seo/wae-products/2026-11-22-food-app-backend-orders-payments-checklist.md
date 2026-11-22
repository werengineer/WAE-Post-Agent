# Piece: Food and mess app backend checklist (orders, payments, webhooks)

**Product tie-in:** Magical Treat Server (backend for the Magical Treat apps). This piece is general engineering guidance. It makes no claim about what Magical Treat Server does. TODO: the team may add one approved sentence about the server where marked.

- **Title tag (58 chars):** Food App Backend Checklist: Orders, Payments, Webhooks
- **Meta description (155 chars):** A plain checklist for building the backend of a food or mess app: data model, order states, safe retries, payment webhooks and what to log.
- **Suggested URL:** /blog/food-app-backend-orders-payments-checklist
- **Schema:** Article + FAQPage (JSON-LD at the end)

## Outline
- H1: Food App Backend Checklist: Orders, Payments and Webhooks
  - H2: What a food or mess app backend has to do
  - H2: Start with a small data model
  - H2: Give every order a clear set of states
  - H2: Make retries safe with idempotency keys
  - H2: Confirm payments from the webhook, not the browser
  - H2: Keep money and menu prices stable after the order
  - H2: Log the things you will need on a bad day
  - H2: Quick checklist
  - H2: FAQ

---

# Food App Backend Checklist: Orders, Payments and Webhooks

A food or mess app looks simple on the phone: pick items, pay, wait. The backend behind it has to handle double taps, lost connections, late payment messages and price changes. This checklist covers the parts that most often go wrong. It is written for developers and small teams building or reviewing a server for a food ordering or mess management app.

## What a food or mess app backend has to do

At minimum the server does five jobs:

1. Know who the user is (login and roles such as customer, staff, admin).
2. Serve the menu.
3. Accept orders and track their status.
4. Take payment and confirm it.
5. Give staff a way to see and update orders.

Everything below supports one of these jobs.

## Start with a small data model

Most food ordering backends use the same core records. Keep them separate:

- **User:** account, role, contact details.
- **Menu item:** name, price, availability, category.
- **Order:** who ordered, when, total, current status.
- **Order line:** one row per item in an order, with the quantity and the price at the time of ordering.
- **Payment:** the amount, the provider's payment ID, and its status.
- **Status history:** one row each time an order changes status.

Add tables later only when a real feature needs them.

## Give every order a clear set of states

Write the allowed states down and allow only the moves you list. A simple example:

`placed` → `paid` → `preparing` → `ready` → `completed`

with `cancelled` possible from the early states. Rules that help:

- Reject impossible moves, for example `completed` back to `preparing`.
- Store each change as a new history row with the time and who made it, instead of only overwriting one column.
- Let only staff or admin roles change status. Check the role on the server, not in the app.

## Make retries safe with idempotency keys

Phones lose signal. A user taps "Pay", the request is sent, the reply never arrives, and the app retries. Without protection the user may get two orders or two charges.

An idempotency key is a stable ID for one logical action. The client sends the same key on every retry of that action, and the server returns the first result instead of doing the work again. Practical points taken from payment provider guidance:

- The key identifies one action, not one network attempt.
- If the same key arrives with different content, reject it with an error.
- If two requests with the same key arrive at the same moment, one waits or gets a retryable error.
- Let the database enforce this with a unique key, rather than checking first and inserting second.

## Confirm payments from the webhook, not the browser

After a customer pays, the payment provider sends your server a webhook (a message saying the payment succeeded or failed). Razorpay's guidance is to fulfil from the webhook because the browser callback can be lost, blocked or forged. Good habits:

- Verify the webhook signature before trusting it.
- Reply quickly with a success code and do the heavy work afterwards.
- Store the provider's event ID and ignore events you have seen before. Providers can send the same event more than once.
- Do not assume the order of events. Handle whichever arrives first.
- Only move an order to `paid` after the webhook (or a server-side check with the provider) confirms it.

## Keep money and menu prices stable after the order

- Copy the item price into the order line when the order is placed. If the menu price changes tomorrow, yesterday's orders must not change.
- Calculate the total on the server. Never trust a total sent by the app.
- Store amounts as whole minor units (for example paise) or as exact decimals, not floating-point numbers.
- Keep refunds as their own records linked to the payment.

## Log the things you will need on a bad day

- A request ID on every API call, returned to the client.
- Order ID and payment ID in every related log line.
- Every webhook received, with its result.
- Failed logins and role-check failures.

Do not log passwords, tokens or full card data.

## Quick checklist

- [ ] Roles checked on the server for every staff or admin action
- [ ] Allowed order status moves written down and enforced
- [ ] Status history stored
- [ ] Idempotency key on order creation and payment start
- [ ] Webhook signature verified
- [ ] Webhook event IDs stored and duplicates ignored
- [ ] Order marked paid only after confirmation from the provider
- [ ] Prices copied into order lines
- [ ] Totals calculated on the server
- [ ] Money stored as exact values
- [ ] Logs carry request, order and payment IDs

For a general API security list, see our [Node and Express API checklist](/blog/secure-node-express-api-checklist) (TODO: confirm live URL once published).

## FAQ

### What tables does a food ordering app backend need?
At least users, menu items, orders, order lines, payments and an order status history. Order lines should store the price at the time of the order, so later menu changes do not alter past orders.

### What is an idempotency key?
It is a stable ID that a client sends with each retry of the same action, such as placing an order. The server uses it to return the first result instead of creating a duplicate order or charge.

### Why confirm payment from a webhook instead of the app?
The app or browser callback can be lost, blocked or forged. A signed webhook comes from the payment provider to your server, so it is a more reliable signal that the payment really happened.

### What should happen if the same webhook arrives twice?
Ignore the repeat. Store each provider event ID and skip any ID you have already processed. Make this check atomic in the database so two copies arriving together cannot both run.

### Should the app send the order total?
No. The server should calculate the total from its own menu prices. The app can show an estimate, but the server's number is the one that is charged.

### What order states does a food app need?
A simple set is placed, paid, preparing, ready, completed and cancelled. Write down which moves are allowed and reject all others.

---

## JSON-LD

```json
{
  "@context": "https://schema.org",
  "@graph": [
    {
      "@type": "Article",
      "headline": "Food App Backend Checklist: Orders, Payments and Webhooks",
      "description": "A plain checklist for building the backend of a food or mess app: data model, order states, safe retries, payment webhooks and what to log.",
      "inLanguage": "en",
      "datePublished": "2026-11-22",
      "author": { "@type": "Organization", "name": "We Are Engineer" },
      "publisher": {
        "@type": "Organization",
        "name": "We Are Engineer",
        "url": "https://weareengineer.com"
      },
      "mainEntityOfPage": "https://weareengineer.com/blog/food-app-backend-orders-payments-checklist"
    },
    {
      "@type": "FAQPage",
      "mainEntity": [
        {
          "@type": "Question",
          "name": "What tables does a food ordering app backend need?",
          "acceptedAnswer": { "@type": "Answer", "text": "At least users, menu items, orders, order lines, payments and an order status history. Order lines should store the price at the time of the order, so later menu changes do not alter past orders." }
        },
        {
          "@type": "Question",
          "name": "What is an idempotency key?",
          "acceptedAnswer": { "@type": "Answer", "text": "It is a stable ID that a client sends with each retry of the same action, such as placing an order. The server uses it to return the first result instead of creating a duplicate order or charge." }
        },
        {
          "@type": "Question",
          "name": "Why confirm payment from a webhook instead of the app?",
          "acceptedAnswer": { "@type": "Answer", "text": "The app or browser callback can be lost, blocked or forged. A signed webhook comes from the payment provider to your server, so it is a more reliable signal that the payment really happened." }
        },
        {
          "@type": "Question",
          "name": "What should happen if the same webhook arrives twice?",
          "acceptedAnswer": { "@type": "Answer", "text": "Ignore the repeat. Store each provider event ID and skip any ID you have already processed. Make this check atomic in the database so two copies arriving together cannot both run." }
        },
        {
          "@type": "Question",
          "name": "Should the app send the order total?",
          "acceptedAnswer": { "@type": "Answer", "text": "No. The server should calculate the total from its own menu prices. The app can show an estimate, but the server's number is the one that is charged." }
        },
        {
          "@type": "Question",
          "name": "What order states does a food app need?",
          "acceptedAnswer": { "@type": "Answer", "text": "A simple set is placed, paid, preparing, ready, completed and cancelled. Write down which moves are allowed and reject all others." }
        }
      ]
    }
  ]
}
```

## Sources used for the facts above
- https://razorpay.com/docs/payments/payment-gateway/s2s-integration/test-s2s/best-practices/retries-and-idempotency (fulfil on webhook; event order not guaranteed)
- https://docs.adyen.com/development-resources/api-idempotency (concurrent same-key requests are retryable)
- https://docs.truelayer.com/docs/idempotency (same key with different payload is an error)
- https://www.cashfree.com/docs/payments/online/webhooks/webhook-indempotency (webhook idempotency)
- https://www.back4app.com/templates/food-delivery-platform (typical entities: user, restaurant, menu, order)
