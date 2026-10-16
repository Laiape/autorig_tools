"""One-off, reversible asset migration. Run without --apply to inspect the plan."""
from pathlib import Path
import collections
import datetime
import hashlib
import json
import os
import re
import shutil
import sys

ROOT = Path(__file__).resolve().parents[1]
ASSETS = ROOT / "maya_tools/assets"
STAMP = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
BACKUP = ROOT / "recovery" / ("asset_cleanup_" + STAMP)
TEXT = {".py", ".md", ".txt", ".json", ".mel", ".mod", ".guides", ".curves",
        ".build", ".skc", ".ma", ".skinmap", ".weights", ".shp", ".svg"}
CATEGORIES = {"guides", "curves", "build", "skin_clusters", "models", "scenes", "corrective_blendshapes"}
VERSION = re.compile(r"(?:_v|_)(\d+)(?=\.)")
assets = sorted(p for p in ASSETS.iterdir() if p.is_dir())
names = {p.name: p.name[:1].upper() + p.name[1:] for p in assets if p.name != "chihuahua_v001"}
files = sorted(p for p in ASSETS.rglob("*") if p.is_file())

def checked(path, base):
    result = path.resolve()
    if not result.is_relative_to(base.resolve()) or result == base.resolve():
        raise RuntimeError("Unsafe migration path: " + str(result))
    return result

def version(p):
    m = VERSION.search(p.name)
    return int(m.group(1)) if m else -1

def external_files():
    for base in [ROOT / "scripts", ROOT / "modulos", ROOT / "maya_tools/scripts", ROOT / "maya_tools/docs"]:
        for p in base.rglob("*"):
            if p.is_file() and p.suffix in TEXT and "__pycache__" not in p.parts:
                yield p
    yield from ROOT.glob("*.md")
    yield ROOT / "maya_tools/how_it_works.md"

remove = {}
redirect = {}
families = collections.defaultdict(list)
hashes = collections.defaultdict(list)
for p in files:
    rel = p.relative_to(ASSETS)
    if "__pycache__" in rel.parts or ".mayaSwatches" in rel.parts or re.search(r"\.bak\d*$", p.name):
        remove[p] = "regenerable cache or backup"
        continue
    if rel.parts[0] == "chihuahua_v001":
        remove[p] = "duplicate picker; only character label and shape UUIDs differ"
        continue
    if p.name == "Edward_reference_picker_assets.zip":
        remove[p] = "superseded export of reference_workflow directory"
        continue
    if len(rel.parts) == 3 and rel.parts[1] in CATEGORIES and version(p) >= 0:
        # Model prefixes CHAR_ and plain character refer to the same model family.
        stem = VERSION.sub("_VERSION", p.name)
        if rel.parts[1] == "models":
            stem = stem.removeprefix("CHAR_")
        families[(rel.parts[0], rel.parts[1], stem.casefold())].append(p)
        with p.open("rb") as stream:
            digest = hashlib.file_digest(stream, "sha256").hexdigest()
        hashes[(rel.parts[0], rel.parts[1], p.suffix, digest)].append(p)
    elif len(rel.parts) == 2 and p.suffix == ".pdf" and version(p) >= 0:
        families[(rel.parts[0], "feedback", VERSION.sub("_VERSION", p.name))].append(p)

for group in hashes.values():
    canonical = max(group, key=lambda p: (version(p), p.name))
    for p in group:
        if p != canonical:
            redirect[p] = canonical
            remove[p] = "byte-identical duplicate of " + str(canonical.relative_to(ASSETS))

candidates = set()
for group in families.values():
    remaining = [p for p in group if p not in redirect]
    if not remaining:
        continue
    newest = max(remaining, key=lambda p: (version(p), p.name))
    selected = max(remaining, key=lambda p: (p.stat().st_mtime_ns, version(p)))
    for p in remaining:
        if p not in {newest, selected}:
            candidates.add(p)

# Preserve explicit dependencies transitively, including baselines used by tests/docs.
external = sorted(set(external_files()))
retained = set(files) - set(remove) - candidates
protected = {}
all_names = {p.name.encode(): p for p in candidates}
all_names.update({p.name.encode(): target for p, target in redirect.items()})
name_pattern = re.compile(rb'(?<![A-Za-z0-9_])[A-Za-z][A-Za-z0-9_]{0,80}_v[0-9]{3,4}\.(?:guides|curves|build|ma|mb|skc|json|weights)(?![A-Za-z])')
queue = list(retained) + external
while queue:
    p = queue.pop()
    if p.suffix not in TEXT | {".mb"}:
        continue
    data = p.read_bytes()
    for match in name_pattern.finditer(data):
        dependency = all_names.get(match.group())
        if dependency is None:
            continue
        if dependency not in retained:
            retained.add(dependency)
            protected[dependency] = str(p.relative_to(ROOT))
            queue.append(dependency)
for p in candidates - retained:
    remove[p] = "superseded unreferenced version"

def new_filename(name):
    for old, new in names.items():
        if old == new:
            continue
        name = re.sub(r"(?<![A-Za-z0-9])" + re.escape(old) + r"(?=[_.]|$)", new, name)
    return name

rename = {}
for p in files:
    if p in remove:
        continue
    parts = list(p.relative_to(ASSETS).parts)
    parts[0] = names[parts[0]]
    parts[-1] = new_filename(parts[-1])
    target = ASSETS.joinpath(*parts)
    if str(p) != str(target):
        rename[p] = target

