# FairFlow Guardian Submission Packet

## Two-Minute Demo

Use the generated deck as the actual judge-facing demo:

- `output/presentation/fairflow_2_minute_video_deck.pptx`
- `output/presentation/fairflow_2_minute_video_script.txt`
- `output/presentation/fairflow_2min_video_contact_sheet.png`

Voiceover target: 155 words. The deck is intentionally paced so the presenter can speak calmly while showing the live dashboard.

## Recording Flow

1. Open the app at `http://localhost:5174`.
2. Start on `BTCUSDT` / `Calm`.
3. Show Competition Runway: readiness, audit hash, evidence pack, route proof, and calm paper approval.
4. Open Submission Kit or Evidence Pack for proof URLs.
5. Switch to `Manipulated`.
6. Show `NO_TRADE` and explain that route refusal is the core proof.
7. Close by copying the evidence pack and showing the audit hash.

## Why It Matches The BGA Track

- BGA ethos: reduces information asymmetry for retail users.
- Technical depth: agent committee, typed FastAPI/Next.js stack, Bybit public data, SQLite audit ledger, and Solidity anchor kit.
- Risk design: hidden cost, liquidity, volatility, liquidation, manipulation, policy stress, red-team, and route gates.
- Transparency: receipt, evidence pack, provenance card, audit hash, and generated walkthrough PDF.

## Final Artifacts

- Walkthrough PDF: `output/pdf/fairflow_guardian_complete_walkthrough.pdf`
- PPT demo: `output/presentation/fairflow_2_minute_video_deck.pptx`
- Narration script: `output/presentation/fairflow_2_minute_video_script.txt`
- Visual QA sheet: `output/presentation/fairflow_2min_video_contact_sheet.png`
- Latest dashboard screenshot: `tmp/assets/fairflow_dashboard_latest.png`

## Last-Minute Checks

```bash
pnpm run smoke:final
pnpm run test:api
pnpm run build
```

Safety boundary: FairFlow is an educational, paper-only prototype. It does not place live trades and is not investment advice.
