# R1999 Translator

Offline overlay translator for the Reverse: 1999 PC client. The `engine` (Python, OCR and translation, no UI)
and the `ui` (overlay, hotkeys, settings) are separate processes; see `docs/PROTOCOL.md` to write another UI.

Output: `dist\R1999Translator\R1999Translator.exe`. On first run it downloads the translation model (about 620 MB,
CC-BY-NC-4.0) to `%APPDATA%\R1999Translator\engine\models`. Run the game in windowed or borderless mode.

## Hotkeys

| Key | Action |
| --- | --- |
| F7 | Translation on / off |
| F8 | Sentence / word mode |
| F9 | Settings (arrow keys, Enter, Esc) |

The translation is drawn as plain text, without a background, in the size, colour and position measured from the
game's own subtitles. Settings (font from the installed fonts, size adjustment, matching the original style,
interface language, and more) are in the F9 menu and saved in `%APPDATA%\R1999Translator`.

Interface language: add `<code>.json` to `%APPDATA%\R1999Translator\locales` (copy `ui\r1999ui\locales\en.json`,
set `_name`); it then appears in the menu. Names: add or fix entries in `engine\glossary.json` in the same
folder, in the format of `engine\r1999engine\data\glossary.json`.
Target languages: add entries to `engine\languages.json` in the same folder, in the format of
`engine\r1999engine\data\languages.json`; a language with its own `model_repo` downloads that model when it is
first selected.
