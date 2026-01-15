#!/usr/bin/env python3
"""luagmp_docgen.py

Generates Markdown docs from comment blocks of the form:

    /* luagmp (class)
     *
     * This class exposes ...
     * @name Discord
     * @side client
     * @category Discord
     */

Also accepts the legacy prefix "luadoc" (/* luadoc (...)).

Templates are Jinja2 (.md) files.

Output layout (default):
- Classes:    <out>/<side>-classes/<category-slug>/<ClassName>.md   (aggregates constructors/methods/properties/callbacks)
- Functions:  <out>/<side>-functions/<category-slug>/<name>.md
- Events:     <out>/<side>-events/<category-slug>/<name>.md
- Globals:    <out>/<side>-globals/<name>.md                        (not nested by category)
- Constants:  <out>/<side>-constants/<Category>.md                  (aggregated by side+category, not nested by category)

Common failure mode fixed in this patched version:
- If your templates are inside a "templates/" subfolder (as in templates.zip), the generator now finds them.

Performance improvements in this patched version:
- Only scans selected extensions by default (now: .cpp, .hpp, .h).
- Performs a fast binary pre-scan for the markers "luagmp (" or "luadoc (" and skips files that cannot contain docs.

Usage:
  python luagmp_docgen.py --project "C:/path/to/src" --out "../gmpdocs" --templates "./templates.zip"

Optional:
  --ext ".cpp,.hpp,.h"   # extensions to scan (comma-separated). Use "*" to scan all.
"""

from __future__ import annotations

import argparse
import re
import sys
import zipfile
import shutil
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from jinja2 import Environment, FileSystemLoader, StrictUndefined


# -----------------------------
# Data models (match templates)
# -----------------------------

@dataclass
class Side:
    value: str  # templates use side.value


@dataclass
class Param:
    type: str
    name: str
    description: str


@dataclass
class Returns:
    type: str
    description: str


@dataclass
class ConstElement:
    name: str
    description: str


@dataclass
class BlockBase:
    kind: str
    description: str = ""
    name: Optional[str] = None
    version: Optional[str] = None
    deprecated: Optional[str] = None
    extends: Optional[str] = None  # class.md expects definition.extends
    side: Side = field(default_factory=lambda: Side("unknown"))
    category: str = "Uncategorized"
    notes: List[str] = field(default_factory=list)
    params: List[Param] = field(default_factory=list)
    returns: Optional[Returns] = None
    example_code: Optional[str] = None
    declaration: str = ""  # templates expect *.declaration, always synthesized

    # Additional flags used by templates
    cancellable: bool = False  # event.md
    static: bool = False       # class.md, callbacks
    read_only: bool = False    # class.md property rendering


@dataclass
class ClassDoc:
    definition: BlockBase
    constructors: List[BlockBase] = field(default_factory=list)
    properties: List[BlockBase] = field(default_factory=list)
    methods: List[BlockBase] = field(default_factory=list)
    callbacks: List[BlockBase] = field(default_factory=list)


# -----------------------------
# Template loading
# -----------------------------

REQUIRED_TEMPLATES = {"class.md", "function.md", "event.md", "const.md", "global.md"}


def _looks_like_template_dir(p: Path) -> bool:
    if not p.is_dir():
        return False
    existing = {c.name for c in p.iterdir() if c.is_file()}
    return REQUIRED_TEMPLATES.issubset(existing)


def load_templates_source(templates_path: Path) -> Path:
    """Return the directory containing the .md templates.

    Accepts:
    - a directory containing the templates
    - a directory containing a "templates/" subfolder with the templates
    - a .zip that contains either templates at the root or within a "templates/" folder
    """
    if templates_path.is_dir():
        if _looks_like_template_dir(templates_path):
            return templates_path
        sub = templates_path / "templates"
        if _looks_like_template_dir(sub):
            return sub
        raise FileNotFoundError(
            f"Templates directory does not contain required files {sorted(REQUIRED_TEMPLATES)}: {templates_path}"
        )

    if templates_path.is_file() and templates_path.suffix.lower() == ".zip":
        extract_dir = templates_path.parent / (templates_path.stem + "_extracted")
        extract_dir.mkdir(parents=True, exist_ok=True)
        with zipfile.ZipFile(str(templates_path), "r") as zf:
            zf.extractall(str(extract_dir))

        # Templates may be in root or in templates/
        if _looks_like_template_dir(extract_dir):
            return extract_dir
        sub = extract_dir / "templates"
        if _looks_like_template_dir(sub):
            return sub

        raise FileNotFoundError(
            f"Extracted templates zip but could not find required templates {sorted(REQUIRED_TEMPLATES)} in: {extract_dir}"
        )

    raise FileNotFoundError(f"Templates path not found or unsupported: {templates_path}")


