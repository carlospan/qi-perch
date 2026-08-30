mod brain_sidecar;

use tauri::{
  menu::{Menu, MenuItem},
  tray::{MouseButton, MouseButtonState, TrayIconBuilder, TrayIconEvent},
  Manager, WindowEvent,
};

fn show_main(app: &tauri::AppHandle) {
  if let Some(window) = app.get_webview_window("main") {
    let _ = window.show();
    let _ = window.unminimize();
    let _ = window.set_focus();
  }
}

#[cfg_attr(mobile, tauri::mobile_entry_point)]
pub fn run() {
  tauri::Builder::default()
    .setup(|app| {
      brain_sidecar::attach(app.handle());

      let open = MenuItem::with_id(app, "open", "打开栖", true, None::<&str>)?;
      let quit = MenuItem::with_id(app, "quit", "退出栖", true, None::<&str>)?;
      let menu = Menu::with_items(app, &[&open, &quit])?;

      let icon = app
        .default_window_icon()
        .cloned()
        .expect("default window icon required for tray");

      let _tray = TrayIconBuilder::with_id("qi-tray")
        .icon(icon)
        .tooltip("栖")
        .menu(&menu)
        .show_menu_on_left_click(false)
        .on_menu_event(|app, event| match event.id.as_ref() {
          "open" => show_main(app),
          "quit" => {
            // 触发 RunEvent::Exit → brain_sidecar 仅收自拉起的大脑
            app.exit(0);
          }
          _ => {}
        })
        .on_tray_icon_event(|tray, event| {
          if let TrayIconEvent::Click {
            button: MouseButton::Left,
            button_state: MouseButtonState::Up,
            ..
          } = event
          {
            show_main(tray.app_handle());
          }
        })
        .build(app)?;

      Ok(())
    })
    .on_window_event(|window, event| {
      if let WindowEvent::CloseRequested { api, .. } = event {
        // 关主窗 = 藏到托盘，不退壳、不杀后端
        let _ = window.hide();
        api.prevent_close();
      }
    })
    .build(tauri::generate_context!())
    .expect("error while building tauri application")
    .run(|app_handle, event| {
      brain_sidecar::on_run_event(app_handle, &event);
    });
}
