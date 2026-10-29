#Requires AutoHotkey v2.0
#SingleInstance Force

; ==========================================
; CONFIGURATION (MASTER)
; ==========================================
; Update these to your actual paths!
PythonScriptPath := A_ScriptDir "\background_remover.py"
EOSUtilityPath   := "C:\Program Files (x86)\Canon\EOS Utility\EOS Utility 2.exe" 
WorkerScriptPath := A_ScriptDir "\photo-shooting-shortcuts.ahk"
SrcDir           := EnvGet("USERPROFILE") "\Pictures\canon-pics"
DestDir          := EnvGet("USERPROFILE") "\Pictures\canon-pics-proccessed"


global PythonPID := 0
global WorkerPID := 0

; ==========================================
; LAUNCH SEQUENCE
; ==========================================

; 1. Start Python Background Remover
try {
    Run("python.exe `"" PythonScriptPath "`" --src `"" SrcDir "`" --dest `"" DestDir "`"", , "Min", &PythonPID)
} catch {
    MsgBox("Failed to start Python script.")
}

; 2. Start the AHK Hotkey Worker
try {
    Run("`"" A_AhkPath "`" `"" WorkerScriptPath "`"", , , &WorkerPID)
} catch {
    MsgBox("Failed to start the Studio Hotkeys script.")
}

; 3. Start EOS Utility
if !WinExist("ahk_exe EOS Utility 2.exe") and !WinExist("ahk_exe EOS Utility.exe") {
    try {
        Run(EOSUtilityPath)
    } catch {
        MsgBox("Could not find EOS Utility. Please check the path.")
    }
}

; ==========================================
; FLOATING CONTROL PANEL (GUI)
; ==========================================

StudioGui := Gui("+AlwaysOnTop -MaximizeBox -MinimizeBox", "סטודיו")
StudioGui.MarginX := 15
StudioGui.MarginY := 15

; "Ready to Shoot" Text
StudioGui.SetFont("s16 c008000 bold", "Segoe UI") ; Green, bold font
StudioGui.Add("Text", "w200 Center", "מוכן לצילום")

; Quit Button
StudioGui.SetFont("s12 cBlack norm", "Segoe UI")
QuitBtn := StudioGui.Add("Button", "w200 h45 y+15", "סגור מערכת (Quit)")

; When the button is clicked, exit the script (this triggers CleanupOnExit)
QuitBtn.OnEvent("Click", (*) => ExitApp())

; Show the GUI in the bottom right corner without stealing focus from the camera app

; 1. Show the GUI invisibly first so AHK calculates its final width and height
StudioGui.Show("Hide")
StudioGui.GetPos(,, &GuiWidth, &GuiHeight)

; 2. Get the primary monitor's working area (this safely excludes the Windows taskbar)
MonitorGetWorkArea(1, &WorkLeft, &WorkTop, &WorkRight, &WorkBottom)

; 3. Calculate the bottom-right coordinates (adding a 15-pixel breathing room margin)
PosX := WorkRight - GuiWidth - 15
PosY := WorkBottom - GuiHeight - 15

; 4. Show the GUI at the calculated coordinates without stealing focus
StudioGui.Show("NoActivate x" PosX " y" PosY)


; ==========================================
; MONITOR & SHUTDOWN SEQUENCE
; ==========================================

OnExit(CleanupOnExit)
SetTimer(WatchMainProgram, 2000)

WatchMainProgram() {
    ; If EOS Utility is completely closed, trigger the exit
    if !WinExist("ahk_exe EOS Utility 2.exe") and !WinExist("ahk_exe EOS Utility.exe") {
        ExitApp()
    }
}

CleanupOnExit(ExitReason, ExitCode) {
    ; Kill Python
    if (PythonPID) {
        try ProcessClose(PythonPID)
    }
    
    ; Kill the AHK Worker script
    if (WorkerPID) {
        try ProcessClose(WorkerPID)
    }
    
    ; Ensure Canon is closed 
    if WinExist("ahk_exe EOS Utility 2.exe") {
        try WinClose("ahk_exe EOS Utility 2.exe")
    }
    if WinExist("ahk_exe EOS Utility.exe") {
        try WinClose("ahk_exe EOS Utility.exe")
    }
}