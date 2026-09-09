# claude-code-statusline-simple

A single-file status line for [Claude Code](https://claude.com/claude-code).
No dependencies, no config file, no Nerd Font. One Python script, ~300 lines.

![status line](docs/statusline.svg)

It shows the model, the reasoning effort, the advisor model, how full the
context window is, and how much of each rate-limit window is used.

## The gauges change colour as they fill

Green while there is room, amber past halfway, red when a window is nearly
spent. The shift is continuous rather than stepped, so a limit creeping up on
you is visible before it becomes a number you have to read.

![gauges at rising usage](docs/heat.svg)

Both images are drawn by `statusline.py` itself (`python3 tools/render_svg.py`
turns its real ANSI output into SVG), so what is shown here is what the script
prints — not a mock-up.

## Why another one

There are richer status lines out there ([ccstatusline](https://github.com/sirmalloc/ccstatusline)
is excellent and configurable). This one is deliberately not that: no build
step, no npm, no TOML. Copy one file, add four lines to `settings.json`, done.

Two details it does get fussy about:

- **Sub-cell bars.** The bar is drawn at 1/8-cell precision, so 8% still shows
  a visible `▍` instead of collapsing to an empty bar.
- **Advisor model.** As of Claude Code 2.1.229 the advisor model is not in the
  status line JSON, so it is recovered by tailing the last assistant message in
  the transcript.

## Install

```sh
curl -o ~/.claude/statusline.py \
  https://raw.githubusercontent.com/chobitnet/claude-code-statusline-simple/main/statusline.py
```

Then in `~/.claude/settings.json`:

```json
{
  "statusLine": {
    "type": "command",
    "command": "python3 ~/.claude/statusline.py"
  }
}
```

Requires Python 3.8+ (stdlib only) and a terminal with truecolor support.

## Preview it before installing

```sh
python3 statusline.py --demo
```

This renders both styles against sample data and prints a glyph check, so you
can see whether the partial-block characters and the Powerline arrow survive
your font.

## Styles

`minimal` (default) separates segments with a thin rule and needs no special
font. `powerline` uses filled backgrounds joined by ``, which requires a
Nerd Font:

```sh
CC_STATUSLINE_STYLE=powerline python3 ~/.claude/statusline.py
```

Set it in the `settings.json` command if you want it permanently:

```json
"command": "CC_STATUSLINE_STYLE=powerline python3 ~/.claude/statusline.py"
```

## Debugging

Claude Code passes the status line a JSON object on stdin
([schema](https://code.claude.com/docs/en/statusline)). To capture what your
version actually sends:

```sh
touch ~/.claude/.statusline-debug
```

The next render writes the raw JSON to `~/.claude/.statusline-input.json`.
Delete the flag file to stop.

## Customising

Everything worth changing is a constant near the top of the file: the colour
stops (`HEAT_STOPS`), the bar width (`BAR_W`), the greys, and the accent
colours. `build()` decides which segments exist; `render_minimal()` and
`render_powerline()` decide how they look. The two are kept separate so a new
renderer only has to handle the segment dicts.

## Licence

MIT. See [LICENSE](LICENSE).

---

## 日本語

Claude Code のステータスラインを、Python 1ファイルだけで済ませるものです。
依存なし・設定ファイルなし・Nerd Font なしで動きます。

表示するのは、モデル / effort / advisor モデル / コンテキスト使用量 /
レート制限の各枠です。

![ステータスライン](docs/statusline.svg)

ゲージは使用率に応じて緑→琥珀→赤へ**連続的に**変わります。段階で飛ばないので、
制限に近づいていることが数字を読む前に分かります。

![使用率とゲージの色](docs/heat.svg)

この2枚は `statusline.py` 自身に描かせたものです(`python3 tools/render_svg.py` が
実際の ANSI 出力を SVG に写します)。作り物ではなく、スクリプトが吐く実物です。

### 導入

```sh
curl -o ~/.claude/statusline.py \
  https://raw.githubusercontent.com/chobitnet/claude-code-statusline-simple/main/statusline.py
```

`~/.claude/settings.json` に:

```json
{
  "statusLine": {
    "type": "command",
    "command": "python3 ~/.claude/statusline.py"
  }
}
```

Python 3.8 以降（標準ライブラリのみ）と、truecolor が出るターミナルが要ります。

### 入れる前に見る

```sh
python3 statusline.py --demo
```

2つのスタイルをサンプルデータで描き、グリフ確認も出します。部分ブロックや
Powerline の矢印が豆腐（□）にならないか、ここで分かります。

### 作りのメモ

- バーは1/8セル刻みで描いています。8% のような小さい値を空バーに潰さないためです。
- advisor モデルは 2.1.229 時点でステータスライン JSON に含まれないため、
  トランスクリプトの最終 assistant メッセージから復元しています。
- `CC_STATUSLINE_STYLE=powerline` で Powerline 風になります（Nerd Font 必須）。
- 色・バー幅はファイル冒頭の定数、表示項目は `build()`、見た目は
  `render_minimal()` / `render_powerline()` に分けてあります。
