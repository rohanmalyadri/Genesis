# Genesis RAG: frontend

Next.js app for [Genesis RAG](../README.md). Made with love by Rohan Malyadri from Obscuron X Labs.

```bash
npm install
npm run dev        # http://localhost:3000
npm run build      # production build
```

The app talks to the backend at `NEXT_PUBLIC_API_URL` (default `http://localhost:8000`).
If the backend has `API_KEY` set, also set `NEXT_PUBLIC_API_KEY` to the same value.
