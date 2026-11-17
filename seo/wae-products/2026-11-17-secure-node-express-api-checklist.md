# Piece: Secure Node.js and Express API checklist

**Title tag:** Secure a Node.js Express API: 10-Point Checklist | WAE
**Meta description:** A plain checklist to secure a Node.js Express API: HTTPS, Helmet, input checks, JWT rules, rate limits, CORS and safe errors. Based on Express and OWASP guidance.
**URL slug:** /blog/secure-node-express-api-checklist
**Author/Publisher:** We Are Engineer (Sumus Engineer Private Limited)

## Outline
- H1: How to Secure a Node.js Express API: A 10-Point Checklist
- H2: What a backend API server does
- H2: The checklist
  - H3: 1. Use a supported Express version
  - H3: 2. Serve only HTTPS
  - H3: 3. Treat all input as untrusted
  - H3: 4. Add Helmet
  - H3: 5. Check tokens the right way (JWT)
  - H3: 6. Check access on every route
  - H3: 7. Limit login attempts and request rates
  - H3: 8. Set CORS to named origins
  - H3: 9. Return safe errors and keep logs
  - H3: 10. Keep dependencies clean
- H2: How to use this list in a review
- H2: FAQ

---

# How to Secure a Node.js Express API: A 10-Point Checklist

An API server is the part of an app that users never see. The mobile app or website sends it requests, and it checks who is asking, reads or writes data, and sends an answer back. If it is weak, every app that depends on it is weak. This checklist covers ten checks you can run on an Express API today. It follows the official Express security guide and the OWASP REST Security Cheat Sheet.

## What a backend API server does

A backend API server runs on a server, not on the user's phone or browser. The app sends an HTTP request. The server checks the login, applies the business rules, talks to the database, and returns a response. Not every app needs one, but you usually do once an app stores data, logs people in, or shows different data to different users.

## The checklist

### 1. Use a supported Express version
Express 2.x and 3.x are no longer maintained and their security problems will not be fixed. Run Express 4.x or 5.x, and keep it current.

### 2. Serve only HTTPS
TLS stops people from reading or changing traffic on the way. OWASP says REST APIs should expose only HTTPS endpoints. The Express guide suggests handling TLS in a reverse proxy such as Nginx, and notes that Let's Encrypt gives free certificates.

### 3. Treat all input as untrusted
Check length, range, format and type of every value. Use parameterized queries for SQL. Set a request size limit (answer 413 when it is exceeded). Require a supported `Content-Type` on requests with a body (answer 415 otherwise). Check the target host before any `res.redirect` so your API is not an open redirect.

### 4. Add Helmet
Helmet sets security headers such as `Content-Security-Policy`, `Strict-Transport-Security`, `X-Content-Type-Options` and `X-Frame-Options`, and removes `X-Powered-By`.

```js
const helmet = require('helmet');
app.use(helmet());
```

### 5. Check tokens the right way (JWT)
If you use JSON Web Tokens, follow OWASP:
- Require a signature or MAC, and reject unsecured `alg: none` tokens.
- Do not let the token header choose the verification algorithm.
- Validate at least `iss`, `aud` and `exp`.
- Keep passwords, tokens and API keys out of URLs. Send them in headers or the body.

### 6. Check access on every route
Enforce access control on every endpoint that is not public. Use an allowlist of HTTP methods and answer 405 for others. Check permission per method and per record, not only per login. Use 401 when the caller is not signed in and 403 when they are signed in but not allowed.

### 7. Limit login attempts and request rates
Block repeated failed logins by username and by IP address. The Express guide points to the `rate-limiter-flexible` package for this. Answer 429 when a limit is passed. A common pattern is one global limit plus a stricter one on login routes. If you run more than one server, keep the counters in a shared store such as Redis, so each server sees the same counts.

### 8. Set CORS to named origins
If browsers from other sites do not need to call your API, turn CORS off. If they do, allow only the exact origins you need.

