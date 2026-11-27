# Piece: personal and advisor website checklist (2026-11-27)

Product: Maheshkabra (client project). Note: the live site and owner were not confirmed to be a WAE project. This piece is generic and makes no claim about any person or company. TODO: WAE team to confirm the live URL, then adapt the examples to the real services.

**Title tag:** How to Build a Personal Website That Google and AI Can Understand (58 chars)

**Meta description:** A plain checklist for a personal or advisor website: what to write on the home page, how to set titles, add schema and be found by Google and AI tools. (about 160 chars)

**URL slug:** /blog/personal-website-checklist

## H1: How to Build a Personal Website That Google and AI Can Understand

If your website shows only your name and a slogan, search engines and AI assistants have little to work with. They need to know who you are, what you do, who you help and how to contact you. This checklist shows how to say it clearly, in plain words.

## H2: What should a personal website say on the home page?

Put four facts in the first screen, in text (not inside an image):

1. Your full name.
2. What you do, in one sentence. Example pattern: "[Name] helps [who] with [what]."
3. Who you help.
4. One clear way to contact you.

A slogan such as "Unlocking Potential, Together" is fine as a tagline, but it must sit next to a sentence that says what you actually do. A tagline alone does not tell Google or an AI assistant anything.

## H2: How do I write a good title tag and meta description?

- Title tag: put your name and your role or service first, for example "Your Name | What You Do". Keep it near 60 characters.
- Meta description: one or two sentences saying what you offer and for whom. Keep it near 150 characters.
- Give every page its own title and description. Do not copy the home page text to other pages.

## H2: Which pages does a personal or advisor site need?

| Page | Why it matters |
|---|---|
| Home | Says who you are and what you do |
| About | Your background, written only with facts you can prove |
| Services | One section for each thing you offer |
| Contact | Email, form, and city if you want local clients |
| FAQ | Short answers to questions clients ask often |
| Writing or Insights (optional) | Shows your knowledge and gives search engines more pages |

A "Contact Us" link with no email, phone or form is a common gap. Make at least one contact method visible.

## H2: How do I add structured data (schema)?

Structured data is a small block of code that tells search engines the facts on your page. For a person, use `Person`. For a business, use `Organization` or `ProfessionalService`. Only include facts that are true and visible on the page. Test the page in Google's Rich Results Test and the Schema Markup Validator.

Example for the home page (replace every TODO):

```json
{
  "@context": "https://schema.org",
  "@type": "Person",
  "name": "TODO full name",
  "url": "https://TODO-your-domain",
  "jobTitle": "TODO",
  "description": "TODO one sentence about what you do and who you help",
  "sameAs": ["TODO official LinkedIn or other profile URL"]
}
```

## H2: How do I make my site easy for AI assistants to quote?

- Write short, direct paragraphs. Start each section with the answer.
- Use the same name, job description and spelling everywhere: site, LinkedIn, directories.
- Add an About page with plain facts: who, what, where, how to contact.
- Add a `llms.txt` file at the root of your site that lists your key pages with one line each. This is optional and Google does not use it, but it is cheap and some AI tools may read it.
- Do not block search or AI crawlers in `robots.txt` unless you mean to. Add a `Sitemap:` line.

## H2: What technical basics should I check?

- Use https and make sure `http://` redirects to it.
- Add a `sitemap.xml` and submit it in Google Search Console.
- Make sure the page text is in the HTML that loads, not only drawn by JavaScript after load. Many site builders hide text this way.
- Add alt text to images and keep pages fast on a phone.
- Set a canonical link on each page.

## H2: Quick checklist

- [ ] Home page says who you are, what you do, who you help
- [ ] Unique title and meta description on every page
- [ ] Visible contact details
- [ ] About, Services and FAQ pages
- [ ] Person or Organization JSON-LD
- [ ] robots.txt, sitemap.xml, llms.txt
- [ ] Same name and description on all profiles

## H2: Frequently asked questions

### Does a personal website need a blog?
No. A blog helps only if you write useful answers to questions your clients ask. A clear Home, About, Services, Contact and FAQ page set is a good start.

### How long does it take for Google to show a new site?
It varies. Submitting a sitemap in Google Search Console and linking to the site from your profiles helps Google find it. No one can promise a ranking date.

### Is a tagline enough for SEO?
No. Search engines read text. Add a plain sentence that says what you do and who you help, next to the tagline.

### What is schema markup?
It is code in the page that labels facts such as your name, job title and website, so search engines can read them without guessing.

### What is llms.txt?
A plain text file at `/llms.txt` that lists your key pages and a short description for AI tools. It is optional, and Google Search does not use it.

### Should I use my own name or a brand name as the site name?
Use the name people search for. Use it the same way on every page and profile.

## FAQPage and Article JSON-LD

```json
{
  "@context": "https://schema.org",
  "@graph": [
    {
      "@type": "Article",
      "headline": "How to Build a Personal Website That Google and AI Can Understand",
      "datePublished": "2026-11-27",
      "author": {"@type": "Organization", "name": "We Are Engineer", "url": "https://weareengineer.com"},
      "publisher": {"@type": "Organization", "name": "We Are Engineer", "url": "https://weareengineer.com"}
    },
    {
      "@type": "FAQPage",
      "mainEntity": [
        {"@type": "Question", "name": "Does a personal website need a blog?", "acceptedAnswer": {"@type": "Answer", "text": "No. A blog helps only if you write useful answers to questions your clients ask. A clear Home, About, Services, Contact and FAQ page set is a good start."}},
        {"@type": "Question", "name": "How long does it take for Google to show a new site?", "acceptedAnswer": {"@type": "Answer", "text": "It varies. Submitting a sitemap in Google Search Console and linking to the site from your profiles helps Google find it. No one can promise a ranking date."}},
        {"@type": "Question", "name": "Is a tagline enough for SEO?", "acceptedAnswer": {"@type": "Answer", "text": "No. Search engines read text. Add a plain sentence that says what you do and who you help, next to the tagline."}},
        {"@type": "Question", "name": "What is schema markup?", "acceptedAnswer": {"@type": "Answer", "text": "It is code in the page that labels facts such as your name, job title and website, so search engines can read them without guessing."}},
        {"@type": "Question", "name": "What is llms.txt?", "acceptedAnswer": {"@type": "Answer", "text": "A plain text file at /llms.txt that lists your key pages and a short description for AI tools. It is optional, and Google Search does not use it."}}
      ]
    }
  ]
}
```