def build_jinja_env(templates_dir: Path) -> Environment:
    return Environment(
        loader=FileSystemLoader(str(templates_dir)),
        undefined=StrictUndefined,
        autoescape=False,
        trim_blocks=True,
        lstrip_blocks=True,
    )


# -----------------------------
# Parsing logic
# -----------------------------

# Accept both prefixes to be resilient.
BLOCK_RE = re.compile(
    r"/\*\s*(?:luagmp|luadoc)\s*\((?P<kind>[^)]+)\)\s*(?P<body>.*?)\*/",
    re.DOTALL | re.IGNORECASE,
)

TAG_RE = re.compile(r"^\s*@(?P<tag>\w+)\s*(?P<rest>.*)$")


def slugify(s: str) -> str:
    s = (s or "").strip().lower()
    s = re.sub(r"[^a-z0-9]+", "-", s)
    s = re.sub(r"-{2,}", "-", s).strip("-")
    return s or "uncategorized"


def normalize_side(raw: str) -> Side:
    v = (raw or "").strip().lower()
    if v in ("client", "server", "shared", "both"):
        return Side(v)
    return Side(v or "unknown")


def clean_block_lines(body: str) -> List[str]:
    lines: List[str] = []
    for raw in body.splitlines():
        line = raw.strip("\r\n")
        line = re.sub(r"^\s*\*\s?", "", line)
        lines.append(line.rstrip())

    while lines and not lines[0].strip():
        lines.pop(0)
    while lines and not lines[-1].strip():
        lines.pop()
    return lines


def parse_param(rest: str) -> Optional[Param]:
    m = re.match(r"^\((?P<type>[^)]+)\)\s+(?P<name>\S+)\s*(?P<desc>.*)$", (rest or "").strip())
    if not m:
        return None
    return Param(
        type=m.group("type").strip(),
        name=m.group("name").strip(),
        description=m.group("desc").strip(),
    )


def parse_return(rest: str) -> Optional[Returns]:
    m = re.match(r"^\((?P<type>[^)]+)\)\s*(?P<desc>.*)$", (rest or "").strip())
    if not m:
        return None
    return Returns(
        type=m.group("type").strip(),
        description=m.group("desc").strip(),
    )


def parse_block(kind: str, body: str) -> BlockBase:
    lines = clean_block_lines(body)

    desc_lines: List[str] = []
    tag_lines: List[str] = []

    seen_tag = False
    for line in lines:
        if TAG_RE.match(line):
            seen_tag = True
            tag_lines.append(line)
        else:
            if not seen_tag:
                desc_lines.append(line)
            else:
                tag_lines.append(line)

    b = BlockBase(kind=(kind or "").strip().lower())
    b.description = "\n".join(desc_lines).strip()

    in_example = False
    example_acc: List[str] = []

    in_decl = False
    decl_acc: List[str] = []

    for line in tag_lines:
        m = TAG_RE.match(line)
        if m:
            tag = m.group("tag").strip().lower()
            rest = m.group("rest").rstrip()

            if tag != "example" and in_example:
                in_example = False
                b.example_code = "\n".join(example_acc).rstrip()
                example_acc.clear()

            if tag != "declaration" and in_decl:
                in_decl = False
                b.declaration = "\n".join(decl_acc).rstrip()
                decl_acc.clear()

            if tag == "name":
                b.name = rest.strip() or b.name
            elif tag == "version":
                b.version = rest.strip() or b.version
            elif tag == "deprecated":
                b.deprecated = rest.strip() or b.deprecated
            elif tag == "side":
                b.side = normalize_side(rest)
            elif tag == "category":
                b.category = rest.strip() or b.category
            elif tag == "extends":
                # Used by class.md template (definition.extends)
                b.extends = rest.strip() or b.extends
            elif tag in ("note", "notes"):
                if rest.strip():
                    b.notes.append(rest.strip())
            elif tag == "param":
                p = parse_param(rest)
                if p:
                    b.params.append(p)
            elif tag in ("return", "returns"):
                r = parse_return(rest)
                if r:
                    b.returns = r
            elif tag == "cancellable":
                val = rest.strip().lower()
                b.cancellable = val in ("", "1", "true", "yes", "y", "on")
            elif tag == "static":
                val = rest.strip().lower()
                b.static = val in ("", "1", "true", "yes", "y", "on")
            elif tag in ("readonly", "read_only", "read-only"):
                val = rest.strip().lower()
                b.read_only = val in ("", "1", "true", "yes", "y", "on")
            elif tag == "declaration":
                in_decl = True
                if rest.strip():
                    decl_acc.append(rest)
            elif tag == "example":
                in_example = True
                if rest.strip():
                    example_acc.append(rest)
            else:
                # Unknown tag: ignore
                pass
        else:
            if in_example:
                example_acc.append(line)
            if in_decl:
                decl_acc.append(line)

    if in_decl:
        b.declaration = "\n".join(decl_acc).rstrip()

    if in_example:
        b.example_code = "\n".join(example_acc).rstrip()

    if not b.category:
        b.category = "Uncategorized"

    if b.kind == "global" and b.returns is None:
        b.returns = Returns(type="void", description="")

    return b


