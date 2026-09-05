//! 拉起 Python 大脑：bundled `qi-brain`（安装布局）或仓库 `python -m qi`（开发）。
//!
//! 选脑优先级（P3 sidecar）：
//! 1. 9527 已在听 → 沿用（borrowed，退出不杀）
//! 2. **debug（`tauri:dev`）**：优先仓库根 `python -m qi`（数据根走仓库 `data/`）；
//!    失败再回退 bundled。要强制测 bundled 时设 `QI_PREFER_BUNDLED=1`。
//! 3. **release / 安装壳**：完整 onedir / 已解压 runtime / `qi-brain.zip` 解压 → 起它
//! 4. 否则仓库根 `python -m qi`
//! 5. 失败 → 日志提示（前端走既有连接失败可见路径）
//!
//! 退出策略（P2 托盘）：仅在壳 **自己拉起** 大脑时，于 `RunEvent::Exit`（「退出栖」）结束子进程；
//! 沿用已在听的后端（borrowed）不杀。关主窗藏托盘不会走到 Exit。
//!
//! 安装包只带 `qi-brain.zip`（避免 NSIS 数千文件落半套）；解压到 `%LOCALAPPDATA%/Qi/runtime/qi-brain`。

use std::fs;
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
const STAMP_NAME: &str = ".qi-brain-stamp";
const NUMPY_CORE_REL: &[&str] = &["_internal", "numpy", "_core"];

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
  // tauri:dev：优先仓库 Python，这样 resolve_data_root → PROJECT_ROOT/data，
  // 避免误连安装包留下的 %LOCALAPPDATA%/Qi。
  if prefer_repo_brain() {
    match spawn_repo_python() {
      Ok(child) => return Ok(child),
      Err(err) => {
        eprintln!("[qi] 开发优先仓库大脑失败，回退 bundled：{err}");
      }
    }
  }
  if let Some(exe) = resolve_bundled_brain(app)? {
    return spawn_bundled(&exe);
  }
  spawn_repo_python()
}

fn prefer_repo_brain() -> bool {
  if prefer_bundled_requested() {
    return false;
  }
  cfg!(debug_assertions)
}

fn prefer_bundled_requested() -> bool {
  matches!(
    std::env::var("QI_PREFER_BUNDLED").ok().as_deref(),
    Some("1") | Some("true") | Some("TRUE") | Some("yes") | Some("YES")
  )
}

fn spawn_bundled(exe: &Path) -> Result<Child, String> {
  let cwd = exe.parent().unwrap_or(exe);
  let mut cmd = Command::new(exe);
  cmd.current_dir(cwd)
    .env("PYTHONUNBUFFERED", "1")
    .stdin(Stdio::null())
    .stdout(Stdio::null())
    .stderr(Stdio::null());
  apply_no_console(&mut cmd);

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
    .stdout(Stdio::null())
    .stderr(Stdio::null());
  apply_no_console(&mut cmd);

  eprintln!(
    "[qi] 启动大脑：{} {:?} -m qi（cwd={}）",
    python.display(),
    prefix_args,
    root.display()
  );

  cmd.spawn()
    .map_err(|e| format!("{}：{e}", python.display()))
}

/// Windows：子进程不弹控制台黑窗（安装壳体验）。
fn apply_no_console(cmd: &mut Command) {
  #[cfg(windows)]
  {
    use std::os::windows::process::CommandExt;
    const CREATE_NO_WINDOW: u32 = 0x0800_0000;
    cmd.creation_flags(CREATE_NO_WINDOW);
  }
  let _ = cmd;
}

fn brain_exe_name() -> &'static str {
  if cfg!(windows) {
    "qi-brain.exe"
  } else {
    "qi-brain"
  }
}

