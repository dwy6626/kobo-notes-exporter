#!/usr/bin/env python3
import argparse
import re
import sqlite3
import zipfile
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Set, Tuple
from xml.etree import ElementTree as ET


def clean_text(value: Optional[str]) -> str:
    if value is None:
        return ""
    return " ".join(value.strip().split())


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Export Kobo highlights/notes from KoboReader.sqlite to Markdown"
    )
    parser.add_argument("--db", default="", help="Path to KoboReader.sqlite")
    parser.add_argument(
        "--device-root",
        default="",
        help="Kobo mount root path (e.g. /Volumes/KOBOeReader)",
    )
    parser.add_argument(
        "--kepub-dir",
        default="",
        help="Path to kepub directory (optional, auto-detected if omitted)",
    )
    parser.add_argument("--out", default="kobo_notes.md", help="Output markdown path")
    parser.add_argument("--book", default="", help="Only export this exact book title")
    parser.add_argument(
        "--limit", type=int, default=0, help="Max rows to export (0 means all rows)"
    )
    parser.add_argument(
        "--asc", action="store_true", help="Sort rows old-to-new (default: new-to-old)"
    )
    parser.add_argument(
        "--volumes-root",
        default="/Volumes",
        help="Root path used for auto-detect mounted Kobo (default: /Volumes)",
    )
    return parser.parse_args()


def candidate_db_paths_for_device_root(device_root: Path) -> List[Path]:
    return [
        device_root / ".kobo" / "KoboReader.sqlite",
        device_root / "KoboReader.sqlite",
    ]


def discover_mounted_kobo_databases(volumes_root: Path) -> List[Path]:
    if not volumes_root.exists() or not volumes_root.is_dir():
        return []

    candidates: List[Path] = []
    for entry in sorted(volumes_root.iterdir(), key=lambda p: p.name.casefold()):
        if not entry.is_dir():
            continue
        for db_path in candidate_db_paths_for_device_root(entry):
            if db_path.exists():
                candidates.append(db_path)
                break

    # Prefer volumes with "kobo" in the volume name.
    candidates.sort(
        key=lambda p: (
            0 if "kobo" in p.parent.name.casefold() else 1,
            p.parent.name.casefold(),
        )
    )
    return candidates


def auto_detect_db_path(volumes_root: Path) -> Optional[Path]:
    mounted = discover_mounted_kobo_databases(volumes_root)
    if mounted:
        return mounted[0]

    local = Path.cwd() / "KoboReader.sqlite"
    if local.exists():
        return local

    return None


def resolve_db_path(args: argparse.Namespace) -> Path:
    if clean_text(args.db):
        db_path = Path(args.db).expanduser().resolve()
        if not db_path.exists():
            raise SystemExit(f"Database not found: {db_path}")
        return db_path

    if clean_text(args.device_root):
        device_root = Path(args.device_root).expanduser().resolve()
        for db_path in candidate_db_paths_for_device_root(device_root):
            if db_path.exists():
                return db_path.resolve()
        raise SystemExit(
            "Could not find KoboReader.sqlite under device root. "
            f"Checked: {', '.join(str(p) for p in candidate_db_paths_for_device_root(device_root))}"
        )

    detected = auto_detect_db_path(Path(args.volumes_root).expanduser().resolve())
    if detected is None:
        raise SystemExit(
            "Could not auto-detect KoboReader.sqlite. Use --db or --device-root explicitly."
        )
    return detected.resolve()


def resolve_kepub_dir(args: argparse.Namespace, db_path: Path) -> Optional[Path]:
    if clean_text(args.kepub_dir):
        kepub_dir = Path(args.kepub_dir).expanduser().resolve()
        return kepub_dir if kepub_dir.exists() else None

    candidates: List[Path] = []
    if db_path.parent.name == ".kobo":
        candidates.append((db_path.parent / "kepub").resolve())
        candidates.append((db_path.parent.parent / "kepub").resolve())
    else:
        candidates.append((db_path.parent / "kepub").resolve())

    for p in candidates:
        if p.exists() and p.is_dir():
            return p
    return None


