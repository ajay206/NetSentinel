# NOC Console (Frontend)

The **noc-console** application is the user‑facing dashboard for NetSentinel.  
It is a single‑page application built with **Vite**, **React**, **TypeScript**, and **Tailwind CSS**.  
The UI runs locally (Node 22) and talks to the backend **api‑gateway** through the Vite dev‑server proxy, so you never need to hard‑code hostnames or ports in the source code.

---

## Purpose

| Goal | Description |
|------|-------------|
| **Live alarm view** | Shows a table of the most recent alarms with colour‑coded severity (critical → red, major → orange, …, cleared → gray). |
| **Service health tiles** | Small cards that display the health status of core services (api‑gateway, Kafka, TimescaleDB). |
| **Extensible panels** | The layout is deliberately simple – a grid of panels that can be expanded in later weeks (e.g., KPI charts, topology view, ticket list). |

---

## Project Layout

```
noc-console/
├─ public/                 # Static assets (favicon, index.html)
├─ src/
│  ├─ api/                 # Thin wrappers around the HTTP & WS endpoints
│  │   ├─ health.ts        # GET /health
│  │   ├─ alarms.ts        # GET /api/alarms/recent
│  │   └─ ws.ts            # WebSocket client for /ws/alarms
│  ├─ components/          # Re‑usable UI pieces
│  │   ├─ AlarmTable.tsx   # Table that renders alarms with severity colours
│  │   ├─ ServiceTile.tsx  # Tile that shows health of a single service
│  │   └─ Layout.tsx       # Simple grid layout for panels
│  ├─ pages/               # Top‑level pages (currently only Dashboard)
│  │   └─ Dashboard.tsx
│  ├─ hooks/               # Custom React hooks (e.g., useAlarms, useHealth)
│  ├─ utils/               # Helper functions (date formatting, className helpers)
│  └─ main.tsx             # React entry point
├─ vite.config.ts          # Vite config – includes the proxy definition
├─ tsconfig.json
├─ tailwind.config.cjs
├─ package.json
└─ README.md               # THIS FILE
```

---

## How It Talks to the Backend

During development the Vite dev server proxies API calls to the **api‑gateway** that is running on port 8000.

```ts
// vite.config.ts (excerpt)
export default defineConfig({
  server: {
    proxy: {
      // All /api/*, /health and /ws/* requests are forwarded to the gateway
      '^/(api|health|ws)': {
        target: 'http://localhost:8000',
        changeOrigin: true,
        ws: true,
      },
    },
  },
});
```

Because of this proxy:

* The frontend code uses **relative URLs** (`/api/alarms/recent`, `/health`, `/ws/alarms`).
* No environment variable is required for the gateway address.
* When you build the app for production, the same relative URLs will work behind any reverse‑proxy (e.g., Traefik) that routes `/api` and `/ws` to the gateway container.

The `src/api` folder contains thin wrappers that use **fetch** for HTTP calls and the native **WebSocket** API for the live alarm stream.

---

## Adding a New Panel (Week 3+)

1. **Create a component** in `src/components/` (or `src/pages/` if it is a full page).  
   Follow the existing pattern: export a default React component that receives any needed props.

2. **Update the layout**:  
   Open `src/components/Layout.tsx` and add your component to the JSX grid.  
   The layout uses Tailwind’s `grid` utilities, so you can control column/row span with classes like `col-span-2`.

3. **Wire data sources** (if needed):  
   * For HTTP data, add a function in `src/api/` and a corresponding hook in `src/hooks/`.  
   * For real‑time data, extend `src/api/ws.ts` to listen for additional message types and expose them via a custom hook.

4. **Style**:  
   Use Tailwind utility classes; refer to `tailwind.config.cjs` for the colour palette that matches alarm severities.

5. **Test**:  
   Run `npm run test` (Jest) and `npm run lint` to ensure the new code follows the repo standards.

---

## Scripts

| Script | Description |
|--------|-------------|
| `npm run dev` | Starts Vite dev server on **http://localhost:5173** (proxy configured). |
| `npm run build` | Produces an optimized static bundle in `dist/`. |
| `npm run lint` | Runs **eslint** + **prettier** checks. |
| `npm run typecheck` | Executes **tsc** in `noEmit` mode. |
| `npm run test` | Runs **vitest** unit tests. |
| `npm run preview` | Serves the production build locally (`vite preview`). |

---

## Development Checklist

1. **Prerequisite** – Node 22 (see `docs/handbook/02-local-setup.md`).  
2. Run `npm install` once after cloning.  
3. `make console-install` (installs deps via npm).  
4. `make console` (starts dev server).  
5. Verify the dashboard loads at **http://localhost:5173** and shows live alarms.  
6. When adding new panels, run the full lint/typecheck/test suite before committing.

--- 

## Gotchas on Mac M2 (8 GB RAM)

* The Vite dev server is lightweight, but keep an eye on memory when the simulator is also running.  
* If you see the UI become sluggish, stop the **netgen‑simulator** (`make down` or `docker compose stop sim`) and restart the console.  

Happy coding!  

---  

*This README is maintained for junior developers joining the project. It explains the purpose, structure, and how to extend the NOC console.*