/// 解析可用的 bundled 大脑 exe；缺完整性则拒绝半套树。
fn resolve_bundled_brain(app: &AppHandle) -> Result<Option<PathBuf>, String> {
  if let Ok(custom) = std::env::var("QI_BRAIN_EXE") {
    let p = PathBuf::from(&custom);
    if p.is_file() {
      let dir = p.parent().unwrap_or(Path::new("."));
      if brain_tree_complete(dir) {
        return Ok(Some(p));
      }
      return Err(format!(
        "QI_BRAIN_EXE 指向的大脑不完整（缺 numpy._core 扩展）：{}",
        dir.display()
      ));
    }
    eprintln!("[qi] QI_BRAIN_EXE 不存在：{custom}");
  }

  let name = brain_exe_name();

  // 1) 现成完整 onedir（开发 resources / 旧安装布局）
  for dir in candidate_brain_dirs(app) {
    let exe = dir.join(name);
    if exe.is_file() {
      if brain_tree_complete(&dir) {
        eprintln!("[qi] 发现完整 bundled 大脑：{}", exe.display());
        return Ok(Some(exe));
      }
      eprintln!(
        "[qi] 跳过不完整大脑树（缺 numpy 扩展）：{}",
        dir.display()
      );
    }
  }

  // 2) zip → %LOCALAPPDATA%/Qi/runtime/qi-brain
  let Some(zip_path) = find_brain_zip(app) else {
    return Ok(None);
  };
  let dest = runtime_brain_dir()?;
  ensure_extracted_brain(&zip_path, &dest)?;
  let exe = dest.join(name);
  if !exe.is_file() {
    return Err(format!("解压后仍无 {}", exe.display()));
  }
  if !brain_tree_complete(&dest) {
    return Err(format!(
      "解压后大脑仍缺 numpy._core 扩展：{}",
      dest.display()
    ));
  }
  eprintln!("[qi] 使用解压后的大脑：{}", exe.display());
  Ok(Some(exe))
}

fn candidate_brain_dirs(app: &AppHandle) -> Vec<PathBuf> {
  let mut dirs = Vec::new();
  if let Ok(resource_dir) = app.path().resource_dir() {
    dirs.push(resource_dir.join("qi-brain"));
    dirs.push(resource_dir);
  }
  if let Ok(exe) = std::env::current_exe() {
    if let Some(dir) = exe.parent() {
      dirs.push(dir.join("qi-brain"));
      dirs.push(dir.join("resources").join("qi-brain"));
    }
  }
  // tauri:dev：资源尚未拷到 target 时，直接读 src-tauri/resources
  dirs.push(
    PathBuf::from(env!("CARGO_MANIFEST_DIR"))
      .join("resources")
      .join("qi-brain"),
  );
  // runtime 解压目录不走这里：须经 zip stamp 校验后再用
  dirs
}

fn find_brain_zip(app: &AppHandle) -> Option<PathBuf> {
  let mut candidates = Vec::new();
  if let Ok(resource_dir) = app.path().resource_dir() {
    candidates.push(resource_dir.join("qi-brain.zip"));
  }
  if let Ok(exe) = std::env::current_exe() {
    if let Some(dir) = exe.parent() {
      candidates.push(dir.join("resources").join("qi-brain.zip"));
      candidates.push(dir.join("qi-brain.zip"));
    }
  }
  candidates.push(
    PathBuf::from(env!("CARGO_MANIFEST_DIR"))
      .join("resources")
      .join("qi-brain.zip"),
  );
  for path in candidates {
    if path.is_file() {
      eprintln!("[qi] 发现大脑 zip：{}", path.display());
      return Some(path);
    }
  }
  None
}

fn runtime_brain_dir() -> Result<PathBuf, String> {
  let base = platform_qi_data_root()?;
  Ok(base.join("runtime").join("qi-brain"))
}

fn platform_qi_data_root() -> Result<PathBuf, String> {
  #[cfg(windows)]
  {
    let local = std::env::var("LOCALAPPDATA").map_err(|_| {
      String::from("缺少 LOCALAPPDATA，无法解压 qi-brain")
    })?;
    return Ok(PathBuf::from(local).join("Qi"));
  }
  #[cfg(target_os = "macos")]
  {
    let home = dirs_home()?;
    return Ok(home.join("Library").join("Application Support").join("Qi"));
  }
  #[cfg(all(unix, not(target_os = "macos")))]
  {
    if let Ok(xdg) = std::env::var("XDG_DATA_HOME") {
      if !xdg.trim().is_empty() {
        return Ok(PathBuf::from(xdg).join("Qi"));
      }
    }
    let home = dirs_home()?;
    return Ok(home.join(".local").join("share").join("Qi"));
  }
  #[cfg(not(any(windows, unix)))]
  {
    Err(String::from("当前平台不支持解压 bundled qi-brain"))
  }
}

#[cfg(unix)]
fn dirs_home() -> Result<PathBuf, String> {
  std::env::var_os("HOME")
    .map(PathBuf::from)
    .ok_or_else(|| String::from("缺少 HOME"))
}

fn brain_tree_complete(dir: &Path) -> bool {
  let exe = dir.join(brain_exe_name());
  if !exe.is_file() {
    return false;
  }
  let mut core = dir.to_path_buf();
  for part in NUMPY_CORE_REL {
    core.push(part);
  }
  if !core.is_dir() {
    return false;
  }
  match fs::read_dir(&core) {
    Ok(entries) => entries.filter_map(|e| e.ok()).any(|e| {
      let name = e.file_name();
      let s = name.to_string_lossy();
      let s = s.as_ref();
      s.starts_with("_multiarray_umath")
        && (s.ends_with(".pyd") || s.ends_with(".so") || s.ends_with(".dylib"))
    }),
    Err(_) => false,
  }
}

