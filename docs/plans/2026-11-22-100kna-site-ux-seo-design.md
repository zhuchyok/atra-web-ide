# 100kna.ru — UX + SEO bible v2 (2026-11-22)

Approved: conversion shell without theme swap (Reboot). Chat widget out of scope.

## Principles

- Honest prices only («от», итог после замера; no fake 40% / 0%).
- Header phone `+7 8352 38-31-20` + CTA «Вызвать на замер».
- **Price in H1/Title: only `/tseny/`** (and future real promo pages). Elsewhere: price under H1 / in CTA / tiles.
- Short menu labels; SEO in Yoast + H1.
- KISS: content + CSS + block templates, no new theme.

## Templates

### T0 Home

1. Header (logo, phone, CTA)
2. Hero — 3 offers
3. Trust strip (5 days, warranty ≤5y, two cities)
4. Catalog tiles with «от» → sections + `/tseny/`
5. 5 steps
6. Measure block (live form)
7. FAQ
8. Offices teaser → contacts

### T1 Money (category / scenario / brand)

1. One H1 (intent + geo; **no «от ₽»** except `/tseny/`)
2. Lead + price block under H1 («от …», what is / isn’t included)
3. `.bikos-cta-box` measure CTA
4. Short bullets / process
5. FAQ (section-specific; price FAQ lives on `/tseny/`)
6. Internal links: → `/tseny/` + 2–3 brands/scenarios
7. Repeat CTA

### T2 Trust (company, payment, contacts, privacy)

Facts + one measure CTA (except privacy).

## Intent ownership

| URL                        | Owns                    |
| -------------------------- | ----------------------- |
| `/`                        | Geo entry + brand + CTA |
| `/plastikovye-okna/`       | Catalog / choice + geo  |
| Brand URLs                 | Brand + geo             |
| `/tseny/`                  | All price queries       |
| Balcony / doors / cottages | Scenario + geo          |

## Visual (unified shell, 2026-11-22 night)

Reading: local windows dealer, trust-first, keep Reboot — one content language for T0/T1/article.

- Primary `#296ab1`, tokens `--bikos-*` in Additional CSS (`custom_css[reboot]`).
- Oswald for H1/H2/CTA/phone; body ~17px, content max-width 720px.
- Shared `.bikos-cta-box` + `.bikos-price-table` on money + articles.
- Images: radius 8px + soft shadow; H2 with light top rule.
- Sticky mobile measure CTA: CSS ready (`.bikos-sticky-measure`); inject HTML later if needed.
- Keep Clearfy login-hide; don’t mass-disable Clearfy / don’t fight Bitrix.

## Rollout order

1. `/plastikovye-okna/` + `/dveri/` H1 fix
2. Home T0 trim
3. Remaining T1/T2
4. Revive dead bottom form
5. Optional mobile sticky

## DoD (smoke)

- home, `/tseny/`, `/plastikovye-okna/`, `/dveri/`: one H1; measure CTA; doors H1 without price; category H1 with geo.
