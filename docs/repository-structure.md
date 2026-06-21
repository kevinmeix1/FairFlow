# Repository Structure

FairFlow Guardian is organized as a full-stack hackathon prototype with a curated submission packet.

```text
app/                 Next.js app routes and metadata
components/          Dashboard UI and interaction surface
contracts/           Solidity audit anchor contract
fairflow_api/        FastAPI backend, agents, market adapter, audit ledger
lib/                 Typed frontend API client
scripts/             Local build, PDF, validation, and smoke-test tools
tests/               Backend behavior and submission-readiness tests
docs/                Experiment notes and repository documentation
output/              Generated PDFs and presentation outputs
submission/          Curated judge-facing deck, PDFs, screenshots, and video slot
```

Generated local caches, runtime dependencies, temporary render pages, and local SQLite ledgers are ignored by `.gitignore`.
