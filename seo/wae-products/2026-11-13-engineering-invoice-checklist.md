# Piece: Engineering project invoicing guide (for the WAE Billing System)

**Status:** ready to publish after the TODOs are filled (WAE Billing System features and public URL are not confirmed online).
**Suggested URL:** `https://weareengineer.com/blog/how-to-invoice-engineering-projects`
**Title tag (58 chars):** How to Invoice Engineering Projects: A Simple Checklist
**Meta description (152 chars):** Learn how to bill engineering clients: pick a billing model, write a clear invoice, set payment terms and follow up. Includes a checklist and FAQ.

## Outline
- H1: How to Invoice Engineering Projects: A Simple Checklist
  - H2: Short answer
  - H2: Step 1: Choose a billing model
  - H2: Step 2: Agree the payment terms before work starts
  - H2: Step 3: Put the right details on every invoice
  - H2: Step 4: Match each invoice to the work done
  - H2: Step 5: Send, track and follow up
  - H2: Common invoicing mistakes
  - H2: Where the WAE Billing System fits
  - H2: Frequently asked questions

---

# How to Invoice Engineering Projects: A Simple Checklist

## Short answer
To invoice an engineering project, agree on a billing model (hourly, fixed fee, milestone or percent-complete), write the payment terms into the contract, send an invoice that shows who is billing whom and for what, tie each invoice to work that was actually delivered, and track it until it is paid.

## Step 1: Choose a billing model
Engineering work is often billed in more than one way on the same project. Common models:

- **Hourly:** the client pays for time worked, at agreed rates.
- **Fixed fee:** one price for a defined scope.
- **Milestone:** the fixed fee is split into parts, each billed when a stage is done.
- **Percent-complete:** each invoice bills the share of the work finished so far.
- **Reimbursable costs:** travel, materials or third-party costs billed on top, as agreed.

Write down which model applies to which phase. Mixed projects are where most billing confusion starts.

## Step 2: Agree the payment terms before work starts
Put these in the contract or proposal, not in an email after the fact:

- When invoices are sent (for example, at each milestone or at month end)
- How many days the client has to pay
- Accepted payment methods
- What happens with late payment
- How scope changes are priced and approved

## Step 3: Put the right details on every invoice
A clear invoice gets paid faster because the client's accounts team does not have to ask questions. Include:

1. A unique invoice number
2. The invoice date and the due date
3. Your legal business name, address and contact details
4. The client's legal name and address
5. A description of the work, matched to the contract line or milestone
6. Quantity and rate, or the fixed amount
7. Taxes, shown as a separate line
8. The total due and how to pay

**India:** tax invoices must carry specific particulars under Rule 46 of the CGST Rules, and requirements such as tax codes and e-invoicing depend on your turnover and registration. Sources we checked disagreed on thresholds, so check the current rules on the official GST portal or with your accountant. (TODO: have a qualified accountant review this section before publishing.)

## Step 4: Match each invoice to the work done
Do not bill ahead of delivery without the client agreeing to it. For each invoice, keep a record of:

- The milestone, phase or time entries it covers
- Any approval or sign-off from the client
- Which earlier invoices it follows, so totals never exceed the contract value

## Step 5: Send, track and follow up
- Send the invoice as soon as the milestone is accepted.
- Keep a list of invoices by status: draft, sent, paid, overdue.
- Follow up on the day an invoice becomes overdue, politely and in writing.
- Record each payment against the right invoice.

## Common invoicing mistakes
- Billing without a purchase order or approval the client requires
- Vague descriptions such as "Services rendered"
- Mixing hourly and fixed-fee work on one line
- Forgetting reimbursable costs, then billing them months later
- Having no single place to see what is paid and what is overdue

## Where the WAE Billing System fits
The WAE Billing System is the billing and invoicing system of We Are Engineer (Sumus Engineer Private Limited, Pune, India). It is part of the WAE platform ecosystem alongside WAE Academy, WAE Social, WAE Projects and others.

TODO (needed from the product owner before this section is published): the list of real features (for example invoice creation, payment tracking, tax support), who it is for (internal use or clients), its public URL, and a screenshot. Do not publish feature claims until these are confirmed.

## Frequently asked questions

### What is the best way to bill an engineering client?
It depends on how well the scope is defined. Fixed or milestone billing suits a clear scope. Hourly suits uncertain scope. Many projects use a mix, so state the model for each phase in the contract.

### Should I invoice monthly or per milestone?
Use whichever the contract says. Milestone billing ties payment to delivered results. Monthly billing suits long, ongoing work. Choose it at the start and keep to it.

### What should an invoice include?
A unique number, dates, both parties' legal details, a clear description of the work, amounts, taxes, the total and payment instructions.

### What is percent-complete billing?
Each invoice bills the share of a fixed-fee phase that has been completed so far. It needs a clear way to measure progress that both sides accept.

### How do I get paid faster?
Send invoices promptly, make them easy to match to the contract, state the due date clearly, and follow up the day a payment is late.

### Do I need billing software?
Spreadsheets work for a few invoices. Software helps when you have several projects, mixed billing models or need to see overdue invoices at a glance.

## JSON-LD (Article + FAQPage)
```json
{
  "@context": "https://schema.org",
  "@graph": [
    {
      "@type": "Article",
      "headline": "How to Invoice Engineering Projects: A Simple Checklist",
      "description": "Learn how to bill engineering clients: pick a billing model, write a clear invoice, set payment terms and follow up.",
      "datePublished": "2026-11-13",
      "author": { "@type": "Organization", "name": "We Are Engineer", "url": "https://weareengineer.com" },
      "publisher": { "@type": "Organization", "name": "Sumus Engineer Private Limited", "url": "https://weareengineer.com" },
      "mainEntityOfPage": "https://weareengineer.com/blog/how-to-invoice-engineering-projects"
    },
    {
      "@type": "FAQPage",
      "mainEntity": [
        {"@type": "Question", "name": "What is the best way to bill an engineering client?", "acceptedAnswer": {"@type": "Answer", "text": "It depends on how well the scope is defined. Fixed or milestone billing suits a clear scope. Hourly suits uncertain scope. Many projects use a mix, so state the model for each phase in the contract."}},
        {"@type": "Question", "name": "Should I invoice monthly or per milestone?", "acceptedAnswer": {"@type": "Answer", "text": "Use whichever the contract says. Milestone billing ties payment to delivered results. Monthly billing suits long, ongoing work."}},
        {"@type": "Question", "name": "What should an invoice include?", "acceptedAnswer": {"@type": "Answer", "text": "A unique number, dates, both parties' legal details, a clear description of the work, amounts, taxes, the total and payment instructions."}},
        {"@type": "Question", "name": "What is percent-complete billing?", "acceptedAnswer": {"@type": "Answer", "text": "Each invoice bills the share of a fixed-fee phase that has been completed so far. It needs a clear way to measure progress that both sides accept."}},
        {"@type": "Question", "name": "How do I get paid faster?", "acceptedAnswer": {"@type": "Answer", "text": "Send invoices promptly, make them easy to match to the contract, state the due date clearly, and follow up the day a payment is late."}},
        {"@type": "Question", "name": "Do I need billing software?", "acceptedAnswer": {"@type": "Answer", "text": "Spreadsheets work for a few invoices. Software helps when you have several projects, mixed billing models or need to see overdue invoices at a glance."}}
      ]
    }
  ]
}
```
