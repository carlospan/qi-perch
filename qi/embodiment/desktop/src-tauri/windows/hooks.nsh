; 安装/卸载前结束大脑与壳，避免 NSIS 覆盖半套 resources。
; 须用 ExecShellWait + SW_HIDE：裸 ExecWait taskkill 会闪黑控制台。
!macro _QiKillSideProcesses
  ExecShellWait "open" "$SYSDIR\taskkill.exe" "/F /IM qi-brain.exe /T" SW_HIDE
  ExecShellWait "open" "$SYSDIR\taskkill.exe" "/F /IM qi.exe /T" SW_HIDE
  Sleep 400
!macroend

!macro NSIS_HOOK_PREINSTALL
  !insertmacro _QiKillSideProcesses
!macroend

!macro NSIS_HOOK_PREUNINSTALL
  !insertmacro _QiKillSideProcesses
!macroend
