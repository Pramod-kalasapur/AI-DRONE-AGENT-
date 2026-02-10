# Decision Log

## Assumptions
- Sheets use exact schema provided (pilot_id/name/skills/etc.)
- "Urgent reassignments": HIGH-severity conflicts with auto-suggestions for available alternatives
- Availability: status='Available' AND available_from <= today (2026-02-10)

## Trade-offs
- **Stack**: Flask + gspread (mature, simple 2-way sync). No DB for prototype speed.
- **NLP**: Regex keyword matching (fast, accurate for drone terms). Full LLM too heavy.
- **UI**: Vanilla JS/CSS (no React build step, deploys anywhere). Modern glassmorphism design.
- **Conflicts**: On-query (not polling) to avoid API quota hits.

## With More Time
- WebSockets for live updates
- Full LLM (Grok/Claude) for assignment optimization
- Calendar integration for date overlaps
- Mobile PWA
- Multi-user auth

Deployment: Replit (free, auto-scales, secrets for creds).