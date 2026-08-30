//! 拉起 Python 大脑：bundled `qi-brain`（安装布局）或仓库 `python -m qi`（开发）。
//!
//! 选脑优先级（P3 sidecar）：
//! 1. 9527 已在听 → 沿用（borrowed，退出不杀）
//! 2. 旁有 bundled `qi-brain` → 起它
//! 3. 否则仓库根 `python -m qi`
//! 4. 失败 → 日志提示（前端走既有连接失败可见路径）
//!
//! 退出策略（P2 托盘）：仅在壳 **自己拉起** 大脑时，于 `RunEvent::Exit`（「退出栖」）结束子进程；
//! 沿用已在听的后端（borrowed）不杀。关主窗藏托盘不会走到 Exit。

use std::net::TcpStream;
use std::path::{Path, PathBuf};
use std::process::{Child, Command, Stdio};
use std::sync::Mutex;
use std::thread;
use std::time::{Duration, Instant};

use tauri::{AppHandle, Manager, RunEvent, State};

const WS_PROBE: &str = "127.0.0.1:9527";
/// 冷启动含向量库时可能较慢；超时后仍继续，前端会重连
const WS_READY_TIMEOUT: Duration = Duration::from_secs(45);

pub struct BrainSidecar {
  child: Mutex<Option<Child>>,
  /// 若为 true，退出时不杀（沿用用户已开的大脑进程）
  borrowed: bool,
}

impl BrainSidecar {
  fn empty_borrowed() -> Self {
    Self {
      child: Mutex::new(None),
      borrowed: true,
    }
  }

  fn owned(child: Child) -> Self {
    Self {
      child: Mutex::new(Some(child)),
      borrowed: false,
    }
  }
}

pub fn attach(app: &AppHandle) {
  if skip_requested() {
    eprintln!("[qi] QI_SKIP_BRAIN 已设：不拉起 Python 大脑");
    app.manage(BrainSidecar::empty_borrowed());
    return;
  }

  if ws_up() {
    eprintln!("[qi] {WS_PROBE} 已在听：沿用现有大脑，不重复拉起");
    app.manage(BrainSidecar::empty_borrowed());
    return;
  }

  match spawn_brain(app) {
    Ok(mut child) => {
      let pid = child.id();
      eprintln!("[qi] 已拉起大脑子进程 pid={pid}，等待 {WS_PROBE} …");
      match wait_for_ws_or_exit(&mut child, WS_READY_TIMEOUT) {
        WaitOutcome::Ready => {
          eprintln!("[qi] 大脑通道已就绪（退出壳时会结束子进程）");
          app.manage(BrainSidecar::owned(child));
        }
        WaitOutcome::Exited(status) => {
          eprintln!("[qi] 大脑子进程提前退出：{status}");
          eprintln!("[qi] 可手动运行：qi  或  python -m qi；或先 python tools/build_qi_brain.py");
          app.manage(BrainSidecar::empty_borrowed());
        }
        WaitOutcome::Timeout => {
          eprintln!(
            "[qi] {WS_PROBE} 在 {}s 内未就绪；窗口照常打开，前端会重连",
            WS_READY_TIMEOUT.as_secs()
          );
          app.manage(BrainSidecar::owned(child));
        }
      }
    }
    Err(err) => {
      eprintln!("[qi] 拉起大脑失败：{err}");
      eprintln!("[qi] 可手动运行：qi  或  python -m qi");
      eprintln!("[qi] 或设置 QI_BRAIN_EXE / QI_PYTHON / QI_ROOT；跳过则 QI_SKIP_BRAIN=1");
      app.manage(BrainSidecar::empty_borrowed());
    }
  }
}

pub fn on_run_event(app: &AppHandle, event: &RunEvent) {
  if !matches!(event, RunEvent::Exit) {
    return;
  }
  let Some(state) = app.try_state::<BrainSidecar>() else {
    return;
  };
  shutdown(&state);
}

fn shutdown(state: &State<'_, BrainSidecar>) {
  if state.borrowed {
    return;
  }
  let Ok(mut guard) = state.child.lock() else {
    return;
  };
  let Some(mut child) = guard.take() else {
    return;
  };
  let pid = child.id();
  eprintln!("[qi] 结束大脑子进程 pid={pid}");
  kill_child(&mut child);
}

