# Piece: How to Prepare for Your Final Year Project Viva

**Suggested URL:** https://weareengineer.com/blog/final-year-project-viva-preparation
**Page type:** how-to guide (AEO featured snippet + FAQ, GEO quotable answers)
**Internal links:** /blog, /about, /workshop, https://projects.weareengineer.com/students, https://www.wae.social, and the 2026-11-15 guide (/blog/how-to-choose-final-year-engineering-project, once published)
**Why this gap:** "Final year project viva questions" is a question every engineering student asks near submission. Ranking pages are student blogs and college rubrics, many generic or thin. WAE has a real, relevant offer (project mentorship with code and architecture review) and a clear policy ("WAE does not build or sell final-year projects for students"). The viva tests whether the project is the student's own, which fits that policy. It is the "next piece" listed in the 2026-11-15 report.
**Before publishing, the team must check every TODO line.** No fees, dates, student counts, marks splits or placement claims are used.

---

## Title tag (57 chars)
Final Year Project Viva: How to Prepare and Pass | WAE

## Meta description (154 chars)
Facing your final year project viva? Learn what examiners ask, how to answer, and a 7-day plan to explain your own project with confidence.

## H1
How to Prepare for Your Final Year Project Viva

## Outline
- H2: The short answer
- H2: What the viva really checks
- H2: The 8 question areas you should expect
- H2: How to answer: a simple 4-part structure
- H2: A 7-day preparation plan
- H2: What to do when you do not know the answer
- H2: Mistakes that cost marks
- H2: Team projects: know the whole project
- H2: Build your own project with a mentor at WAE
- H2: FAQ

---

## The short answer

To prepare for a final year project viva, learn your own project end to end: the problem it solves, how it is designed, why you chose each tool, how you tested it, and what its limits are. Examiners want to confirm the work is yours and that you understand your decisions. Practise answering aloud, and rehearse one short demo.

## What the viva really checks

A project viva is not a theory exam. The panel usually wants to see three things:

1. **Ownership.** Did you build this, and do you know how it works?
2. **Decisions.** Can you explain why you chose this design, this tool, this method?
3. **Honesty.** Do you know what works, what does not, and what you would change?

Marks and format differ by college and university. Ask your project guide for the exact evaluation sheet, and check whether a presentation, a demo or a source-code review is part of your viva. TODO: the team may add a link to a real university evaluation rubric if one is public.

## The 8 question areas you should expect

Prepare one clear answer for each area, using your own project.

1. **Problem and motivation.** What problem does it solve? Who will use it? Why did you pick this topic?
2. **Objectives and scope.** What did you set out to do? What is included, and what is left out?
3. **Design.** What is the architecture? Can you trace one request from the user action to the result?
4. **Tools and implementation.** Why this language, framework or board? Which part did you write yourself?
5. **Data.** Where is data stored, and why that choice? How are records related? (Even machine learning and IoT projects usually store data.)
6. **Security and safety.** How do users log in? What is the difference between authentication and authorisation? How are passwords protected? For hardware projects: what safety limits did you consider?
7. **Testing and results.** How did you test? What failed, how did you fix it, and what was the result after the fix?
8. **Limits and future work.** What are the weaknesses? What would you do next?

Branch-specific projects need branch-specific questions. For an ML project, expect questions on data and evaluation. For an electronics project, expect questions on component choice and calibration. For a civil or mechanical project, expect questions on assumptions and calculations. TODO: a separate branch-wise question page can be written once reviewed by an engineer of each branch.

## How to answer: a simple 4-part structure

Use this order for most questions:

1. **Direct answer** in one sentence.
2. **Context** from your project.
3. **Evidence**: a test, a screen, a log, a measurement, a file.
4. **Limit**: one honest note on what it does not cover.

Example (web project, question: "Why did you choose this database?"):
"I used a relational database because my data has clear links between users and orders. In my project the orders table points to the users table with a foreign key. I tested this by adding an order for a user that did not exist, and the database rejected it. The limit is that I have not tested it with a large amount of data."

Avoid absolute words such as "100% secure", "bug-free" or "production-ready". Say what you tested and under what conditions.

## A 7-day preparation plan

- **Day 1: Project map.** Write one page: problem, users, architecture, tools, data, tests, limits. Check that it matches your final report and your working build.
- **Day 2: Trace one flow.** Follow one complete use of the project, from the first user action to the final result. Be able to draw it.
- **Day 3: Tools and decisions.** For each tool or component, write one line: why this and not the alternative.
- **Day 4: Revise only what you used.** Revise the concepts your project actually uses (for example your own tables and keys, your own model and metric, your own circuit). Skip the rest.
- **Day 5: Tests.** Prepare three real test cases. Include one that failed, the cause and the fix.
- **Day 6: Demo.** Rehearse a two to three minute demo of the core feature with test data. Prepare a backup, such as screenshots or a recorded run, in case the live demo fails. Do not show passwords, keys or tokens.
- **Day 7: Mock viva.** Ask a friend or senior to ask questions from the 8 areas. Answer aloud and keep time.

Your own timeline may be shorter or longer. The order matters more than the number of days.

## What to do when you do not know the answer

- **Say so, then show what you do know.** "I did not work on that part. In my implementation, this is how it works."
- **Incomplete feature:** say it was not completed and explain how that affects the results.
- **Failed test:** explain the cause, the fix and the result of the retest.
- **Never guess confidently.** A calm, honest answer scores better than a wrong, confident one.

## Mistakes that cost marks

- Learning a question bank instead of your own project.
- A report, diagrams and code that do not match each other.
- Claims with no evidence.
- Not being able to explain code or a circuit you present as yours.
- Spending the whole demo on small features and skipping the core one.
- Not reading the evaluation sheet.

