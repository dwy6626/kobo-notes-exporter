# Kobo Notes Exporter

將插在 macOS 的 Kobo reader 劃線（highlight）與筆記（note）匯出成 Markdown。

## 輸出格式

- 每本書輸出成一個 `.md` 檔案（寫入 `--out-dir`）
- 章節使用 `## 章節標題`
- 劃線（highlight）使用引用格式：`> 引文`
- 筆記（note）直接輸出為下一行純文字（不加 `>`)

## 功能

- 支援指定裝置掛載根目錄：`--device-root`（建議主要使用）
- 支援精準覆寫資料來源：`--db`、`--kepub-dir`
- 支援輸出路徑已存在時的行為控制：`--out-exists`（`overwrite` / `rename` / `raise`）
- 提供短參數：`-d` / `-r` / `-k` / `-o` / `-e`
- 預設可自動偵測已掛載 Kobo（掃描 `/Volumes/*`）
- 章節名稱採多層 fallback：
  1. `KoboReader.sqlite` 的 `content` (`ContentType=899`)
  2. `kepub/<BookID>` 的 `toc.ncx` / `nav.xhtml`
  3. `VolumeIndex` 對齊
  4. 最後回退為 `未分類`
- 章節排序依書內順序（`VolumeIndex`）
- 章內排序依閱讀位置（`StartContainerPath`, `StartContainerChildIndex`, `StartOffset`）

## 環境需求

- Python 3.14+
- [uv](https://docs.astral.sh/uv/)

## 安裝

```bash
cd /Users/davidye/Projects/kobo/kobo-notes-exporter
uv venv
uv sync
```

## 使用方式

建議主要使用 `--device-root`。需要精準控制時，再搭配 `--db` / `--kepub-dir` 覆寫。

短參數對照：`-d` = `--db`、`-r` = `--device-root`、`-k` = `--kepub-dir`、`-o` = `--out-dir`、`-e` = `--out-exists`。

### 1) 自動偵測已掛載 Kobo（最簡單）

```bash
uv run kobo-notes-export --out-dir ./kobo_highlights
```

### 2) 指定裝置根目錄（推薦）

```bash
uv run kobo-notes-export \
  --device-root /Volumes/KOBOeReader \
  --out-dir ./kobo_highlights
```

### 3) 明確指定資料庫（進階）

```bash
uv run kobo-notes-export \
  --db /path/to/KoboReader.sqlite \
  --out-dir ./kobo_highlights
```

### 4) `--device-root` + 覆寫 `--db` / `--kepub-dir`（進階）

```bash
uv run kobo-notes-export \
  --device-root /Volumes/KOBOeReader \
  --db /path/to/KoboReader.sqlite \
  --kepub-dir /path/to/kepub \
  --out-dir ./kobo_highlights \
  --out-exists rename
```

## 參數優先順序

1. 有給 `--device-root` 時，會先以該裝置目錄為主。
2. 若同時給 `--db`，則使用你指定的 DB（相對路徑會相對於 `--device-root`）。
3. 若同時給 `--kepub-dir`，則使用你指定的目錄（相對路徑會相對於 `--device-root`）。
4. 若沒給 `--device-root`，可單用 `--db`；若都沒給則自動掃描 `/Volumes`。

## 輸出檔案說明

- 輸出資料夾由 `--out-dir` 決定（預設：`kobo_notes`）
- 每本書會產生一個 Markdown 檔
- 檔名會自動清理不合法字元（例如 `/ \ : * ? " < > |`）
- `--out-exists` 預設為 `raise`：
  - `raise`：若輸出路徑已存在就直接報錯
  - `overwrite`：保留既有資料夾並覆蓋同名檔案
  - `rename`：先把既有輸出路徑改名（`<目錄名>.bak.<timestamp>`）再輸出

## 常見問題

### 找不到資料庫

- 確認 Kobo 已掛載在 macOS（通常在 `/Volumes/<裝置名稱>`）
- 確認有 `KoboReader.sqlite`，常見位置：
  - `/Volumes/<裝置名稱>/.kobo/KoboReader.sqlite`
  - `/Volumes/<裝置名稱>/KoboReader.sqlite`

### 章節名稱不完整

- 建議同時提供 `--kepub-dir`，讓程式可讀取 `toc.ncx` / `nav.xhtml` 增強章節名稱解析

## 開發

```bash
uv run python -m kobo_notes_exporter.cli --help
```

### 執行單元測試

執行全部測試：

```bash
uv run python -m unittest discover -s tests
```

執行單一測試檔：

```bash
uv run python -m unittest tests.test_output_dir_behavior
```

執行單一測試方法：

```bash
uv run python -m unittest tests.test_output_dir_behavior.OutputDirBehaviorTests.test_parse_args_supports_short_options
```

## 專案結構

- `src/kobo_notes_exporter/cli.py`: CLI 與匯出邏輯
- `pyproject.toml`: 專案與 entrypoint 設定
