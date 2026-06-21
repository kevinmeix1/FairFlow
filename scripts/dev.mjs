import { spawn } from "node:child_process";
import { existsSync } from "node:fs";
import { join } from "node:path";
import { fileURLToPath } from "node:url";

const root = fileURLToPath(new URL("../", import.meta.url));
const python = existsSync(join(root, ".venv/bin/python")) ? join(root, ".venv/bin/python") : "python3";
const nextBin = process.platform === "win32" ? "next.cmd" : "next";
let shuttingDown = false;

const services = [
  {
    name: "api",
    command: python,
    args: ["-m", "uvicorn", "fairflow_api.main:app", "--host", "0.0.0.0", "--port", "8000", "--reload"]
  },
  {
    name: "web",
    command: join(root, "node_modules/.bin", nextBin),
    args: ["dev", "--hostname", "0.0.0.0", "--port", process.env.PORT ?? "5174"]
  }
];

const children = services.map((service) => {
  const child = spawn(service.command, service.args, {
    cwd: root,
    env: {
      ...process.env,
      FAIRFLOW_API_URL: process.env.FAIRFLOW_API_URL ?? "http://localhost:8000"
    },
    stdio: "inherit"
  });

  child.on("exit", (code, signal) => {
    if (shuttingDown) return;
    console.log(`[${service.name}] exited with ${signal ?? code}`);
    shutdown(code ?? 1);
  });

  return child;
});

function shutdown(code = 0) {
  shuttingDown = true;
  for (const child of children) {
    if (!child.killed) child.kill("SIGTERM");
  }
  setTimeout(() => process.exit(code), 500).unref();
}

process.on("SIGINT", () => shutdown(0));
process.on("SIGTERM", () => shutdown(0));
