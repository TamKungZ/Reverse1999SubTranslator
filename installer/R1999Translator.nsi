Unicode true

!include "MUI2.nsh"
!include "LogicLib.nsh"
!include "FileFunc.nsh"
!insertmacro GetSize
!insertmacro GetFileName

!ifndef VERSION
  !define VERSION "1.0.0"
!endif
!ifndef OUTFILE
  !define OUTFILE "..\dist\R1999Translator-Setup-${VERSION}.exe"
!endif
!ifndef DATA_DIR
  !define DATA_DIR "$APPDATA\R1999Translator"
!endif

!define NAME "R1999 Translator"
!define EXE "R1999Translator.exe"
!define ENGINE_EXE "r1999-engine.exe"
!define APP_DIR_NAME "R1999Translator"
!define PUBLISHER "TamKungZ_"
!define EMAIL "dev@tamkungz.me"
!define URL "https://github.com/TamKungZ/Reverse1999SubTranslator"
!define SETTINGS_KEY "Software\R1999Translator"
!define UNINSTALL_KEY "Software\Microsoft\Windows\CurrentVersion\Uninstall\R1999Translator"
!define SOURCE "..\dist\R1999Translator"

Name "${NAME}"
OutFile "${OUTFILE}"
InstallDir "$LOCALAPPDATA\Programs\${APP_DIR_NAME}"
InstallDirRegKey HKCU "${SETTINGS_KEY}" "InstallDir"
RequestExecutionLevel user
SetCompressor /SOLID lzma
BrandingText "${PUBLISHER}"

!define MUI_ICON "..\ui\r1999ui\assets\icon.ico"
!define MUI_UNICON "..\ui\r1999ui\assets\icon.ico"
!define MUI_ABORTWARNING
!define MUI_FINISHPAGE_RUN "$INSTDIR\${EXE}"
!define MUI_PAGE_CUSTOMFUNCTION_LEAVE DirLeave

!insertmacro MUI_PAGE_WELCOME
!insertmacro MUI_PAGE_LICENSE "..\LICENSE"
!insertmacro MUI_PAGE_COMPONENTS
!insertmacro MUI_PAGE_DIRECTORY
!insertmacro MUI_PAGE_INSTFILES
!insertmacro MUI_PAGE_FINISH

!insertmacro MUI_UNPAGE_CONFIRM
!insertmacro MUI_UNPAGE_INSTFILES

!insertmacro MUI_LANGUAGE "English"
!insertmacro MUI_LANGUAGE "Thai"

LangString SectionProgram ${LANG_ENGLISH} "${NAME} (required)"
LangString SectionProgram ${LANG_THAI} "${NAME} (จำเป็น)"
LangString SectionDesktop ${LANG_ENGLISH} "Desktop shortcut"
LangString SectionDesktop ${LANG_THAI} "ทางลัดบนเดสก์ท็อป"
LangString BadDir ${LANG_ENGLISH} "The install folder cannot be inside ${DATA_DIR}, which holds your settings and models. Choose another folder."
LangString BadDir ${LANG_THAI} "ไม่สามารถติดตั้งในโฟลเดอร์ ${DATA_DIR} ซึ่งเก็บการตั้งค่าและโมเดลของคุณได้ กรุณาเลือกโฟลเดอร์อื่น"
LangString NotInstalled ${LANG_ENGLISH} "${NAME} was not found in this folder. Nothing was removed."
LangString NotInstalled ${LANG_THAI} "ไม่พบ ${NAME} ในโฟลเดอร์นี้ จึงไม่มีอะไรถูกลบ"
LangString DeleteData ${LANG_ENGLISH} "Also delete the settings and downloaded models in ${DATA_DIR}?"
LangString DeleteData ${LANG_THAI} "ลบการตั้งค่าและโมเดลที่ดาวน์โหลดไว้ใน ${DATA_DIR} ด้วยหรือไม่?"

VIProductVersion "${VERSION}.0"
!macro VersionInfo LANG
  VIAddVersionKey /LANG=${LANG} "ProductName" "${NAME}"
  VIAddVersionKey /LANG=${LANG} "CompanyName" "${PUBLISHER}"
  VIAddVersionKey /LANG=${LANG} "LegalCopyright" "Copyright (c) 2026 ${PUBLISHER}"
  VIAddVersionKey /LANG=${LANG} "FileDescription" "${NAME} Setup"
  VIAddVersionKey /LANG=${LANG} "FileVersion" "${VERSION}"
  VIAddVersionKey /LANG=${LANG} "ProductVersion" "${VERSION}"
!macroend
!insertmacro VersionInfo ${LANG_ENGLISH}
!insertmacro VersionInfo ${LANG_THAI}

!macro CloseRunning PREFIX
  Function ${PREFIX}CloseRunning
    nsExec::Exec 'taskkill /F /IM ${EXE} /IM ${ENGINE_EXE}'
    Pop $0
    Sleep 800
  FunctionEnd
!macroend
!insertmacro CloseRunning ""
!insertmacro CloseRunning "un."

