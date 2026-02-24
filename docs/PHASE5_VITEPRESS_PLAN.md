# Фаза 5: Documentation Automation - План и обоснование

**Дата:** 2026-02-24  
**Статус:** 🔄 ОТЛОЖЕНА (низкий приоритет, инфраструктура документирована)

---

## Анализ текущей ситуации

### Что уже есть:

1. **Обширная документация в `docs/`**:
   - `MASTER_REFERENCE.md` — главный документ (связка с другими)
   - `CHANGES_FROM_OTHER_CHATS.md` — история изменений
   - `VERIFICATION_CHECKLIST_OPTIMIZATIONS.md` — чеклисты
   - `VICTORIA.md`, `VERONICA.md` — роли агентов
   - `TEAM_PERSONALITIES.md` — команда экспертов
   - И ещё ~50 документов

2. **Хорошая структура**:
   - Разделение по темам
   - Markdown с code blocks
   - Ссылки между документами

3. **README в корне** с основной информацией

### Проблемы:

1. ❌ **Нет поиска** — сложно найти информацию в 50+ файлах
2. ❌ **Нет навигации** — не видно структуры документации
3. ❌ **Нет версионирования** — история изменений не связана с версиями
4. ❌ **Статичные .md** — нет интерактивности

---

## Решение: VitePress

**Паттерн из Element Plus:**
- VitePress для статичного сайта из Markdown
- Full-text search встроенный
- Auto-navigation из структуры папок
- Тема с Dark/Light mode
- Deploy на GitHub Pages

---

## План внедрения (когда будет время)

### Этап 1: Инициализация (1 час)

```bash
cd docs
npm init vitepress
```

**Ответы на вопросы:**
- Site title: ATRA Documentation
- Description: Knowledge OS & Singularity 14.0 Documentation
- Theme: Default with Search

### Этап 2: Конфигурация (2 часа)

Создать `docs/.vitepress/config.ts`:

```typescript
import { defineConfig } from 'vitepress'

export default defineConfig({
  title: 'ATRA Documentation',
  description: 'Knowledge OS & Singularity 14.0',
  base: '/atra-web-ide/',  // Для GitHub Pages
  
  themeConfig: {
    nav: [
      { text: 'Guide', link: '/MASTER_REFERENCE' },
      { text: 'API', link: '/api/' },
      { text: 'Team', link: '/TEAM_PERSONALITIES' }
    ],
    
    sidebar: [
      {
        text: 'Introduction',
        items: [
          { text: 'Master Reference', link: '/MASTER_REFERENCE' },
          { text: 'Changes Log', link: '/CHANGES_FROM_OTHER_CHATS' },
          { text: 'Architecture', link: '/ARCHITECTURE_FULL' }
        ]
      },
      {
        text: 'Agents',
        items: [
          { text: 'Victoria (Team Lead)', link: '/VICTORIA' },
          { text: 'Veronica (Developer)', link: '/VERONICA' },
          { text: 'Team', link: '/TEAM_PERSONALITIES' }
        ]
      },
      {
        text: 'Development',
        items: [
          { text: 'Verification Checklist', link: '/VERIFICATION_CHECKLIST_OPTIMIZATIONS' },
          { text: 'Curator Runbook', link: '/CURATOR_RUNBOOK' },
          { text: 'Contributing', link: '/CONTRIBUTING' }
        ]
      },
      {
        text: 'Optimizations',
        items: [
          { text: 'Results', link: '/OPTIMIZATIONS_IMPLEMENTATION_RESULTS' },
          { text: 'Victoria Enhanced', link: '/VICTORIA_ENHANCED_OPTIMIZATIONS' },
          { text: 'Audit Results', link: '/AUDIT_SYSTEM_TEST_RESULTS' }
        ]
      }
    ],
    
    search: {
      provider: 'local'
    },
    
    socialLinks: [
      { icon: 'github', link: 'https://github.com/yourusername/atra-web-ide' }
    ]
  }
})
```

### Этап 3: Организация файлов (1 час)