fn skip_requested() -> bool {
  matches!(
    std::env::var("QI_SKIP_BRAIN").ok().as_deref(),
    Some("1") | Some("true") | Some("TRUE") | Some("yes") | Some("YES")
  )
}

/// 探 9527 是否已在听 WebSocket。
/// 必须走完整握手：空 TCP 连上即断会被 websockets 打成 `opening handshake failed` ERROR。
fn ws_up() -> bool {
  use std::io::{Read, Write};

  let addr = WS_PROBE.parse().expect("static addr");
  let mut stream = match TcpStream::connect_timeout(&addr, Duration::from_millis(200)) {
    Ok(s) => s,
    Err(_) => return false,
  };
  let _ = stream.set_read_timeout(Some(Duration::from_millis(400)));
  let _ = stream.set_write_timeout(Some(Duration::from_millis(200)));

  // RFC6455 示例 key；服务端验的是格式，不要求我们真的继续帧交换
  let req = concat!(
    "GET / HTTP/1.1\r\n",
    "Host: 127.0.0.1:9527\r\n",
    "Upgrade: websocket\r\n",
    "Connection: Upgrade\r\n",
    "Sec-WebSocket-Key: dGhlIHNhbXBsZSBub25jZQ==\r\n",
    "Sec-WebSocket-Version: 13\r\n",
    "\r\n",
  );
  if stream.write_all(req.as_bytes()).is_err() {
    return false;
  }

  let mut buf = [0u8; 256];
  let n = match stream.read(&mut buf) {
    Ok(n) if n > 0 => n,
    _ => return false,
  };
  let head = String::from_utf8_lossy(&buf[..n]);
  head.starts_with("HTTP/1.1 101") || head.starts_with("HTTP/1.0 101")
}

enum WaitOutcome {
  Ready,
  Timeout,
  Exited(std::process::ExitStatus),
}

fn wait_for_ws_or_exit(child: &mut Child, timeout: Duration) -> WaitOutcome {
  let deadline = Instant::now() + timeout;
  while Instant::now() < deadline {
    if ws_up() {
      return WaitOutcome::Ready;
    }
    match child.try_wait() {
      Ok(Some(status)) => return WaitOutcome::Exited(status),
      Ok(None) => {}
      Err(err) => {
        eprintln!("[qi] 探测子进程失败：{err}");
        return WaitOutcome::Timeout;
      }
    }
    thread::sleep(Duration::from_millis(250));
  }
  if ws_up() {
    WaitOutcome::Ready
  } else {
    WaitOutcome::Timeout
  }
}

fn spawn_brain(app: &AppHandle) -> Result<Child, String> {
  if let Some(exe) = find_bundled_brain(app) {
    return spawn_bundled(&exe);
  }
  spawn_repo_python()
}

fn spawn_bundled(exe: &Path) -> Result<Child, String> {
  let cwd = exe.parent().unwrap_or(exe);
  let mut cmd = Command::new(exe);
  cmd.current_dir(cwd)
    .env("PYTHONUNBUFFERED", "1")
    .stdin(Stdio::null())
    .stdout(Stdio::inherit())
    .stderr(Stdio::inherit());

  eprintln!(
    "[qi] 启动 bundled 大脑：{}（cwd={}）",
    exe.display(),
    cwd.display()
  );

  cmd.spawn()
    .map_err(|e| format!("{}：{e}", exe.display()))
}

fn spawn_repo_python() -> Result<Child, String> {
  let root = find_repo_root().ok_or_else(|| {
    String::from(
      "找不到 bundled qi-brain，也找不到仓库根（缺 pyproject.toml）。\
       请先 python tools/build_qi_brain.py，或设 QI_ROOT / QI_BRAIN_EXE",
    )
  })?;
  let (python, prefix_args) = find_python(&root)?;

  let mut cmd = Command::new(&python);
  cmd.args(&prefix_args)
    .args(["-m", "qi"])
    .current_dir(&root)
    .env("PYTHONUNBUFFERED", "1")
    .stdin(Stdio::null())
    .stdout(Stdio::inherit())
    .stderr(Stdio::inherit());

  eprintln!(
    "[qi] 启动大脑：{} {:?} -m qi（cwd={}）",
    python.display(),
    prefix_args,
    root.display()
  );

  cmd.spawn()
    .map_err(|e| format!("{}：{e}", python.display()))
}

