# Changelog

## [1.0.0] - 2026-11-24

### Added

- Offline overlay translator for the Reverse: 1999 PC client, made of a separate engine (OCR and translation) and UI process.
- Translation with the NLLB-200 model, downloaded on first run, in sentence mode and in word by word mode.
- Names and game terms from an editable glossary.
- Overlay drawn with the size, colour and position measured from the game's own subtitles.
- Settings menu (F9), hotkeys for translation on and off (F7) and for the mode (F8), and a tray icon.
- Font choice from the fonts installed on the machine. Each language can name its preferred fonts in `languages.json`, and release builds bundle Kanit (SIL Open Font License 1.1) as the default for Thai.- Target languages Thai, Indonesian and Vietnamese. More languages can be added in `languages.json`, each optionally with its own model that is downloaded when the language is first selected.
- Interface languages English and Thai. More can be added as locale files.
- Local HTTP protocol so another UI can use the engine.
- Reading of subtitles that wrap to two lines, that move or change between frames, that are centered, and of scenes without a speaker name.
- Per-user Windows installer and uninstaller.