fn zip_stamp(zip_path: &Path) -> Result<String, String> {
  let meta = fs::metadata(zip_path).map_err(|e| format!("读 zip 元数据失败：{e}"))?;
  let modified = meta
    .modified()
    .ok()
    .and_then(|t| t.duration_since(std::time::UNIX_EPOCH).ok())
    .map(|d| d.as_secs())
    .unwrap_or(0);
  Ok(format!("{}:{}", meta.len(), modified))
}

fn ensure_extracted_brain(zip_path: &Path, dest: &Path) -> Result<(), String> {
  let stamp = zip_stamp(zip_path)?;
  let stamp_file = dest.join(STAMP_NAME);
  if brain_tree_complete(dest) {
    if let Ok(existing) = fs::read_to_string(&stamp_file) {
      if existing.trim() == stamp {
        eprintln!("[qi] runtime 大脑已是最新：{}", dest.display());
        return Ok(());
      }
    }
  }

  eprintln!(
    "[qi] 解压大脑 zip → {} （首次或更新，可能需数十秒）…",
    dest.display()
  );
  if dest.exists() {
    fs::remove_dir_all(dest).map_err(|e| format!("清理旧 runtime 失败：{e}"))?;
  }
  fs::create_dir_all(dest).map_err(|e| format!("创建 runtime 目录失败：{e}"))?;
  extract_zip(zip_path, dest)?;
  if !brain_tree_complete(dest) {
    let _ = fs::remove_dir_all(dest);
    return Err(format!(
      "解压结果不完整（缺 numpy._core._multiarray_umath*.pyd）：{}",
      dest.display()
    ));
  }
  fs::write(&stamp_file, format!("{stamp}\n")).map_err(|e| format!("写 stamp 失败：{e}"))?;
  eprintln!("[qi] 大脑解压完成");
  Ok(())
}

fn extract_zip(zip_path: &Path, dest: &Path) -> Result<(), String> {
  // Windows：用系统 Expand-Archive，避免再引 zip crate（离线/代理环境友好）
  #[cfg(windows)]
  {
    let mut cmd = Command::new("powershell.exe");
    cmd.args([
      "-NoProfile",
      "-NonInteractive",
      "-WindowStyle",
      "Hidden",
      "-ExecutionPolicy",
      "Bypass",
      "-Command",
      "Expand-Archive -LiteralPath $env:QI_BRAIN_ZIP -DestinationPath $env:QI_BRAIN_DEST -Force",
    ])
    .env("QI_BRAIN_ZIP", zip_path)
    .env("QI_BRAIN_DEST", dest)
    .stdin(Stdio::null())
    .stdout(Stdio::null())
    .stderr(Stdio::piped());
    apply_no_console(&mut cmd);
    let output = cmd
      .output()
      .map_err(|e| format!("启动 PowerShell 解压失败：{e}"))?;
    if !output.status.success() {
      let err = String::from_utf8_lossy(&output.stderr);
      return Err(format!(
        "Expand-Archive 失败：{} {}",
        output.status,
        err.trim()
      ));
    }
    return Ok(());
  }
  #[cfg(not(windows))]
  {
    let _ = (zip_path, dest);
    Err(String::from("非 Windows 暂不支持从 zip 解压 qi-brain"))
  }
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
  let mut cmd = Command::new(name);
  cmd.arg("--version")
    .stdin(Stdio::null())
    .stdout(Stdio::null())
    .stderr(Stdio::null());
  apply_no_console(&mut cmd);
  cmd.status().map(|s| s.success()).unwrap_or(false)
}

fn kill_child(child: &mut Child) {
  #[cfg(windows)]
  {
    let pid = child.id();
    // 先立刻杀主进程，避免壳卡在 taskkill 上「等好一会儿才闪一下再退」
    let _ = child.kill();
    // 进程树清扫：后台跑、不阻塞 Exit；CREATE_NO_WINDOW 防黑控制台
    let mut cmd = Command::new("taskkill");
    cmd.args(["/PID", &pid.to_string(), "/T", "/F"])
      .stdin(Stdio::null())
      .stdout(Stdio::null())
      .stderr(Stdio::null());
    apply_no_console(&mut cmd);
    let _ = cmd.spawn();
    // 主进程已被 kill，wait 应很快返回；勿再同步等 taskkill
    let _ = child.wait();
    return;
  }
  #[cfg(not(windows))]
  {
    let _ = child.kill();
    let _ = child.wait();
  }
}
