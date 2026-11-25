# 100kna.ru — Beat competitors (Approach A) — design

Approved: 2026-11-23 (user: «а»).

## Design read

Local windows dealer landing (Чебоксары / Новочебоксарск), trust-first, density like gosokna21 / oknavsem21, **without** fake «цены 2019 / −40%». Keep Reboot + Clearfy. Brand blue `#296ab1` (not GOS21 coral-dark clone).

## Decision

**Approach A:** Stay on Reboot. Rebuild conversion on Gutenberg + Additional CSS + live lead form. No new theme / no Tilda.

Beat them on: honest «от ₽ + что входит», working form, filled sections, real works, clear funnel — not on dark theme cosplay.

## Competitors → what we take / skip

| Take                                           | Skip                         |
| ---------------------------------------------- | ---------------------------- |
| Intent triad (окна / балкон / двери)           | «Цены 2019», TОП-5 hyperbole |
| Dual CTA: form + tel (not tel-only)            | SEO mega-menu forest day-1   |
| Trust: external reviews + steps + «что входит» | Copying their %/claims       |
| Calc / photo later (P1)                        | Full Bitrix rebuild          |
| Sticky messengers + tel                        | Dead Quizle                  |

## T0 Home (target map)

1. Header: logo, phone `+7 8352 38-31-20`, CTA → **live form** (modal or anchor)
2. Hero: one promise + product photo + 2 CTA (замер / цены)
3. Trust strip: срок от 5 дн · гарантия монтажа до 5 лет · 2 города · link Яндекс-отзывы
4. Intent: Что нужно? → окна / балконы / двери
5. Catalog tiles with «от» → sections + `/tseny/`
6. **5 шагов** (filled, not empty)
7. Measure block: **live form** (имя*, тел*, что нужно, согласие)
8. FAQ accordion
9. Offices teaser → `/contacts/`
10. Sticky mobile: tel + form

## Forms (P0)

- Kill «Форма не актуальна» path (Quizle dead).
- Replace with CF7 / Fluent / native WP form that actually mails or posts.
- Same form ID reused: home, contacts, tseny, money pages CTA.

## Contacts (P0)

- Office cards with phones hierarchy: CTA = 38-31-20; office lines labeled.
- Yandex Map iframe (not empty H2).

## Visual

- `--bikos-max: 1100px` (match Reboot wrap; was 720).
- Cards / CTA: radius 8–12px, blue primary, soft panels `#f3f7fc`.
- No purple gradients, no fake stock lifestyle if we have real works.

## Out of scope (P0)

- Full calculator, photo upload, new theme, chat widget rebuild.

## Success criteria

- Home useful words ≥ ~1800, H2 ≥ 8 with body
- Lead form submit OK on ≥3 URLs
- Dead form string = 0
- Map iframe ≥ 1 on `/contacts/`
- CTA = form + tel
