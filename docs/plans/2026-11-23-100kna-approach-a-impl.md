# 100kna Approach A — implementation plan

Design: `docs/plans/2026-11-23-100kna-beat-competitors-design.md`

## P0 — stop feeling empty (this sprint)

1. **Live lead form** — replace Quizle «Форма не актуальна» with working CF7/Fluent/HTML mailto fallback; wire header CTA + home + contacts + tseny.
2. **Home density** — fill «5 шагов»; add trust strip; intent triad; expand FAQ; remove empty shells.
3. **Contacts** — Yandex Map iframe; office cards; CTA phone hierarchy.
4. **Smoke** — form submit path visible OK; no dead string; map present; H2s have body.

## P1 — funnel parity

5. Simple price grid «что входит» on `/tseny/`.
6. Works gallery (8–12 real photos with street/profile).
7. Light calculator or «расчёт по фото» one-screen.

## P2

8. Team faces, sticky WA/TG if numbers exist, PDF optional.

## UI polish (2026-11-23) — done live

9. **Hero:** `slider_count=1`, `slider_post_in=1292` (окна); arrows/pagination hidden.
10. **Desktop nav:** burger `display:none` ≥992px; product menu one row under header (`position:relative`, no fixed twin).
11. **Shell v2:** trust pills, intent hover, form card; `--bikos-max` rhythm.
12. **Noise:** removed «Комплексный подход» / «Наши клиенты»; mypopup/quizle CSS hide; Bitrix24 proactive bubble muted (button kept).
13. **Form fix:** cleaned mangled `bikos-lead-form` attributes (`POST"tel:` / JS garbage) → clean FormSubmit.

Smoke: desktop 1440 — hero windows-only, nav orderOk, water gone, form placeholders clean.

## Beat v3 / path 2 — rolled back (2026-11-23 eve)

User asked restore slider + page width + styles. Reverted:

- Removed `BIKOS BEAT v3` CSS; kept UX shell 2026-11-22 (`--bikos-max:1100px`).
- `slider_count=1`, `slider_post_in=1292`.
- Removed home `bikos-bento` / `bikos-calc` HTML.

## Rollback

WP revisions + Customizer CSS snapshot; disable new popup; restore Quizle only if needed as hidden.