def fetch_rows(conn: sqlite3.Connection, asc: bool, limit: int, book: str):
    order = "ASC" if asc else "DESC"
    where_book = ""
    limit_clause = ""
    params: List[object] = []

    if clean_text(book):
        where_book = "AND cb.Title = ?"
        params.append(book)

    if limit > 0:
        limit_clause = "LIMIT ?"
        params.append(limit)

    query = f"""
        SELECT
            COALESCE(cb.Title, '(Unknown Title)') AS book_title,
            b.VolumeID,
            b.ContentID,
            b.DateCreated,
            b.StartContainerPath,
            b.StartContainerChildIndex,
            b.StartOffset,
            b.Text,
            b.Annotation
        FROM Bookmark b
        LEFT JOIN content cb ON b.VolumeID = cb.ContentID
        WHERE (
            (b.Text IS NOT NULL AND TRIM(b.Text) <> '')
            OR (b.Annotation IS NOT NULL AND TRIM(b.Annotation) <> '')
        )
        {where_book}
        ORDER BY b.DateCreated {order}
        {limit_clause}
    """
    return conn.execute(query, params).fetchall()


def base_content_id(content_id: str) -> str:
    cid = clean_text(content_id)
    if not cid:
        return ""
    if "#" in cid:
        cid = cid.split("#", 1)[0]
    if ".xhtml-" in cid:
        return cid.rsplit("-", 1)[0]
    return cid


def content_path_from_content_id(content_id: str) -> str:
    cid = clean_text(content_id)
    if not cid:
        return ""
    if "#" in cid:
        cid = cid.split("#", 1)[0]
    if "!" in cid:
        return cid.split("!")[-1].lstrip("/")
    return cid.lstrip("/")


def chapter_fallback_from_content_id(content_id: str) -> str:
    cid = clean_text(content_id)
    if "!" in cid:
        return cid.split("!")[-1]
    return cid or "未分類"


def fallback_order_from_content_id(content_id: str) -> int:
    cid = chapter_fallback_from_content_id(content_id)
    nums = re.findall(r"\d+", cid)
    if nums:
        try:
            return int(nums[-1])
        except ValueError:
            return 10**9
    return 10**9


def looks_like_filename_title(title: str) -> bool:
    t = clean_text(title).lower()
    if not t:
        return True
    return (
        t.endswith(".xhtml")
        or t.endswith(".html")
        or t.startswith("xhtml/")
        or t.startswith("text/")
        or t.startswith("bodymatter_")
    )


def load_chapter_map(conn: sqlite3.Connection, volume_ids: Set[str]) -> Dict[str, Dict[str, str]]:
    if not volume_ids:
        return {}

    placeholders = ",".join(["?"] * len(volume_ids))
    query = f"""
        SELECT BookID, ContentID, Title
        FROM content
        WHERE BookID IN ({placeholders})
          AND ContentType = '899'
          AND Title IS NOT NULL
          AND TRIM(Title) <> ''
    """

    chapter_map: Dict[str, Dict[str, str]] = {}
    for book_id, content_id, title in conn.execute(query, tuple(volume_ids)):
        bid = clean_text(book_id)
        cid = base_content_id(content_id)
        t = clean_text(title)
        if not bid or not cid or not t:
            continue
        chapter_map.setdefault(bid, {})
        chapter_map[bid][cid] = t
    return chapter_map


def load_chapter_order_map(
    conn: sqlite3.Connection, volume_ids: Set[str]
) -> Dict[str, Dict[str, int]]:
    if not volume_ids:
        return {}

    placeholders = ",".join(["?"] * len(volume_ids))
    query = f"""
        SELECT BookID, ContentID, VolumeIndex
        FROM content
        WHERE BookID IN ({placeholders})
          AND ContentType IN ('9', '899')
    """

    order_map: Dict[str, Dict[str, int]] = {}
    for book_id, content_id, volume_index in conn.execute(query, tuple(volume_ids)):
        bid = clean_text(book_id)
        cid = base_content_id(content_id)
        if not bid or not cid:
            continue
        try:
            order_value = int(volume_index)
        except (TypeError, ValueError):
            continue
        order_map.setdefault(bid, {})
        if cid not in order_map[bid] or order_value < order_map[bid][cid]:
            order_map[bid][cid] = order_value
    return order_map


