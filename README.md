# R1999 Translator

Offline subtitle translator for the Reverse: 1999 PC client. It reads the game's English subtitles from the screen and draws a translation over them. After the translation model has been downloaded, nothing leaves the computer.

## What to expect

- The translation is made in real time while the game runs, so it appears a moment after the subtitle, not together with it.
- It is machine translation and is not always accurate. It helps to follow the overall context of a scene.
- Understanding English and listening to the voice acting are still needed. The translation only eases the load of the difficult words the game uses, more or less.

## Screenshots

<!--
![Dialog](docs/images/dialog.png)
![Main menu](docs/images/main-menu.png)
-->

## Install

1. Download `R1999Translator-Setup-<version>.exe` from [Releases](https://github.com/TamKungZ/Reverse1999SubTranslator/releases) and run it. It installs for the current user and needs no administrator rights.
2. Set the game's text language to English and run the game in windowed or borderless mode.
3. Start R1999 Translator. On the first start it downloads the translation model: NLLB-200 (about 620 MB) or, if you pick Argos in the menu, a 64 MB model that translates about ten times faster.

Requires Windows 11 (64-bit). Windows N editions also need the Media Feature Pack from Microsoft.

## Use

| Key | Action |
| --- | --- |
| F7 | Translation on / off |
| F8 | Sentence / word mode |
| F9 | Settings (arrow keys, Enter, Esc) |

The translation is drawn over the game's subtitles in the same size, colour and alignment. The F9 menu changes the font, the size, the languages and more.

## Languages

The game text is read in English and translated into:

| Language | Status |
| --- | --- |
| Thai | Tested the most |
| Indonesian | Same model, little testing |
| Vietnamese | Same model, little testing |

The program itself is available in English and Thai.

## Customizing

Everything below lives in `%APPDATA%\R1999Translator`.

- **More target languages:** add entries to `engine\languages.json`. The translation model covers about 200 languages. Format: [languages.json](engine/r1999engine/data/languages.json).
- **Names and game terms:** add or fix entries in `engine\glossary.json`. Format: [glossary.json](engine/r1999engine/data/glossary.json).
- **Program languages:** add `locales\<code>.json`. Format: [en.json](ui/r1999ui/locales/en.json).

Another interface can use the engine through its local HTTP protocol, see [docs/PROTOCOL.md](docs/PROTOCOL.md).

## License

Source code: Mozilla Public License 2.0, see [LICENSE](LICENSE). The translation model is NLLB-200 under CC-BY-NC-4.0, which does not allow commercial use. The Argos models are OPUS-MT models packaged by Argos Open Tech under CC-BY-4.0. Releases bundle the Kanit font under the SIL Open Font License 1.1.