def build_declaration(block_kind: str, block_name: str | None, params, returns, class_name: str | None = None) -> str:
    """Build a declaration string.

    This is a *documentation* signature, not a fully accurate C++ ABI signature.
    It uses the types provided in @param/@return verbatim.
    """
    params = params or []

    # Constructor uses class name; we return only the arglist, the template adds Vec4.new(...)
    if block_kind == "constructor":
        return ", ".join([f"{p.type} {p.name}".strip() for p in params])

    # Default return type
    ret_type = "void"
    if returns and getattr(returns, "type", None):
        rt = returns.type.strip()
        if rt:
            ret_type = rt

    name = block_name or ""
    args = ", ".join([f"{p.type} {p.name}".strip() for p in params])
    return f"{ret_type} {name}({args})"


# -----------------------------
# Project scan + aggregation
# -----------------------------

DEFAULT_EXTS = {".cpp", ".hpp", ".h"}


def should_scan_file(path: Path, allowed_exts: Optional[set[str]]) -> bool:
    lowered = str(path).lower()
    if any(p in lowered for p in (
        "/.git/", "\\.git\\",
        "/node_modules/", "\\node_modules\\",
        "/dist/", "\\dist\\",
        "/build/", "\\build\\",
        "/.venv/", "\\.venv\\",
        "/vendor/", "\\vendor\\",
    )):
        return False

    if path.suffix.lower() in (".png", ".jpg", ".jpeg", ".webp", ".exe", ".dll", ".so", ".zip", ".7z", ".rar", ".pdf"):
        return False

    if allowed_exts is None:
        return True

    return path.suffix.lower() in allowed_exts


def file_might_contain_docs(path: Path) -> bool:
    """Fast binary pre-scan to avoid decoding files that cannot contain blocks."""
    markers = (b"luagmp (", b"luadoc (")

    try:
        size = path.stat().st_size
        if size == 0:
            return False
        # Avoid extreme files
        if size > 50 * 1024 * 1024:
            return False

        with path.open("rb") as f:
            while True:
                chunk = f.read(256 * 1024)
                if not chunk:
                    return False
                if any(m in chunk for m in markers):
                    return True
    except Exception:
        return False


