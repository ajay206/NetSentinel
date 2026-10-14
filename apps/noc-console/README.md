# NOC Console (Frontend)

The **noc-console** application is the user‑facing dashboard for NetSentinel.  
It is a single‑page application built with **Vite**, **React**, **TypeScript**, and **Tailwind CSS**. The UI runs locally (Node 22) and talks to the backend **api‑gateway** through the Vite dev‑server proxy, so no hostnames or ports are hard‑coded.

---

## Purpose (Week 3)

| Feature | Description |
|---------|-------------|
| **Live alarm view** | Table of recent alarms, colour‑coded by severity (critical → red, major → orange, …, cleared → gray). |
| **Network map** | SVG topology from `/api/topology`; sites rendered as square (core), diamond (hub), circle (access). Site colour reflects the worst **ACTIVE** alarm severity (green = none, yellow = warning, orange = major, red = critical). Critical sites pulse. |
| **KPI activity panel** | Shows total samples, samples/min, cells reporting, last sample time (stale badge after 60 s), and network‑wide KPI averages (last 500 values) updated every 2 s via `/ws/kpis`. |
| **Service health tiles** | Health status of core services (api‑gateway, Kafka, TimescaleDB). |
| **IST timestamps** | All dates/times displayed in **IST (Asia/Kolkata)** with an “IST” label. |

---

## Project Layout

```
noc-console/
├─ public/                 # Static assets (favicon, index.html)
├─ src/
│  ├─ api/                 # Thin wrappers around HTTP & WS endpoints
│  │   ├─ health.ts        # GET /health
│  │   ├─ alarms.ts        # GET /api/alarms/recent
│  │   ├─ topology.ts      # GET /api/topology
│  │   ├─ kpis.ts          # GET /api/kpis/activity
│  │   └─ ws.ts            # WebSocket client for /ws/kpis
│  ├─ components/          # Re‑usable UI pieces
│  │   ├─ AlarmTable.tsx
│  │   ├─ ServiceTile.tsx
│  │   ├─ NetworkMap.tsx   # SVG map, uses useTopology()
│  │   ├─ KpiActivity.tsx  # Live KPI panel, uses useKpiActivity()
│  │   └─ Layout.tsx
│  ├─ hooks/               # Custom React hooks
│  │   ├─ useAlarms.ts
│  │   ├─ useHealth.ts
│  │   ├─ useTopology.ts   # fetches topology, returns parsed SVG data
│  │   └─ useKpiActivity.ts
│  ├─ lib/                 # Helper libraries
│  │   ├─ time.ts          # IST conversion, formatDate, stale check
│  │   └─ siteStatus.ts    # severity ranking, colour mapping, pulse flag
│  ├─ pages/
│  │   └─ Dashboard.tsx    # Assembles Layout with the four panels
│  ├─ utils/               # Misc helpers (classNames, debounce)
│  └─ main.tsx
├─ vite.config.ts
├─ tsconfig.json
├─ tailwind.config.cjs
├─ package.json
└─ README.md               # THIS FILE
```

---

## How It Talks to the Backend

During development the Vite dev server proxies API calls to the **api‑gateway** on port 8000.

```ts
// vite.config.ts (excerpt)
export default defineConfig({
  server: {
    proxy: {
      '^/(api|health|ws)': {
        target: 'http://localhost:8000',
        changeOrigin: true,
        ws: true,
      },
    },
  },
});
```

* Front‑end uses **relative URLs** (`/api/topology`, `/api/kpis/activity`, `/ws/kpis`).  
* The same URLs work in production behind any reverse‑proxy.

---

## Adding a New Panel (Week 3+)

1. **Create a component** in `src/components/` (or a full page in `src/pages/`). Export a default React component.  
2. **Update the layout** – edit `src/components/Layout.tsx` and insert your component into the Tailwind `grid`.  
3. **Wire data sources**:  
   * HTTP → add a function in `src/api/` and a hook in `src/hooks/`.  
   * Real‑time → extend `src/api/ws.ts` to listen for new message types and expose via a hook.  
4. **Style** – use Tailwind utilities; refer to `tailwind.config.cjs` for the colour palette that matches alarm severities.  
5. **Test** – run `npm run test` and `npm run lint` before committing.

---

## Scripts

| Script | Description |
|--------|-------------|
| `npm run dev` | Starts Vite dev server (`http://localhost:5173`). |
| `npm run build` | Produces an optimized static bundle in `dist/`. |
| `npm run lint` | Runs **eslint** + **prettier**. |
| `npm run typecheck` | Executes **tsc** in `noEmit` mode. |
| `npm run test` | Runs **vitest** unit tests. |
| `npm run preview` | Serves the production build locally. |

---

## Development Checklist

1. **Prerequisite** – Node 22 (see `docs/handbook/02-local-setup.md`).  
2. `npm install` once after cloning.  
3. `make console-install` (installs deps via npm).  
4. `make console` (starts dev server).  
5. Verify the dashboard loads at **http://localhost:5173** and shows:  
   * Network map with site colours and pulsing critical sites.  
   * KPI activity panel updating every 2 s.  
   * Live alarm table.  
6. Run the full lint/typecheck/test suite before pushing.

---

## Gotchas on Mac M2 (8 GB RAM)

* The Vite dev server is lightweight, but running the KPI simulator together can push memory. Stop the simulator (`make down` or `docker compose stop sim`) if the UI becomes sluggish.  
* SVG rendering is cheap; however, very large topologies (full mode) may cause the map to lag. Use the default **small** topology for development.

Happy coding!  

---  

*This README is maintained for junior developers joining the project. It explains the purpose, structure, new Week 3 panels, and how to extend the NOC console.*