A smaller feature that works and that you can fully explain is stronger than a large module you cannot defend.

## Team projects: know the whole project

In a team, examiners often ask each member about the whole project, not only their own part. Know the architecture and the results of the full project, know exactly which parts you built, and be able to show proof, such as files, commits or test records.

## Build your own project with a mentor at WAE

The best viva preparation starts months earlier: a project you built yourself and understand. WAE Projects offers student project mentorship. According to projects.weareengineer.com/students, you get a mentor from start to finish, a scoped plan with finishable milestones, code and architecture review at each milestone, and a verified project card on your WAE profile once the project is finished.

WAE does not build or sell final-year projects for students. You build your own work with a mentor.

TODO: price and application details are not confirmed. The team will share the details when you apply. See [Student Project Mentorship](https://projects.weareengineer.com/students).

Still choosing a topic? Read [How to Choose a Final Year Engineering Project](/blog/how-to-choose-final-year-engineering-project). TODO: link live only after that page is published.

## FAQ

### What is asked in a final year project viva?
Examiners usually ask about your problem and objectives, your design, the tools you chose and why, your data, testing and results, security or safety, and the limits of your work. They also check which parts you built yourself. Prepare one clear answer for each area using your own project.

### How do I prepare for a project viva in a few days?
Write a one-page project map, trace one full flow of your project, list why you chose each tool, prepare three real test cases, and rehearse a short demo. Then do a mock viva with a friend. Revise only the concepts your project uses.

### How do I start a project viva answer?
Give a one-sentence direct answer first, then add context from your project, one piece of evidence such as a test or a screen, and one honest limit. This keeps answers short and shows that you understand your own work.

### What if I do not know the answer to a viva question?
Say honestly that you do not know or did not work on that part, then explain what you do know from your own implementation. Do not guess with confidence. Examiners respect honesty and may ask a simpler follow-up.

### Do I need to know the whole project in a team viva?
Yes. In many vivas each member can be asked about any part. Know the full architecture and results, and be clear about which parts you built and how you can show it.

### Should I prepare theory questions too?
Prepare the theory behind what you used, such as your database design, your model and its metric, or your circuit components. Do not spend time on topics your project does not use. The viva tests your own project more than general theory.

### How many marks does the viva carry?
It depends on your college and university. Ask your project guide for the evaluation sheet. TODO: do not state a figure unless taken from a named official source.

### Does WAE give final year projects to students?
No. WAE does not build or sell final-year projects for students. WAE Projects offers mentorship so that students build their own project with a mentor, a milestone plan and code and architecture review.

---

## JSON-LD

```json
{
  "@context": "https://schema.org",
  "@graph": [
    {
      "@type": "Article",
      "@id": "https://weareengineer.com/blog/final-year-project-viva-preparation#article",
      "headline": "How to Prepare for Your Final Year Project Viva",
      "description": "Learn what examiners ask in a final year project viva, how to answer, and a 7-day plan to explain your own project with confidence.",
      "inLanguage": "en-IN",
      "mainEntityOfPage": "https://weareengineer.com/blog/final-year-project-viva-preparation",
      "datePublished": "2026-11-19",
      "dateModified": "2026-11-19",
      "author": {
        "@type": "Organization",
        "name": "We Are Engineer (WAE)",
        "url": "https://weareengineer.com"
      },
      "publisher": {
        "@type": "Organization",
        "name": "We Are Engineer (WAE)",
        "url": "https://weareengineer.com"
      }
    },
    {
      "@type": "FAQPage",
      "@id": "https://weareengineer.com/blog/final-year-project-viva-preparation#faq",
      "mainEntity": [
        {
          "@type": "Question",
          "name": "What is asked in a final year project viva?",
          "acceptedAnswer": {
            "@type": "Answer",
            "text": "Examiners usually ask about your problem and objectives, your design, the tools you chose and why, your data, testing and results, security or safety, and the limits of your work. They also check which parts you built yourself. Prepare one clear answer for each area using your own project."
          }
        },
        {
          "@type": "Question",
          "name": "How do I prepare for a project viva in a few days?",
          "acceptedAnswer": {
            "@type": "Answer",
            "text": "Write a one-page project map, trace one full flow of your project, list why you chose each tool, prepare three real test cases, and rehearse a short demo. Then do a mock viva with a friend. Revise only the concepts your project uses."
          }
        },
        {
          "@type": "Question",
          "name": "How do I start a project viva answer?",
          "acceptedAnswer": {
            "@type": "Answer",
            "text": "Give a one-sentence direct answer first, then add context from your project, one piece of evidence such as a test or a screen, and one honest limit. This keeps answers short and shows that you understand your own work."
          }
        },
        {
          "@type": "Question",
          "name": "What if I do not know the answer to a viva question?",
          "acceptedAnswer": {
            "@type": "Answer",
            "text": "Say honestly that you do not know or did not work on that part, then explain what you do know from your own implementation. Do not guess with confidence. Examiners respect honesty and may ask a simpler follow-up."
          }
        },
        {
          "@type": "Question",
          "name": "Do I need to know the whole project in a team viva?",
          "acceptedAnswer": {
            "@type": "Answer",
            "text": "Yes. In many vivas each member can be asked about any part. Know the full architecture and results, and be clear about which parts you built and how you can show it."
          }
        },
        {
          "@type": "Question",
          "name": "Does WAE give final year projects to students?",
          "acceptedAnswer": {
            "@type": "Answer",
            "text": "No. WAE does not build or sell final-year projects for students. WAE Projects offers mentorship so that students build their own project with a mentor, a milestone plan and code and architecture review."
          }
        }
      ]
    }
  ]
}
```

TODO before publishing: confirm the author (a named WAE engineer or mentor is better than the Organization; do not invent a name) and the `datePublished` on the day it goes live.
