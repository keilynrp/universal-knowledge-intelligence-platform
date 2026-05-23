# Frontend

Next.js 16 application with React 19, TypeScript 5, and Tailwind CSS 4.

## Development

```bash
npm install
npm run dev        # http://localhost:3004
npm run build      # Production build
npm run lint       # ESLint
```

## Pages

| Route              | Description                                |
|--------------------|--------------------------------------------|
| `/`                | Entity workspace -- browse, search, edit, delete |
| `/analytics`       | Analytics dashboard with key metrics       |
| `/disambiguation`  | Fuzzy-match tool for finding inconsistencies |
| `/authority`       | Authority control -- normalization rules   |
| `/import-export`   | Excel import/export and database purge     |

## Components

| Component              | Purpose                                  |
|------------------------|------------------------------------------|
| `Sidebar.tsx`          | Collapsible navigation sidebar           |
| `Header.tsx`           | Sticky header with dynamic page title    |
| `EntityTableContent.tsx` | Entity listing and review workspace      |
| `DisambiguationTool.tsx` | Fuzzy-match group viewer               |
| `MetricCard.tsx`       | Reusable stat card for analytics         |

## Configuration

The frontend connects to the backend API at `http://localhost:8000`. To change this, update the `fetch` URLs in the page and component files.
