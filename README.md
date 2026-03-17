# Kobo Notes Exporter

將 Kobo 的劃線與註解匯出成 Markdown，格式為：

- `## 章節標題`
- 每則筆記以 `> 引文` 呈現

## Features

- 支援指定資料庫路徑：`--db`
- 支援指定裝置掛載根目錄：`--device-root`
- 預設自動偵測 macOS 掛載的 Kobo：掃描 `/Volumes/*`
- 章節名稱來源多層 fallback：
  1. `KoboReader.sqlite` 的 `content` (`ContentType=899`)
  2. `kepub/<BookID>` 的 `toc.ncx` / `nav.xhtml`
  3. `VolumeIndex` 對齊
  4. 最後回退為 `未分類`
- 章節排序依書內順序（`VolumeIndex`）
- 章內排序依閱讀位置（`StartContainerPath`, `StartContainerChildIndex`, `StartOffset`）

## Prerequisites

- Python 3.14+
- [uv](https://docs.astral.sh/uv/)

## Setup

```bash
cd /Users/davidye/Projects/kobo/kobo-notes-exporter
uv venv
uv sync
```

## Usage

建議主要使用 `--device-root`。需要精準控制時，再搭配 `--db` / `--kepub-dir` 覆寫。

### 1) 自動偵測已掛載 Kobo（預設）

```bash
uv run kobo-notes-export --out-dir ./kobo_notes
```

### 2) 明確指定資料庫（進階）

```bash
uv run kobo-notes-export \
  --db /path/to/KoboReader.sqlite \
  --out-dir ./kobo_notes
```

### 3) 指定裝置根目錄（例如 /Volumes/KOBOeReader）

```bash
uv run kobo-notes-export \
  --device-root /Volumes/KOBOeReader \
  --out-dir ./kobo_notes
```

### 4) 指定 kepub 目錄（可選，進階）

```bash
uv run kobo-notes-export \
  --device-root /Volumes/KOBOeReader \
  --db /path/to/KoboReader.sqlite \
  --kepub-dir /path/to/kepub \
  --out-dir ./kobo_notes
```

## Development

```bash
uv run python -m kobo_notes_exporter.cli --help
```

## Project Structure

- `src/kobo_notes_exporter/cli.py`: CLI 與匯出邏輯
- `pyproject.toml`: 專案與 entrypoint 設定