def read_text_safely(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8", errors="ignore")
    except Exception:
        return path.read_text(encoding="latin-1", errors="ignore")


def scan_blocks(project_dir: Path, allowed_exts: Optional[set[str]], verbose: bool = False) -> List[Tuple[Path, BlockBase]]:
    found: List[Tuple[Path, BlockBase]] = []
    scanned_files = 0
    candidate_files = 0

    for p in project_dir.rglob("*"):
        if not p.is_file():
            continue
        if not should_scan_file(p, allowed_exts):
            continue
        scanned_files += 1

        if not file_might_contain_docs(p):
            continue
        candidate_files += 1

        text = read_text_safely(p)
        for m in BLOCK_RE.finditer(text):
            kind = m.group("kind").strip().lower()
            body = m.group("body")
            found.append((p, parse_block(kind, body)))

    if verbose:
        print(f"Scanned files: {scanned_files} | Candidate files (had markers): {candidate_files} | Blocks: {len(found)}")

    return found


def aggregate(
    blocks: List[Tuple[Path, BlockBase]]
) -> Tuple[Dict[str, ClassDoc], List[BlockBase], List[BlockBase], List[BlockBase], Dict[Tuple[str, str], List[ConstElement]]]:
    classes_by_key: Dict[str, ClassDoc] = {}
    functions: List[BlockBase] = []
    events: List[BlockBase] = []
    globals_: List[BlockBase] = []
    consts_by_cat: Dict[Tuple[str, str], List[ConstElement]] = {}

    # Track "current class" per file for method/property/constructor/callback assignment
    last_class_key_by_file: Dict[Path, str] = {}

    for file_path, b in blocks:
        k = b.kind

        if k == "class":
            if not b.name:
                # If class block missing @name, skip safely
                continue

            key = f"{b.side.value}::{b.category}::{b.name}"
            classes_by_key[key] = ClassDoc(definition=b)
            last_class_key_by_file[file_path] = key

        elif k in ("constructor", "method", "property", "callback"):
            # Assign to nearest prior class in same file
            cls_key = last_class_key_by_file.get(file_path)
            if not cls_key or cls_key not in classes_by_key:
                # No class context; treat as global fallback so it doesn't vanish
                b.declaration = build_declaration("global", b.name, b.params, b.returns, class_name=None)
                globals_.append(b)
                continue

            cls = classes_by_key[cls_key]

            if k == "constructor":
                b.declaration = build_declaration("constructor", b.name, b.params, b.returns, class_name=cls.definition.name)
                cls.constructors.append(b)
            elif k == "method":
                b.declaration = build_declaration("method", b.name, b.params, b.returns, class_name=None)
                cls.methods.append(b)
            elif k == "property":
                cls.properties.append(b)
            elif k == "callback":
                b.declaration = build_declaration("callback", b.name, b.params, b.returns, class_name=None)
                cls.callbacks.append(b)

        elif k in ("func", "function"):
            b.declaration = build_declaration("func", b.name, b.params, b.returns, class_name=None)
            functions.append(b)

        elif k == "event":
            b.declaration = build_declaration("event", b.name, b.params, b.returns, class_name=None)
            events.append(b)

        elif k in ("const", "constant"):
            # Aggregate by side+category; const template expects category + elements
            cat = b.category or "Uncategorized"
            side = b.side.value
            if not b.name:
                continue
            consts_by_cat.setdefault((side, cat), []).append(ConstElement(
                name=b.name,
                description=b.description or "",
            ))

        elif k == "global":
            b.declaration = build_declaration("global", b.name, b.params, b.returns, class_name=None)
            globals_.append(b)

        else:
            # Unknown kind: treat as global so it doesn't get dropped
            b.declaration = build_declaration("global", b.name, b.params, b.returns, class_name=None)
            globals_.append(b)

    return classes_by_key, functions, events, globals_, consts_by_cat


# -----------------------------
# Rendering + output paths
# -----------------------------


def ensure_parent(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)


def write_file(path: Path, content: str) -> None:
    ensure_parent(path)
    path.write_text(content.rstrip() + "\n", encoding="utf-8")


def class_out_path(out_root: Path, cls: ClassDoc) -> Path:
    side = cls.definition.side.value
    cat = slugify(cls.definition.category or "Uncategorized")
    name = cls.definition.name or "UnnamedClass"
    return out_root / f"{side}-classes" / cat / f"{name}.md"


def function_out_path(out_root: Path, fn: BlockBase) -> Path:
    side = fn.side.value
    cat = slugify(fn.category or "Uncategorized")
    name = fn.name or "UnnamedFunction"
    return out_root / f"{side}-functions" / cat / f"{name}.md"


def event_out_path(out_root: Path, ev: BlockBase) -> Path:
    side = ev.side.value
    cat = slugify(ev.category or "Uncategorized")
    name = ev.name or "UnnamedEvent"
    return out_root / f"{side}-events" / cat / f"{name}.md"


def global_out_path(out_root: Path, g: BlockBase) -> Path:
    side = g.side.value
    name = g.name or "UnnamedGlobal"
    # Globals are not nested by category (exception).
    return out_root / f"{side}-globals" / f"{name}.md"


def const_out_path(out_root: Path, side: str, category: str) -> Path:
    safe_name = (category or "Uncategorized").strip() or "Uncategorized"
    # Constants are not nested by category (exception); filename is the category.
    return out_root / f"{side}-constants" / f"{safe_name}.md"


def render_docs(
    out_root: Path,
    env: Environment,
    classes_by_key: Dict[str, ClassDoc],
    functions: List[BlockBase],
    events: List[BlockBase],
    globals_: List[BlockBase],
    consts_by_cat: Dict[Tuple[str, str], List[ConstElement]],
) -> None:
    tpl_class = env.get_template("class.md")
    tpl_func = env.get_template("function.md")
    tpl_event = env.get_template("event.md")
    tpl_global = env.get_template("global.md")
    tpl_const = env.get_template("const.md")

    for _, cls in sorted(
        classes_by_key.items(),
        key=lambda kv: (kv[1].definition.side.value, kv[1].definition.category, kv[1].definition.name or ""),
    ):
        md = tpl_class.render(
            definition=cls.definition,
            constructors=cls.constructors,
            properties=cls.properties,
            methods=cls.methods,
            callbacks=cls.callbacks,
        )
        write_file(class_out_path(out_root, cls), md)

    for fn in functions:
        if not fn.name:
            continue
        md = tpl_func.render(**fn.__dict__)
        write_file(function_out_path(out_root, fn), md)

    for ev in events:
        if not ev.name:
            continue
        md = tpl_event.render(**ev.__dict__)
        write_file(event_out_path(out_root, ev), md)

    for g in globals_:
        if not g.name:
            g.name = "Global"
        md = tpl_global.render(**g.__dict__)
        write_file(global_out_path(out_root, g), md)

    for (side, category), elements in consts_by_cat.items():
        md = tpl_const.render(
            side=Side(side),
            category=category,
            elements=elements,
        )
        write_file(const_out_path(out_root, side, category), md)


# -----------------------------
# Output directory cleaning
# -----------------------------


def clean_output_root(out_root: Path) -> None:
    """Delete all contents of the output root, but keep the root directory itself.

    This ensures that:
    - Removed/renamed entities disappear from docs
    - No stale Markdown files remain between runs
    """
    if not out_root.exists():
        return

    for p in out_root.iterdir():
        try:
            if p.is_file() or p.is_symlink():
                p.unlink()
            elif p.is_dir():
                shutil.rmtree(p)
        except Exception as exc:
            print(f"WARN: Failed to remove {p}: {exc}", file=sys.stderr)


# -----------------------------
# CLI
# -----------------------------


def parse_exts(raw: str) -> Optional[set[str]]:
    raw = (raw or "").strip()
    if not raw:
        return set(DEFAULT_EXTS)
    if raw == "*":
        return None
    parts = [p.strip() for p in raw.split(",") if p.strip()]
    exts = set()
    for p in parts:
        if not p.startswith("."):
            p = "." + p
        exts.add(p.lower())
    return exts or set(DEFAULT_EXTS)


def main(argv: List[str]) -> int:
    ap = argparse.ArgumentParser(description="Generate Markdown docs from luagmp comment blocks.")
    ap.add_argument("--project", required=True, help="Path to source project directory to scan.")
    ap.add_argument("--out", required=True, help="Output docs root directory.")
    ap.add_argument("--templates", required=True, help="Path to templates directory or templates.zip.")
    ap.add_argument(
        "--ext",
        default=".cpp,.hpp,.h",
        help='Comma-separated list of file extensions to scan. Default: .cpp,.hpp,.h. Use "*" to scan all.',
    )
    ap.add_argument("--verbose", action="store_true", help="Print scan statistics.")
    args = ap.parse_args(argv)

    project_dir = Path(args.project).expanduser().resolve()
    out_root = Path(args.out).expanduser().resolve()
    templates_path = Path(args.templates).expanduser().resolve()

    if not project_dir.is_dir():
        print(f"ERROR: --project is not a directory: {project_dir}", file=sys.stderr)
        return 2

    templates_dir = load_templates_source(templates_path)
    env = build_jinja_env(templates_dir)

    allowed_exts = parse_exts(args.ext)
    blocks = scan_blocks(project_dir, allowed_exts, verbose=args.verbose)

    classes_by_key, functions, events, globals_, consts_by_cat = aggregate(blocks)

    # Clean existing docs before writing new ones
    if out_root.exists():
        clean_output_root(out_root)
    else:
        out_root.mkdir(parents=True, exist_ok=True)

    render_docs(out_root, env, classes_by_key, functions, events, globals_, consts_by_cat)

    print(f"Done. Parsed {len(blocks)} blocks.")
    print(
        f"Classes: {len(classes_by_key)} | Functions: {len(functions)} | Events: {len(events)} | "
        f"Globals: {len(globals_)} | Const categories: {len(consts_by_cat)}"
    )
    print(f"Output: {out_root}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