def load_volume_index_title_maps(
    conn: sqlite3.Connection, volume_ids: Set[str]
) -> Tuple[Dict[str, Dict[str, int]], Dict[str, Dict[int, str]]]:
    if not volume_ids:
        return {}, {}

    placeholders = ",".join(["?"] * len(volume_ids))
    query = f"""
        SELECT BookID, ContentID, ContentType, VolumeIndex, Title
        FROM content
        WHERE BookID IN ({placeholders})
          AND ContentType IN ('9', '899')
    """

    content_index_map: Dict[str, Dict[str, int]] = {}
    toc_title_by_index: Dict[str, Dict[int, str]] = {}

    for book_id, content_id, content_type, volume_index, title in conn.execute(
        query, tuple(volume_ids)
    ):
        bid = clean_text(book_id)
        cid = base_content_id(content_id)
        t = clean_text(title)
        try:
            vi = int(volume_index)
        except (TypeError, ValueError):
            continue

        if not bid or not cid:
            continue

        content_index_map.setdefault(bid, {})
        if content_type == "9":
            content_index_map[bid][cid] = vi

        if content_type == "899" and t and not looks_like_filename_title(t):
            toc_title_by_index.setdefault(bid, {})
            if vi not in toc_title_by_index[bid]:
                toc_title_by_index[bid][vi] = t

    return content_index_map, toc_title_by_index


def load_epub_toc_map(volume_ids: Iterable[str], kepub_dir: Optional[Path]) -> Dict[str, Dict[str, str]]:
    toc_map: Dict[str, Dict[str, str]] = {}
    if kepub_dir is None:
        return toc_map

    def add_mapping(book_id: str, href: str, label: str) -> None:
        h = clean_text(href)
        l = clean_text(label)
        if not h or not l:
            return
        if "#" in h:
            h = h.split("#", 1)[0]
        h = h.lstrip("./")
        if not h:
            return
        toc_map.setdefault(book_id, {})
        toc_map[book_id][h] = l
        toc_map[book_id][Path(h).name] = l

    for book_id in volume_ids:
        epub_path = kepub_dir / book_id
        if not epub_path.exists():
            continue
        try:
            with zipfile.ZipFile(epub_path) as zf:
                names = set(zf.namelist())
                toc_candidates = [n for n in names if n.lower().endswith("toc.ncx")]
                nav_candidates = [n for n in names if n.lower().endswith("nav.xhtml")]

                if toc_candidates:
                    toc_name = sorted(toc_candidates)[0]
                    root = ET.fromstring(zf.read(toc_name))
                    for nav_point in root.findall(".//{*}navPoint"):
                        text_elem = nav_point.find(".//{*}text")
                        content_elem = nav_point.find(".//{*}content")
                        if text_elem is not None and content_elem is not None:
                            add_mapping(
                                book_id,
                                content_elem.attrib.get("src", ""),
                                text_elem.text or "",
                            )

                if nav_candidates:
                    nav_name = sorted(nav_candidates)[0]
                    root = ET.fromstring(zf.read(nav_name))
                    for anchor in root.findall(".//{*}a"):
                        add_mapping(
                            book_id,
                            anchor.attrib.get("href", ""),
                            "".join(anchor.itertext()),
                        )
        except Exception:
            continue

    return toc_map


def natural_title_key(title: str) -> Tuple:
    parts = re.split(r"(\d+)", title)
    key: List[object] = []
    for part in parts:
        if part.isdigit():
            key.append(int(part))
        else:
            key.append(part.casefold())
    return tuple(key)


def position_key(
    start_container_path: str, start_container_child_index: object, start_offset: object
) -> Tuple:
    path = clean_text(start_container_path)
    path_nums = [int(x) for x in re.findall(r"\d+", path)] if path else []
    if not path_nums:
        path_nums = [10**9]

    try:
        child_idx = int(start_container_child_index)
    except (TypeError, ValueError):
        child_idx = 10**9

    try:
        offset = int(start_offset)
    except (TypeError, ValueError):
        offset = 10**9

    return (tuple(path_nums), child_idx, offset)


def resolve_chapter_title(
    volume: str,
    content_id: str,
    chapter_map: Dict[str, Dict[str, str]],
    epub_toc_map: Dict[str, Dict[str, str]],
    content_index_map: Dict[str, Dict[str, int]],
    toc_title_by_index: Dict[str, Dict[int, str]],
) -> str:
    cid = base_content_id(content_id)
    chapter_title = chapter_map.get(volume, {}).get(cid) or chapter_fallback_from_content_id(content_id)

    if looks_like_filename_title(chapter_title):
        path_key = content_path_from_content_id(content_id)
        chapter_title = (
            epub_toc_map.get(volume, {}).get(path_key)
            or epub_toc_map.get(volume, {}).get(Path(path_key).name)
            or chapter_title
        )

    if looks_like_filename_title(chapter_title):
        vi = content_index_map.get(volume, {}).get(cid)
        if vi is not None:
            direct = toc_title_by_index.get(volume, {}).get(vi)
            if direct:
                chapter_title = direct
            else:
                prior = [
                    (idx, t)
                    for idx, t in toc_title_by_index.get(volume, {}).items()
                    if idx <= vi and not looks_like_filename_title(t)
                ]
                if prior:
                    prior.sort(key=lambda x: x[0], reverse=True)
                    chapter_title = prior[0][1]

    chapter_title = clean_text(chapter_title)
    if looks_like_filename_title(chapter_title):
        chapter_title = "未分類"
    return chapter_title or "未分類"