fn brain_exe_name() -> &'static str {
  if cfg!(windows) {
    "qi-brain.exe"
  } else {
    "qi-brain"
  }
}

fn find_bundled_brain(app: &AppHandle) -> Option<PathBuf> {
  if let Ok(custom) = std::env::var("QI_BRAIN_EXE") {
    let p = PathBuf::from(&custom);
    if p.is_file() {
      return Some(p);
    }
    eprintln!("[qi] QI_BRAIN_EXE 不存在：{custom}");
  }

  let name = brain_exe_name();
  let mut candidates: Vec<PathBuf> = Vec::new();

  if let Ok(resource_dir) = app.path().resource_dir() {
    candidates.push(resource_dir.join("qi-brain").join(name));
    candidates.push(resource_dir.join(name));
  }

  if let Ok(exe) = std::env::current_exe() {
    if let Some(dir) = exe.parent() {
      candidates.push(dir.join("qi-brain").join(name));
      candidates.push(dir.join("resources").join("qi-brain").join(name));
    }
  }

  // tauri:dev：资源尚未拷到 target 时，直接读 src-tauri/resources
  candidates.push(
    PathBuf::from(env!("CARGO_MANIFEST_DIR"))
      .join("resources")
      .join("qi-brain")
      .join(name),
  );

  for path in candidates {
    if path.is_file() {
      eprintln!("[qi] 发现 bundled 大脑：{}", path.display());
      return Some(path);
    }
  }
  None
}

fn find_repo_root() -> Option<PathBuf> {
  if let Ok(root) = std::env::var("QI_ROOT") {
    let p = PathBuf::from(root);
    if is_repo_root(&p) {
      return Some(p);
    }
  }

  let mut starts = Vec::new();
  if let Ok(exe) = std::env::current_exe() {
    starts.push(exe);
  }
  starts.push(PathBuf::from(env!("CARGO_MANIFEST_DIR")));

  for start in starts {
    let mut dir = start;
    if dir.is_file() {
      dir.pop();
    }
    for _ in 0..10 {
      if is_repo_root(&dir) {
        return Some(dir);
      }
      if !dir.pop() {
        break;
      }
    }
  }
  None
}

fn is_repo_root(dir: &Path) -> bool {
  dir.join("pyproject.toml").is_file() && dir.join("qi").join("cli.py").is_file()
}

/// 返回 (可执行文件, 额外前置参数)，例如 `py` + `["-3"]`。
fn find_python(repo: &Path) -> Result<(PathBuf, Vec<String>), String> {
  if let Ok(custom) = std::env::var("QI_PYTHON") {
    let p = PathBuf::from(&custom);
    if p.exists() {
      return Ok((p, Vec::new()));
    }
    return Err(format!("QI_PYTHON 不存在：{custom}"));
  }

  let venv_win = repo.join(".venv").join("Scripts").join("python.exe");
  if venv_win.is_file() {
    return Ok((venv_win, Vec::new()));
  }
  let venv_unix = repo.join(".venv").join("bin").join("python");
  if venv_unix.is_file() {
    return Ok((venv_unix, Vec::new()));
  }

  if which_ok("python") {
    return Ok((PathBuf::from("python"), Vec::new()));
  }
  if which_ok("python3") {
    return Ok((PathBuf::from("python3"), Vec::new()));
  }
  // Windows launcher
  if cfg!(windows) && which_ok("py") {
    return Ok((PathBuf::from("py"), vec!["-3".into()]));
  }

  Err("找不到 Python（试过 .venv、python、python3、py）".into())
}

fn which_ok(name: &str) -> bool {
  Command::new(name)
    .arg("--version")
    .stdout(Stdio::null())
    .stderr(Stdio::null())
    .status()
    .map(|s| s.success())
    .unwrap_or(false)
}

fn kill_child(child: &mut Child) {
  #[cfg(windows)]
  {
    let pid = child.id();
    let _ = Command::new("taskkill")
      .args(["/PID", &pid.to_string(), "/T", "/F"])
      .stdout(Stdio::null())
      .stderr(Stdio::null())
      .status();
    let _ = child.wait();
    return;
  }
  #[cfg(not(windows))]
  {
    let _ = child.kill();
    let _ = child.wait();
  }
}
