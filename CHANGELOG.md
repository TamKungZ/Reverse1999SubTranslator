# Changelog

## [1.1.0] - 2026-11-24

### Added

- A second translator, Argos, chosen in the menu. It translates a sentence in about 60 ms instead of 700 ms and downloads 64 MB instead of 620 MB. NLLB-200 stays the default. Languages without an Argos model keep using NLLB.
- The `argos` field in `languages.json` and the `translator` setting (`nllb`|`argos`).

### Changed

- While new text is still appearing the picture is read every 0.25 s, and changes to the right of or below the text already read are noticed. The last words of a typed line no longer go untranslated.
- Download requests identify the program, because some model hosts refuse the default Python agent.

## [1.0.1] - 2026-11-24

### Removed

- Code and a development helper that nothing used. There is no change in behavior.

## [1.0.0] - 2026-11-24

### Added

- Offline overlay translator for the Reverse: 1999 PC client, made of a separate engine (OCR and translation) and UI process.
- Translation with the NLLB-200 model, downloaded on first run, in sentence mode and in word by word mode.
- Names and game terms from an editable glossary.
- Overlay drawn with the size, colour, position and alignment measured from the game's own subtitles, centered for the main menu and left aligned for dialog.
- Settings menu (F9), hotkeys for translation on and off (F7) and for the mode (F8), and a tray icon.
- Font choice from the fonts installed on the machine. Each language can name its preferred fonts in `languages.json`, and release builds bundle Kanit (SIL Open Font License 1.1) as the default for Thai.- Target languages Thai, Indonesian and Vietnamese. More languages can be added in `languages.json`, each optionally with its own model that is downloaded when the language is first selected.
- Interface languages English and Thai. More can be added as locale files.
- Local HTTP protocol so another UI can use the engine.
- Reading of subtitles that wrap to two lines, that move or change between frames, that are centered, and of scenes without a speaker name.
- Per-user Windows installer and uninstaller.
- A message that says what to install when the engine cannot start on Windows N editions without the Media Feature Pack.
