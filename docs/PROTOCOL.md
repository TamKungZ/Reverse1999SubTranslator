# Engine protocol

The engine (`r1999-engine`) is a local HTTP server on `127.0.0.1:47631` with no UI dependency.
A UI only captures the game, sends frames, and draws the returned view. All JSON is UTF-8.

## Endpoints

| Method | Path | Purpose |
| --- | --- | --- |
| GET | `/info` | `protocol`, `version`, `state`, `error`, `download`, `languages`, `scripts`, `fonts`, `language_errors`, `model_repo`, `config` |
| POST | `/frame` | Send one frame, receive the current view |
| GET | `/view` | Current view without sending a frame |
| GET / POST | `/config` | Read or update engine settings (JSON object) |
| POST | `/reset` | Clear state and hide the current view |
| POST | `/model/download`, `/model/cancel` | Model download control |
| POST | `/shutdown` | Stop the engine |

`state` is one of `starting`, `loading`, `model_missing`, `downloading`, `ready`, `error`.
`download` is `{state, done, total, file, error}` in bytes.
`languages` maps a language code to its display name and `scripts` to its script (`Thai`, `Latn`, `Jpan`, ...).
`fonts` maps a language code to the font families a UI should prefer for it, the first being the default; a UI
should not offer a language that no installed font can show.
`language_errors` lists entries of the user's `languages.json` that were skipped. `model_repo` is the model the
current `target_lang` uses. Setting `target_lang` to a language whose model is not on disk changes `state` to
`model_missing`; call `/model/download` to fetch it.

## POST /frame

Body: raw pixels, 8-bit BGR, row-major, no padding. Headers:

- `X-Width`, `X-Height`: size of the pixels sent
- `X-Client-W`, `X-Client-H`: size of the game client area in pixels
- `X-Region`: `x0,y0,x1,y1` as fractions of the client area, the rectangle the pixels were cropped from.
  Use `config.region` from `/info`.
- `X-Format`: `bgr` (default) or `png` (body is an encoded image)

Send frames at about 10 Hz only while the game window is in the foreground. Unchanged frames are cheap.
The response is the current view; redraw when `seq` or `kind` changes.

## View

```json
{
  "seq": 12,
  "kind": "sentence",
  "pending": false,
  "speaker": {"raw": "Regulus", "display": "เรกูลัส", "known": true},
  "segments": [{"t": "…", "k": null}, {"t": "เรกูลัส", "k": "name"}],
  "chips": [{"w": "sail", "m": "แล่นเรือ", "k": "word"}],
  "anchor_top": 0.811,
  "source": "original text",
  "style": {
    "text_ink_h": 0.0306, "name_cap": 0.0287, "text_left": 0.2146, "name_left": 0.2219,
    "name_to_text": 0.0704, "pitch": null, "text_color": "#e1dedc", "name_color": "#b4aba4"
  }
}
```

- `kind`: `sentence` (use `segments`), `words` (use `chips`), or `none` (hide)
- `pending`: a live partial translation that will be replaced
- `k`: `null`, `name` (person), `term` (game term), `word` (chips only)
- `anchor_top`: top edge of the original dialog as a fraction of client height; draw the translation above it
- `style` is measured from the game's own subtitles (heights as fractions of client height, x as fractions of
  client width, colours as `#rrggbb`); defaults are used until measured. `text_ink_h` is the ink height of a line
  with ascenders and descenders, `name_cap` the capital-letter height of the speaker name, `name_to_text` the
  distance between the top of the name and the top of the text. A UI that draws the translation in the same
  style picks a font size whose glyphs have these heights.
- Thai text contains U+200B between words as line-break opportunities; render it as zero-width

## Config keys

`mode` (`sentence`|`word`), `timing` (`wait`|`live`), `target_lang` (a key of `languages`), `name_style` (`native`|`original`|`both`),
`word_level` (`off`|`basic`|`medium`), `stable_ms`, `live_interval_ms`, `hide_ms`, `region`, `name_band`,
`model_repo`, `threads`, `device`.
