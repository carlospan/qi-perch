import { spawn } from "node:child_process";
import { homedir } from "node:os";
import { dirname, join } from "node:path";
import { existsSync } from "node:fs";
import { fileURLToPath } from "node:url";

const root = join(dirname(fileURLToPath(import.meta.url)), "..");
const cargoBin = join(homedir(), ".cargo", "bin");
const cargoExe =
  process.platform === "win32"
    ? join(cargoBin, "cargo.exe")
    : join(cargoBin, "cargo");
const tauriJs = join(root, "node_modules", "@tauri-apps", "cli", "tauri.js");

if (!existsSync(cargoExe)) {
  console.error(
    `找不到 cargo：${cargoExe}\n请先安装 Rust：https://rustup.rs 并重启 Cursor/终端。`
  );
  process.exit(1);
}

if (!existsSync(tauriJs)) {
  console.error(`找不到 @tauri-apps/cli：${tauriJs}\n请先在本目录执行 npm install。`);
  process.exit(1);
}

const sep = process.platform === "win32" ? ";" : ":";
process.env.PATH = `${cargoBin}${sep}${process.env.PATH || ""}`;

const args = process.argv.slice(2);
const child = spawn(process.execPath, [tauriJs, ...args], {
  stdio: "inherit",
  env: process.env,
  cwd: root,
});

child.on("exit", (code, signal) => {
  if (signal) process.exit(1);
  process.exit(code ?? 1);
});