### 9. Return safe errors and keep logs
Send generic error messages. Never send stack traces or internal details. Log security events, such as token failures, and clean the logged data so users cannot inject fake log lines.

### 10. Keep dependencies clean
Run `npm audit` on a schedule and read the OWASP Top Ten. Tools such as Snyk or the GitHub Advisory Database can add more checks.

## How to use this list in a review
Take one route at a time and ask: is it HTTPS only, is the input checked, who may call it, what happens on the tenth failed login, and what does the error say? Write the answers in the pull request. A route that cannot answer all five is not ready.

## FAQ

### What is a backend API server?
It is the server-side program that an app calls over HTTP. It checks logins, applies business rules, reads and writes the database, and returns data to the app.

### What is the first thing to secure in an Express API?
Serve it over HTTPS only and run a supported Express version. Then add input checks and access control on every route.

### Does Helmet make an Express API secure by itself?
No. Helmet sets security headers. You still need input checks, access control, rate limits and safe error handling.

### How do I stop brute-force logins on an Express API?
Limit failed attempts per username and per IP address, and answer 429 when the limit is passed. Use a shared store like Redis if you run several servers.

### Should I turn on CORS for my API?
Only if browsers on other sites need to call it. Then allow the specific origins, not every origin.

### Which sources does this checklist follow?
The Express production security guide and the OWASP REST Security Cheat Sheet.

---

**Sources:** https://expressjs.com/en/advanced/best-practice-security.html , https://cheatsheetseries.owasp.org/cheatsheets/REST_Security_Cheat_Sheet.html

**TODO before publishing:** the team should read it, add the author's name and real publish date, and decide if a short "how our own servers handle this" note may be added (needs facts approved by the engineering team; none are invented here).

## JSON-LD

```json
{
  "@context": "https://schema.org",
  "@graph": [
    {
      "@type": "Article",
      "headline": "How to Secure a Node.js Express API: A 10-Point Checklist",
      "description": "A plain checklist to secure a Node.js Express API: HTTPS, Helmet, input checks, JWT rules, rate limits, CORS and safe errors.",
      "datePublished": "2026-11-17",
      "author": {"@type": "Organization", "name": "We Are Engineer"},
      "publisher": {"@type": "Organization", "name": "We Are Engineer", "legalName": "Sumus Engineer Private Limited", "url": "https://weareengineer.com"},
      "mainEntityOfPage": "https://weareengineer.com/blog/secure-node-express-api-checklist"
    },
    {
      "@type": "FAQPage",
      "mainEntity": [
        {"@type": "Question", "name": "What is a backend API server?", "acceptedAnswer": {"@type": "Answer", "text": "It is the server-side program that an app calls over HTTP. It checks logins, applies business rules, reads and writes the database, and returns data to the app."}},
        {"@type": "Question", "name": "What is the first thing to secure in an Express API?", "acceptedAnswer": {"@type": "Answer", "text": "Serve it over HTTPS only and run a supported Express version. Then add input checks and access control on every route."}},
        {"@type": "Question", "name": "Does Helmet make an Express API secure by itself?", "acceptedAnswer": {"@type": "Answer", "text": "No. Helmet sets security headers. You still need input checks, access control, rate limits and safe error handling."}},
        {"@type": "Question", "name": "How do I stop brute-force logins on an Express API?", "acceptedAnswer": {"@type": "Answer", "text": "Limit failed attempts per username and per IP address, and answer 429 when the limit is passed. Use a shared store like Redis if you run several servers."}},
        {"@type": "Question", "name": "Should I turn on CORS for my API?", "acceptedAnswer": {"@type": "Answer", "text": "Only if browsers on other sites need to call it. Then allow the specific origins, not every origin."}},
        {"@type": "Question", "name": "Which sources does this checklist follow?", "acceptedAnswer": {"@type": "Answer", "text": "The Express production security guide and the OWASP REST Security Cheat Sheet."}}
      ]
    }
  ]
}
```
