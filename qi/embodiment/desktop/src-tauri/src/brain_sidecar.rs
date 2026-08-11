//! 开发期把 Python 大脑（`python -m qi`）当作子进程拉起。
//! 正式打包 sidecar 另议；可用环境变量覆盖路径或跳过。

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

  match spawn_brain() {
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
          eprintln!("[qi] 可手动运行：qi  或  python -m qi");
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
      eprintln!("[qi] 或设置 QI_PYTHON / QI_ROOT；跳过则 QI_SKIP_BRAIN=1");
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

fn ws_up() -> bool {
  TcpStream::connect_timeout(
    &WS_PROBE.parse().expect("static addr"),
    Duration::from_millis(200),
  )
  .is_ok()
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

fn spawn_brain() -> Result<Child, String> {
  let root = find_repo_root().ok_or_else(|| {
    String::from("找不到仓库根（缺 pyproject.toml）。请设 QI_ROOT=仓库绝对路径")
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
