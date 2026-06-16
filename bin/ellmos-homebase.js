#!/usr/bin/env node

const { spawn } = require("node:child_process");
const path = require("node:path");
const pkg = require("../package.json");

if (process.argv.includes("--version")) {
  console.log(pkg.version);
  process.exit(0);
}

// Update-Hinweis nur im interaktiven Terminal (nie im MCP-/Pipe-Betrieb); update-notifier v7 ist ESM -> dynamic import
if (process.stdout.isTTY) {
  import("update-notifier").then(({ default: notifier }) => notifier({ pkg }).notify()).catch(() => {});
}

const python = process.env.PYTHON || (process.platform === "win32" ? "python" : "python3");
const srcPath = path.resolve(__dirname, "..", "src");
const env = {
  ...process.env,
  PYTHONPATH: process.env.PYTHONPATH ? `${srcPath}${path.delimiter}${process.env.PYTHONPATH}` : srcPath,
};

const child = spawn(python, ["-m", "homebase.server"], {
  stdio: "inherit",
  env,
});

child.on("error", (error) => {
  console.error(`Failed to start Python runtime '${python}': ${error.message}`);
  console.error("Install Python 3.10+ and the Python dependency 'mcp>=1.0.0'.");
  process.exit(1);
});

child.on("exit", (code, signal) => {
  if (signal) {
    process.kill(process.pid, signal);
    return;
  }
  process.exit(code ?? 0);
});
