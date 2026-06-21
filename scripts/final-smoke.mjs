import { spawnSync } from "node:child_process";
import { existsSync } from "node:fs";
import { join } from "node:path";
import { fileURLToPath } from "node:url";

const root = fileURLToPath(new URL("../", import.meta.url));
const python = existsSync(join(root, ".venv/bin/python")) ? join(root, ".venv/bin/python") : "python3";
const result = spawnSync(python, [join(root, "scripts/final_smoke.py")], {
  cwd: root,
  stdio: "inherit",
});

process.exit(result.status ?? 1);