print("Asset folders:", ", ".join(names.values()))
print("Archive files:", len(remove), "MiB:", round(sum(p.stat().st_size for p in remove) / 2**20, 1))
print("Rename files:", len(rename), "Exact duplicates:", len(redirect))
print("Retained referenced historical inputs:")
for p, origin in sorted(protected.items()):
    print(" ", p.relative_to(ASSETS), "<-", origin)

plan = {"backup": str(BACKUP), "remove": {str(p.relative_to(ROOT)): reason for p, reason in remove.items()},
        "rename": {str(p.relative_to(ROOT)): str(q.relative_to(ROOT)) for p, q in rename.items()},
        "redirect": {str(p.relative_to(ROOT)): str(q.relative_to(ROOT)) for p, q in redirect.items()}}
(ROOT / "tmp/asset_cleanup_plan.json").write_text(json.dumps(plan, indent=2), encoding="utf-8")
if "--apply" not in sys.argv:
    sys.exit(0)

# Backup every changed payload before writing, and keep its original mtime.
BACKUP.mkdir(parents=True)
(BACKUP / "manifest.json").write_text(json.dumps(plan, indent=2), encoding="utf-8")
changed = []
def backup(p):
    target = checked(BACKUP / p.relative_to(ROOT), BACKUP)
    if not target.exists():
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(checked(p, ROOT), target)

# Repoint duplicate basenames and character folder/file tokens. Do not capitalize
# anatomical node names such as maui_brow_l_proxyShape or C_horse_geoShape.
replacements = {}
for p, q in redirect.items():
    replacements[p.name.encode()] = new_filename(q.name).encode()
replacements[b"chihuahua_v001_picker.json"] = b"Chihuahua_picker.json"
path_chars = re.compile(rb"(assets[/\\]+)(" + b"|".join(n.encode() for n in names if names[n] != n) + rb")(?=[/\\])")
file_chars = re.compile(rb"(?<![A-Za-z0-9])(" + b"|".join(n.encode() for n in names if names[n] != n) + rb")(?=_(?:v\d|picker|Picker)|\.(?:ma|mb|jpg|png|guides|curves|skc|build|weights)(?:[\"\s]|$))")
dag_chars = re.compile(rb"(?<=\|)(" + b"|".join(n.encode() for n in names if names[n] != n) + rb")(?=\|)")
duplicate_names = re.compile(b"|".join(re.escape(n) for n in sorted(replacements, key=len, reverse=True)))

for p in sorted((set(files) - set(remove)) | set(external)):
    if p.suffix not in TEXT:
        continue
    original = p.read_bytes()
    data = duplicate_names.sub(lambda m: replacements[m.group()], original)
    data = path_chars.sub(lambda m: m[1] + names[m[2].decode()].encode(), data)
    data = file_chars.sub(lambda m: names[m[1].decode()].encode(), data)
    rel = p.relative_to(ASSETS) if p.is_relative_to(ASSETS) else None
    if rel:
        # Full DAG roots follow the newly named rig. JSON guide root keys and
        # picker labels are identity metadata; individual geometry names stay put.
        data = dag_chars.sub(lambda m: names[m[1].decode()].encode(), data)
        old = rel.parts[0]
        new = names[old]
        if old != new:
            if p.suffix == ".guides":
                data = re.sub(rb'("|^)' + re.escape(old.encode()) + rb'(?="\s*:)', lambda m: m[1] + new.encode(), data, count=1)
            if p.suffix == ".ma":
                # A root transform and its references are exact Maya identifiers.
                data = re.sub(rb'"' + re.escape(old.encode()) + rb'"', b'"' + new.encode() + b'"', data)
            if "picker" in rel.parts:
                for key in [b"name", b"character"]:
                    data = re.sub(rb'("' + key + rb'"\s*:\s*")' + re.escape(old.encode()) + rb'(?=[ "])', lambda m: m[1] + new.encode(), data)
                if p.suffix == ".svg":
                    data = data.replace((">" + old + " |").encode(), (">" + new + " |").encode())
    if data != original:
        backup(p)
        stat = p.stat()
        p.write_bytes(data)
        os.utime(p, ns=(stat.st_atime_ns, stat.st_mtime_ns))
        changed.append(str(p.relative_to(ROOT)))

for p, reason in remove.items():
    source = checked(p, ASSETS)
    target = checked(BACKUP / p.relative_to(ROOT), BACKUP)
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.move(str(source), str(target))

# Case-only renames need a temporary name on Windows, also visible to Git.
for p in sorted((set(files) - set(remove))):
    target_name = new_filename(p.name)
    if target_name != p.name:
        checked(p, ASSETS)
        temp = p.with_name(p.name + ".case_migration")
        p.rename(temp)
        temp.rename(p.with_name(target_name))
for p in assets:
    if p.name == "chihuahua_v001":
        continue
    target_name = names[p.name]
    if target_name != p.name:
        checked(p, ASSETS)
        temp = p.with_name(p.name + "_case_migration")
        p.rename(temp)
        temp.rename(p.with_name(target_name))

# Only remove directories made empty by the archive operation.
for p in sorted(ASSETS.rglob("*"), key=lambda p: len(p.parts), reverse=True):
    if p.is_dir() and not any(p.iterdir()):
        checked(p, ASSETS).rmdir()

plan["changed_content"] = changed
(BACKUP / "manifest.json").write_text(json.dumps(plan, indent=2), encoding="utf-8")
(ROOT / "tmp/asset_cleanup_result.json").write_text(json.dumps(plan, indent=2), encoding="utf-8")
print("Updated content:", len(changed))
print("Backup:", BACKUP)
