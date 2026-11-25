# Piece: API design for a mobile community app

- **Title tag (58 chars):** REST API Design for a Mobile Community App: 8 Rules
- **Meta description (150 chars):** Eight plain rules for a backend API that serves a mobile community app: pagination, auth, errors, retries, uploads and versioning. From the WAE team.
- **URL slug (suggested):** /blog/rest-api-design-mobile-community-app
- **Author / byline:** TODO: name an engineer from the WAE team. Do not publish without a real author.
- **Date published:** TODO (set on publish day)

## Outline
- H1: REST API Design for a Mobile Community App: 8 Rules
- H2: What does a community app need from its backend?
- H2: Rule 1. Name things, not actions
- H2: Rule 2. Use the right HTTP method and status code
- H2: Rule 3. Paginate every list
- H2: Rule 4. Make retries safe
- H2: Rule 5. Check who the user is and what they may do on every request
- H2: Rule 6. Return one error shape
- H2: Rule 7. Keep uploads out of your API server
- H2: Rule 8. Version before you need to
- H2: FAQ

---

# REST API Design for a Mobile Community App: 8 Rules

A community app lets people post, follow, comment and share. The mobile app talks to a backend API for all of it. This guide gives eight rules for that API. They are general engineering practice, not a description of any one product's code. Where a rule comes from a standard, the standard is named.

## What does a community app need from its backend?

Most community apps need the same few things: sign-in, user profiles, posts or items, lists (feeds, search results, comments), and file uploads such as photos. Phones also make this harder than a website. Networks drop, apps stay on old versions for months, and users tap a button twice. Each rule below answers one of these facts.

## Rule 1. Name things, not actions

Use nouns in URLs and let the HTTP method be the verb. `GET /posts/42/comments` reads comments. `POST /posts/42/comments` adds one. Avoid `/getComments` or `/addComment`. This is the style recommended in Microsoft's Azure Architecture Center guide to web API design.

## Rule 2. Use the right HTTP method and status code

Use GET to read, POST to create, PUT or PATCH to change, DELETE to remove. Return `201 Created` after a create, `400` for a bad request, `401` when the caller is not signed in, `403` when signed in but not allowed, `404` when not found, and `429` when the caller sends too many requests. Mobile clients can then react in a standard way.

## Rule 3. Paginate every list

Never return an unbounded list. A feed that grows will slow the app and the server. Return a fixed page size and a way to ask for the next page. For feeds that change often, a cursor (an opaque token for "after this item") avoids showing the same item twice when new posts arrive, which can happen with page numbers.

## Rule 4. Make retries safe

Per RFC 9110, GET, HEAD, OPTIONS, TRACE, PUT and DELETE are idempotent: repeating them has the same effect as sending them once. POST is not. On a weak network the app will retry a "create post" call, and the user may double-tap. Let the client send an idempotency key (a unique ID for the action) with POST requests, and have the server return the first result if it sees the same key again.

## Rule 5. Check who the user is and what they may do on every request

Signing in proves who the caller is. It does not prove they may edit post 42. On each request, check that the caller owns the resource or has the right role. Check this on the server. Never trust a user ID sent in the request body when you can read it from the verified token. For a longer list of protections, see our [secure Node.js and Express API checklist](/blog/secure-node-express-api-checklist) (TODO: confirm this URL once that post is live).

## Rule 6. Return one error shape

Pick one JSON shape for every error, for example a short code, a human message and a field name when the problem is in one field. The mobile app can then show the right message without special cases. Keep messages free of stack traces and internal details.

## Rule 7. Keep uploads out of your API server

Photos and files are large. Many teams let the app upload straight to object storage with a short-lived signed URL that the API issues, then save only the file's address in the database. This keeps the API fast. TODO (optional): add which storage service the team uses, only if engineering approves saying so.

## Rule 8. Version before you need to

Old app versions stay installed. If you change a response in a way that breaks them, they crash. Put a version in the path (`/v1/posts`) or in a header, add fields instead of renaming them, and keep the old version alive until few users remain on the apps that call it. TODO: add the team's real support window only if one exists.

## FAQ

### What is a backend API for a mobile app?
It is a server that the app calls over the internet to sign users in, load data and save changes. The app shows the screens. The backend keeps the data and enforces the rules.

### Should a community app use REST or GraphQL?
Either works. REST is simpler to cache and to learn, and is enough for most community apps. GraphQL helps when screens need many different shapes of data. Choose based on your team's skills and your screens.

### How do I stop the same post being created twice?
Send an idempotency key with each create request. The server stores the key with the result and returns that result if the key arrives again.

### Why paginate an API?
Without pagination, a growing list makes responses bigger and slower. Pages keep responses small and predictable.

### What is the difference between 401 and 403?
401 means the caller is not authenticated (not signed in or the token is bad). 403 means the caller is known but not allowed to do this.

### Where should photo uploads go?
Usually to object storage through a signed URL, not through the API server itself.

## JSON-LD

```json
{
  "@context": "https://schema.org",
  "@graph": [
    {
      "@type": "Article",
      "headline": "REST API Design for a Mobile Community App: 8 Rules",
      "description": "Eight plain rules for a backend API that serves a mobile community app: pagination, auth, errors, retries, uploads and versioning.",
      "author": { "@type": "Person", "name": "TODO: author name" },
      "publisher": {
        "@type": "Organization",
        "name": "We Are Engineer",
        "url": "https://weareengineer.com"
      },
      "datePublished": "TODO: YYYY-MM-DD",
      "mainEntityOfPage": "https://weareengineer.com/blog/rest-api-design-mobile-community-app"
    },
    {
      "@type": "FAQPage",
      "mainEntity": [
        {"@type": "Question", "name": "What is a backend API for a mobile app?", "acceptedAnswer": {"@type": "Answer", "text": "It is a server that the app calls over the internet to sign users in, load data and save changes. The app shows the screens. The backend keeps the data and enforces the rules."}},
        {"@type": "Question", "name": "Should a community app use REST or GraphQL?", "acceptedAnswer": {"@type": "Answer", "text": "Either works. REST is simpler to cache and to learn, and is enough for most community apps. GraphQL helps when screens need many different shapes of data."}},
        {"@type": "Question", "name": "How do I stop the same post being created twice?", "acceptedAnswer": {"@type": "Answer", "text": "Send an idempotency key with each create request. The server stores the key with the result and returns that result if the key arrives again."}},
        {"@type": "Question", "name": "Why paginate an API?", "acceptedAnswer": {"@type": "Answer", "text": "Without pagination, a growing list makes responses bigger and slower. Pages keep responses small and predictable."}},
        {"@type": "Question", "name": "What is the difference between 401 and 403?", "acceptedAnswer": {"@type": "Answer", "text": "401 means the caller is not authenticated. 403 means the caller is known but not allowed to do this."}},
        {"@type": "Question", "name": "Where should photo uploads go?", "acceptedAnswer": {"@type": "Answer", "text": "Usually to object storage through a signed URL, not through the API server itself."}}
      ]
    }
  ]
}
```

## Sources
- https://learn.microsoft.com/en-us/azure/architecture/best-practices/api-design
- https://www.rfc-editor.org/rfc/rfc9110.html (Section 9.2, safe and idempotent methods; the method list was recalled from memory because the fetch did not reach that section. TODO: verify before publishing.)