**Структура:**
```
docs/
├── .vitepress/
│   ├── config.ts
│   └── theme/
│       └── custom.css
├── index.md                    # Главная страница
├── guide/
│   ├── getting-started.md
│   ├── MASTER_REFERENCE.md
│   └── CHANGES_FROM_OTHER_CHATS.md
├── agents/
│   ├── VICTORIA.md
│   ├── VERONICA.md
│   └── TEAM_PERSONALITIES.md
├── development/
│   ├── VERIFICATION_CHECKLIST_OPTIMIZATIONS.md
│   ├── CURATOR_RUNBOOK.md
│   └── CONTRIBUTING.md
└── optimizations/
    ├── OPTIMIZATIONS_IMPLEMENTATION_RESULTS.md
    ├── VICTORIA_ENHANCED_OPTIMIZATIONS.md
    └── AUDIT_SYSTEM_TEST_RESULTS.md
```

Создать символические ссылки или переместить файлы.

### Этап 4: Настройка поиска (30 мин)

VitePress включает встроенный поиск автоматически при `search.provider: 'local'`.

Дополнительно можно добавить Algolia DocSearch:

```typescript
search: {
  provider: 'algolia',
  options: {
    appId: '...',
    apiKey: '...',
    indexName: 'atra-docs'
  }
}
```

### Этап 5: Кастомизация темы (1 час)

Файл: `docs/.vitepress/theme/custom.css`

```css
:root {
  --vp-c-brand: #00d9ff;  /* ATRA primary color */
  --vp-c-brand-light: #4df4ff;
  --vp-c-brand-dark: #00a8cc;
}

.VPDoc {
  font-family: 'Inter', sans-serif;
}
```

### Этап 6: Deploy на GitHub Pages (30 мин)

Файл: `.github/workflows/docs.yml`

```yaml
name: Deploy Docs

on:
  push:
    branches: [main]
    paths:
      - 'docs/**'
      - '.github/workflows/docs.yml'

jobs:
  deploy:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      
      - name: Setup Node
        uses: actions/setup-node@v4
        with:
          node-version: 18
      
      - name: Install deps
        run: |
          cd docs
          npm install
      
      - name: Build docs
        run: |
          cd docs
          npm run docs:build
      
      - name: Deploy to GitHub Pages
        uses: peaceiris/actions-gh-pages@v3
        with:
          github_token: ${{ secrets.GITHUB_TOKEN }}
          publish_dir: docs/.vitepress/dist
```

---

## Преимущества после внедрения

| Аспект | Сейчас | После VitePress | Улучшение |
|--------|--------|-----------------|-----------|
| **Поиск** | Нет (Ctrl+F в IDE) | Full-text search | ✅ Да |
| **Навигация** | Ручная (README) | Auto-sidebar | ✅ Да |
| **Версионирование** | Нет | Git tags → versions | ✅ Да |
| **Mobile-friendly** | Нет | Responsive | ✅ Да |
| **Dark mode** | Нет | Да | ✅ Да |
| **Onboarding** | Сложный | Простой | ✅ +70% |

---

## Почему ОТЛОЖЕНО:

1. **Низкий приоритет** — текущая документация читаема и структурирована
2. **Время** — требует 5-6 часов чистого времени
3. **ROI** — основная польза для новых разработчиков, которых пока нет
4. **Альтернативы** — можно использовать GitHub Wiki или Notion как временное решение

---

## Когда внедрять:

- ✅ Когда появятся новые разработчики в команде
- ✅ Когда документация превысит 100 файлов
- ✅ Когда нужно публичное API documentation
- ✅ Когда есть 1 свободный день для setup

---

## Временное решение (текущее):

1. **GitHub README** — для быстрого старта
2. **MASTER_REFERENCE.md** — как единая точка входа
3. **IDE search** — Ctrl+Shift+F по `docs/`
4. **Cursor @-mentions** — для быстрого доступа к файлам

Это работает для текущей команды (1-2 человека).

---

**Вывод:** Фаза 5 — это **nice to have**, но не критично. Текущая структура документации достаточна для разработки. VitePress можно внедрить позже, когда будет обоснованная необходимость (новая команда, публичное API, 100+ документов).

---

**Приоритет:** 🟢 Низкий  
**ROI:** 📊 Средний (долгосрочно)  
**Время:** ⏱️ 5-6 часов  
**Статус:** 📋 Backlog
