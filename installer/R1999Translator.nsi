Unicode true

!include "MUI2.nsh"
!include "FileFunc.nsh"
!insertmacro GetSize

!ifndef VERSION
  !define VERSION "1.0.0"
!endif

!define NAME "R1999 Translator"
!define EXE "R1999Translator.exe"
!define PUBLISHER "TamKungZ_"
!define EMAIL "dev@tamkungz.me"
!define URL "https://github.com/TamKungZ/Reverse1999SubTranslator"
!define SETTINGS_KEY "Software\R1999Translator"
!define UNINSTALL_KEY "Software\Microsoft\Windows\CurrentVersion\Uninstall\R1999Translator"
!define SOURCE "..\dist\R1999Translator"

Name "${NAME}"
OutFile "..\dist\R1999Translator-Setup-${VERSION}.exe"
InstallDir "$LOCALAPPDATA\Programs\R1999Translator"
InstallDirRegKey HKCU "${SETTINGS_KEY}" "InstallDir"
RequestExecutionLevel user
SetCompressor /SOLID lzma
BrandingText "${PUBLISHER}"

!define MUI_ICON "..\ui\r1999ui\assets\icon.ico"
!define MUI_UNICON "..\ui\r1999ui\assets\icon.ico"
!define MUI_ABORTWARNING
!define MUI_FINISHPAGE_RUN "$INSTDIR\${EXE}"

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
LangString KeepData ${LANG_ENGLISH} "Also delete the settings and downloaded models in $APPDATA\R1999Translator?"
LangString KeepData ${LANG_THAI} "ลบการตั้งค่าและโมเดลที่ดาวน์โหลดไว้ใน $APPDATA\R1999Translator ด้วยหรือไม่?"

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
    nsExec::Exec 'taskkill /F /IM ${EXE} /IM r1999-engine.exe'
    Pop $0
    Sleep 800
  FunctionEnd
!macroend
!insertmacro CloseRunning ""
!insertmacro CloseRunning "un."

Section "$(SectionProgram)" SecProgram
  SectionIn RO
  Call CloseRunning
  RMDir /r "$INSTDIR\_internal"
  RMDir /r "$INSTDIR\engine"
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
  Call un.CloseRunning
  RMDir /r "$INSTDIR\_internal"
  RMDir /r "$INSTDIR\engine"
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

  IfSilent +3
  MessageBox MB_YESNO|MB_ICONQUESTION|MB_DEFBUTTON2 "$(KeepData)" IDNO +2
  RMDir /r "$APPDATA\R1999Translator"
SectionEnd
