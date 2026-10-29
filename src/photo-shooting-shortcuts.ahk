#Requires AutoHotkey v2.0
#SingleInstance Force

; ==========================================
; CONFIGURATION
; ==========================================
TargetFolder := EnvGet("USERPROFILE") "\Pictures\canon-pics"
global CurrentFileName := "1" 

; ==========================================
; HOTKEYS (Ctrl + 0 to Ctrl + 9)
; ==========================================

$^0::CapturePhoto(0)
$^1::CapturePhoto(1)
$^2::CapturePhoto(2)
$^3::CapturePhoto(3)
$^4::CapturePhoto(4)
$^5::CapturePhoto(5)
$^6::CapturePhoto(6)
$^7::CapturePhoto(7)
$^8::CapturePhoto(8)
$^9::CapturePhoto(9)

; ==========================================
; MAIN LOGIC FUNCTION
; ==========================================

CapturePhoto(SuffixNum) {
    global CurrentFileName
    
    ; Determine the suffix string based on the hotkey pressed
    SuffixStr := (SuffixNum = 0) ? "" : "." SuffixNum
    MsgText := (SuffixNum = 0) ? "רגילה" : "תוספת " SuffixNum
    
    ToolTip("...מצלם תמונה " MsgText)
    OldNewest := GetNewestFile(TargetFolder)
    
    if FocusCameraApp() {
        Send("{Space}")
        if (NewFile := WaitForNewFile(TargetFolder, OldNewest)) {
            ToolTip()
            ib := InputBox("הזן שם קובץ:", "שמור תמונה", "w300 h130", CurrentFileName)
            if (ib.Result = "OK" && ib.Value != "") {
                CurrentFileName := ib.Value
                SplitPath(NewFile, , &OutDir, &OutExt)
                
                ; Apply the suffix (e.g., filename.1.jpg or just filename.jpg)
                NewPath := OutDir "\" CurrentFileName SuffixStr "." OutExt
                
                if SafeMove(NewFile, NewPath) {
                    ToolTip("נשמר: " CurrentFileName SuffixStr "." OutExt)
                    
                    ; OPTIONAL: Auto-increment logic
                    ; If you want a specific hotkey (e.g., Ctrl+9) to increase CurrentFileName for the NEXT item, 
                    ; you can add an 'if' statement here. For example:
                    ; if (SuffixNum = 9) {
                    ;     try CurrentFileName := String(Integer(CurrentFileName) + 1)
                    ; }
                }
            }
        } else {
            ToolTip("!שגיאה: הקובץ לא הגיע מהמצלמה")
        }
    }
    SetTimer(() => ToolTip(), -3000)
}

; ==========================================
; ROBUST HELPERS
; ==========================================

FocusCameraApp() {
    SetTitleMatchMode(2) 
    CanonWindows := ["Remote Live View window", "ahk_exe EOS Utility 2.exe", "Remote Shooting", "EOS Utility"]
    for WinName in CanonWindows {
        if WinExist(WinName) {
            WinActivate(WinName)
            Sleep(500)
            return true
        }
    }
    ToolTip("!שגיאה: לא מצאתי את חלון הצילום")
    return false
}

WaitForNewFile(Folder, OldFile) {
    Loop 150 { 
        CurrentNewest := GetNewestFile(Folder)
        if (CurrentNewest != "" && CurrentNewest != OldFile) {
            Sleep(1500) ; Wait for Canon to release the file lock
            return CurrentNewest
        }
        Sleep(100)
    }
    return ""
}

SafeMove(Source, Dest) {
    Loop 30 { 
        try {
            FileMove(Source, Dest, 1)
            return true
        } catch {
            Sleep(500)
        }
    }
    MsgBox("שגיאה קריטית: לא הצלחתי לשנות שם הקובץ. ייתכן שתוכנת קנון עדיין משתמשת בו, או שהקובץ פתוח בתוכנה אחרת.")
    return false
}

GetNewestFile(Folder) {
    LatestFile := ""
    LatestTime := 0
    Loop Files Folder "\*.*" {
        ; FILTER: Ignore temp files/folders. Only look at finalized images.
        if !(A_LoopFileExt ~= "i)^(jpg|jpeg|cr2|cr3|png)$")
            continue

        ; FIX: Use TimeModified instead of TimeCreated
        if (A_LoopFileTimeModified > LatestTime) {
            LatestTime := A_LoopFileTimeModified
            LatestFile := A_LoopFileFullPath
        }
    }
    return LatestFile
}