# Expo app release checklist: build, store review and OTA updates

**Product context:** written for the team behind ShareItClub Expo (ShareItClub mobile app, Expo). This piece is generic. It claims nothing about ShareItClub features, stack, users or numbers. TODO: team to confirm what the app does before adding a product box.

## Title tag
Expo App Release Checklist: Build, Store Review, OTA Updates | WAE
(61 characters; trim "| WAE" if needed)

## Meta description
A plain checklist for shipping an Expo app: release build, env vars on EAS, build numbers, store review notes, and when an OTA update is enough. By We Are Engineer.

## URL (proposed)
/blog/expo-app-release-checklist

## Outline
- H1: Expo app release checklist: build, store review and OTA updates
- H2: Quick answer
- H2: 1. Test the real release build, not Expo Go
- H2: 2. Set environment variables on EAS
- H3: Use the EXPO_PUBLIC_ prefix for values read in app code
- H2: 3. Version numbers and build numbers
- H2: 4. Store review: what to prepare
- H2: 5. OTA update or new store build?
- H2: 6. Runtime version and channels
- H2: 7. Final pre-release list
- H2: FAQ

---

# Expo app release checklist: build, store review and OTA updates

## Quick answer
Before you ship an Expo app, test a real release build on a real device, set every environment variable on EAS, raise the version and build numbers, prepare privacy policy links and demo login for the reviewer, and decide if the change needs a new store build or only an over-the-air (OTA) update. JavaScript and asset changes can go by OTA. Native changes cannot.

## 1. Test the real release build, not Expo Go
A debug build or Expo Go can work while the store build shows a blank screen or crashes. Apple's App Review often flags apps that do not work as described under Guideline 2.1 (App Completeness). Expo's own article on rejections says this is the largest category of review issues.

Check on a physical device with a production-profile build:
- The app opens and the first screen loads.
- Sign-in works.
- Every screen that calls your API gets real data.
- Permissions prompts show clear text.

## 2. Set environment variables on EAS
EAS cloud builds do not read your local `.env` file by default. A missing variable is a common reason a production build crashes while development works.

- Add each variable to the EAS environment that matches the build profile (development, preview, production).
- Values read in app code need the `EXPO_PUBLIC_` prefix.
- Anything with `EXPO_PUBLIC_` ends up inside the app bundle. Never put secret keys there. Keep secrets on your server.

## 3. Version numbers and build numbers
Each upload to a store needs a build number higher than the last one. A stale, hand-managed build number is a frequent reason a second upload fails. Let EAS manage it, or raise it every time. TODO: team to confirm whether the project uses EAS remote versioning.

## 4. Store review: what to prepare
- A working privacy policy link in the app and in the store listing (missing links are a frequent issue under Guideline 5.1).
- A Terms of Service link, if the app has accounts.
- Demo login details in the review notes, if the app needs sign-in.
- Screenshots in the sizes each store requires.
- If the app lets users delete their account, say where in the app. TODO: confirm with the store's current rules for the app's category.

## 5. OTA update or new store build?
| Change | OTA update enough? |
|---|---|
| JavaScript code, styles, text | Yes |
| Images and other assets | Yes |
| New native library or native code | No, new build |
| Permission changes | No, new build |
| Expo SDK upgrade | No, new build |
| App config changes that affect native settings | No, new build |

A common trap: a dependency you think is JavaScript-only has native code. When in doubt, make a new build.

## 6. Runtime version and channels
- An update only runs on builds with the exact same runtime version and platform.
- With the `appVersion` policy, the runtime version changes when you raise the app version. If you change native code and forget to raise it, users get an update their build cannot run.
- Expo recommends a unique runtime version for each production release.
- Use separate channels for preview and production. Publish to preview first, test, then promote to production.
- Expo supports gradual rollout and fast rollback for updates. TODO: read the current EAS Update docs for exact commands before documenting them.

## 7. Final pre-release list
- [ ] Release build tested on a real Android and iOS device
- [ ] All env vars set on EAS for the production profile
- [ ] No secret keys in `EXPO_PUBLIC_` values
- [ ] Version and build number raised
- [ ] Privacy policy and Terms links work
- [ ] Demo login in review notes
- [ ] Screenshots ready
- [ ] Runtime version set; preview channel tested first
- [ ] Rollback plan written down

## FAQ

### Why does my Expo app work in development but crash in the store build?
The most common causes are missing environment variables on EAS, a feature that only works in Expo Go or a debug build, and an API that is not reachable from the release build. Test a production-profile build on a real device before you submit.

### Do EAS builds use my local .env file?
No, not by default. Cloud builds use variables stored in EAS for the matching environment. Values your app code reads need the `EXPO_PUBLIC_` prefix, and they are visible inside the app, so never put secrets in them.

### When is an OTA update enough?
When you changed only JavaScript, styles, text or assets. Changes to native code, native libraries, permissions or the Expo SDK version need a new store build.

### What is a runtime version in EAS Update?
It ties an update to the native build that can run it. The build and the update must have the exact same runtime version and platform, or the update will not apply.

### What do I put in App Review notes?
Working demo login details if the app needs sign-in, and a short note on any feature that needs special steps to see. Also make sure the privacy policy link works.

## JSON-LD
```json
{
  "@context": "https://schema.org",
  "@graph": [
    {
      "@type": "Article",
      "headline": "Expo app release checklist: build, store review and OTA updates",
      "description": "A plain checklist for shipping an Expo app: release build, env vars on EAS, build numbers, store review notes, and when an OTA update is enough.",
      "datePublished": "2026-11-23",
      "author": { "@type": "Organization", "name": "We Are Engineer" },
      "publisher": { "@type": "Organization", "name": "We Are Engineer", "url": "https://weareengineer.com" },
      "mainEntityOfPage": "https://weareengineer.com/blog/expo-app-release-checklist"
    },
    {
      "@type": "FAQPage",
      "mainEntity": [
        { "@type": "Question", "name": "Why does my Expo app work in development but crash in the store build?", "acceptedAnswer": { "@type": "Answer", "text": "The most common causes are missing environment variables on EAS, a feature that only works in Expo Go or a debug build, and an API that is not reachable from the release build. Test a production-profile build on a real device before you submit." } },
        { "@type": "Question", "name": "Do EAS builds use my local .env file?", "acceptedAnswer": { "@type": "Answer", "text": "No, not by default. Cloud builds use variables stored in EAS for the matching environment. Values your app code reads need the EXPO_PUBLIC_ prefix, and they are visible inside the app, so never put secrets in them." } },
        { "@type": "Question", "name": "When is an OTA update enough?", "acceptedAnswer": { "@type": "Answer", "text": "When you changed only JavaScript, styles, text or assets. Changes to native code, native libraries, permissions or the Expo SDK version need a new store build." } },
        { "@type": "Question", "name": "What is a runtime version in EAS Update?", "acceptedAnswer": { "@type": "Answer", "text": "It ties an update to the native build that can run it. The build and the update must have the exact same runtime version and platform, or the update will not apply." } },
        { "@type": "Question", "name": "What do I put in App Review notes?", "acceptedAnswer": { "@type": "Answer", "text": "Working demo login details if the app needs sign-in, and a short note on any feature that needs special steps to see. Also make sure the privacy policy link works." } }
      ]
    }
  ]
}
```

## Sources used for facts
- https://expo.dev/articles/shipping-to-the-app-stores/app-store-rejection-reasons
- https://docs.expo.dev/eas-update/runtime-versions/
- https://docs.expo.dev/eas-update/deployment
- https://expo.dev/blog/5-ota-update-best-practices-every-mobile-team-should-know