def build_markdown(
    rows,
    chapter_map: Dict[str, Dict[str, str]],
    chapter_order_map: Dict[str, Dict[str, int]],
    epub_toc_map: Dict[str, Dict[str, str]],
    content_index_map: Dict[str, Dict[str, int]],
    toc_title_by_index: Dict[str, Dict[int, str]],
) -> str:
    books: Dict[str, Dict[str, Dict[str, object]]] = {}

    for (
        book_title,
        volume_id,
        content_id,
        date_created,
        start_container_path,
        start_container_child_index,
        start_offset,
        text,
        note,
    ) in rows:
        book = clean_text(book_title) or "(Unknown Title)"
        volume = clean_text(volume_id)
        cid = base_content_id(content_id)

        chapter_title = resolve_chapter_title(
            volume,
            content_id,
            chapter_map,
            epub_toc_map,
            content_index_map,
            toc_title_by_index,
        )
        chapter_order = chapter_order_map.get(volume, {}).get(
            cid, fallback_order_from_content_id(content_id)
        )

        books.setdefault(book, {})
        if chapter_title not in books[book]:
            books[book][chapter_title] = {"order": chapter_order, "quotes": []}
        else:
            old = books[book][chapter_title]["order"]
            if isinstance(old, int) and chapter_order < old:
                books[book][chapter_title]["order"] = chapter_order

        pos = position_key(clean_text(start_container_path), start_container_child_index, start_offset)
        created = clean_text(date_created)

        highlight = clean_text(text)
        note_text = clean_text(note)

        if highlight:
            books[book][chapter_title]["quotes"].append({"text": highlight, "pos": pos, "date": created})
        if note_text:
            books[book][chapter_title]["quotes"].append({"text": note_text, "pos": pos, "date": created})

    lines: List[str] = []
    single_book = len(books) == 1

    for idx, (book, chapters) in enumerate(sorted(books.items(), key=lambda x: x[0].casefold()), start=1):
        if not single_book:
            lines.append(f"# {book}")
            lines.append("")

        sorted_chapters = sorted(
            chapters.items(), key=lambda item: (item[1].get("order", 10**9), natural_title_key(item[0]))
        )

        for chapter, payload in sorted_chapters:
            lines.append(f"## {chapter}")
            lines.append("")

            quotes = sorted(payload["quotes"], key=lambda q: (q["pos"], q["date"]))
            for quote in quotes:
                lines.append(f"> {quote['text']}")
                lines.append("")

        if not single_book and idx < len(books):
            lines.append("")

    return "\n".join(lines).rstrip() + "\n"


def main() -> int:
    args = parse_args()
    db_path = resolve_db_path(args)
    out_path = Path(args.out).expanduser().resolve()
    kepub_dir = resolve_kepub_dir(args, db_path)

    conn = sqlite3.connect(f"file:{db_path}?immutable=1", uri=True)
    try:
        rows = fetch_rows(conn, asc=args.asc, limit=args.limit, book=args.book)
        volume_ids = {clean_text(r[1]) for r in rows if clean_text(r[1])}
        chapter_map = load_chapter_map(conn, volume_ids)
        chapter_order_map = load_chapter_order_map(conn, volume_ids)
        content_index_map, toc_title_by_index = load_volume_index_title_maps(conn, volume_ids)
    finally:
        conn.close()

    epub_toc_map = load_epub_toc_map(volume_ids, kepub_dir)

    markdown = build_markdown(
        rows,
        chapter_map,
        chapter_order_map,
        epub_toc_map,
        content_index_map,
        toc_title_by_index,
    )
    out_path.write_text(markdown, encoding="utf-8")

    source = f"db={db_path}"
    if kepub_dir is not None:
        source += f", kepub={kepub_dir}"
    print(f"Exported {len(rows)} items to {out_path} ({source})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