; Everything is installed into a folder named R1999Translator of its own, so that removing the program
; never touches files the user keeps next to it, and never the engine folder of the user data.
Function NormalizeInstDir
  StrCpy $0 "$INSTDIR" 1 -1
  ${If} $0 == "\"
    StrCpy $INSTDIR "$INSTDIR" -1
  ${EndIf}
  ${GetFileName} "$INSTDIR" $0
  ${If} $0 != "${APP_DIR_NAME}"
    StrCpy $INSTDIR "$INSTDIR\${APP_DIR_NAME}"
  ${EndIf}
FunctionEnd

Function ValidateInstDir
  Call NormalizeInstDir
  StrLen $0 "${DATA_DIR}"
  StrCpy $1 "$INSTDIR" $0
  StrCpy $2 "$INSTDIR" 1 $0
  ${If} $1 == "${DATA_DIR}"
    ${If} $2 == ""
    ${OrIf} $2 == "\"
      MessageBox MB_OK|MB_ICONSTOP "$(BadDir)" /SD IDOK
      Abort
    ${EndIf}
  ${EndIf}
FunctionEnd

Function .onInit
  Call ValidateInstDir
FunctionEnd

Function DirLeave
  Call ValidateInstDir
FunctionEnd

Section "$(SectionProgram)" SecProgram
  SectionIn RO
  Call CloseRunning

  ; remove what an earlier version installed, by name, nothing else
  RMDir /r "$INSTDIR\_internal"
  RMDir /r "$INSTDIR\engine\_internal"
  Delete "$INSTDIR\engine\${ENGINE_EXE}"
  RMDir "$INSTDIR\engine"

  SetOutPath "$INSTDIR"
  File /r "${SOURCE}\*.*"
  File "..\LICENSE"
  WriteUninstaller "$INSTDIR\Uninstall.exe"

  CreateDirectory "$SMPROGRAMS\${NAME}"
  CreateShortcut "$SMPROGRAMS\${NAME}\${NAME}.lnk" "$INSTDIR\${EXE}"
  CreateShortcut "$SMPROGRAMS\${NAME}\Uninstall.lnk" "$INSTDIR\Uninstall.exe"

  WriteRegStr HKCU "${SETTINGS_KEY}" "InstallDir" "$INSTDIR"
  WriteRegStr HKCU "${UNINSTALL_KEY}" "DisplayName" "${NAME}"
  WriteRegStr HKCU "${UNINSTALL_KEY}" "DisplayVersion" "${VERSION}"
  WriteRegStr HKCU "${UNINSTALL_KEY}" "Publisher" "${PUBLISHER}"
  WriteRegStr HKCU "${UNINSTALL_KEY}" "Contact" "${EMAIL}"
  WriteRegStr HKCU "${UNINSTALL_KEY}" "URLInfoAbout" "${URL}"
  WriteRegStr HKCU "${UNINSTALL_KEY}" "DisplayIcon" "$INSTDIR\${EXE}"
  WriteRegStr HKCU "${UNINSTALL_KEY}" "InstallLocation" "$INSTDIR"
  WriteRegStr HKCU "${UNINSTALL_KEY}" "UninstallString" '"$INSTDIR\Uninstall.exe"'
  WriteRegStr HKCU "${UNINSTALL_KEY}" "QuietUninstallString" '"$INSTDIR\Uninstall.exe" /S'
  WriteRegDWORD HKCU "${UNINSTALL_KEY}" "NoModify" 1
  WriteRegDWORD HKCU "${UNINSTALL_KEY}" "NoRepair" 1
  ${GetSize} "$INSTDIR" "/S=0K" $0 $1 $2
  WriteRegDWORD HKCU "${UNINSTALL_KEY}" "EstimatedSize" $0
SectionEnd

Section /o "$(SectionDesktop)" SecDesktop
  CreateShortcut "$DESKTOP\${NAME}.lnk" "$INSTDIR\${EXE}"
SectionEnd

Section "Uninstall"
  ${IfNot} ${FileExists} "$INSTDIR\${EXE}"
    MessageBox MB_OK|MB_ICONSTOP "$(NotInstalled)" /SD IDOK
    Abort
  ${EndIf}
  Call un.CloseRunning

  RMDir /r "$INSTDIR\_internal"
  RMDir /r "$INSTDIR\engine\_internal"
  Delete "$INSTDIR\engine\${ENGINE_EXE}"
  RMDir "$INSTDIR\engine"
  Delete "$INSTDIR\${EXE}"
  Delete "$INSTDIR\LICENSE"
  Delete "$INSTDIR\Uninstall.exe"
  RMDir "$INSTDIR"

  Delete "$SMPROGRAMS\${NAME}\${NAME}.lnk"
  Delete "$SMPROGRAMS\${NAME}\Uninstall.lnk"
  RMDir "$SMPROGRAMS\${NAME}"
  Delete "$DESKTOP\${NAME}.lnk"

  DeleteRegKey HKCU "${UNINSTALL_KEY}"
  DeleteRegKey HKCU "${SETTINGS_KEY}"

  ${IfNot} ${Silent}
    MessageBox MB_YESNO|MB_ICONQUESTION|MB_DEFBUTTON2 "$(DeleteData)" IDNO keep_data
    RMDir /r "${DATA_DIR}"
    keep_data:
  ${EndIf}
SectionEnd
