#!/usr/bin/env python3
"""Genera derivados desde URLs de Apps Script aún no presentes localmente.

Los originales remotos nunca se incorporan al repositorio: se descargan a un
archivo temporal sólo para obtener los WebP y quedan referenciados por su URL
en el manifiesto como respaldo.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import tempfile
import time
import urllib.request
from pathlib import Path

from optimize_catalog_images import SETTINGS, atomic_json, generate, image_info, reusable


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def download(url: str, destination: Path) -> None:
    request = urllib.request.Request(url, headers={"User-Agent": "Mágico-Amor-image-optimizer/1.0"})
    with urllib.request.urlopen(request, timeout=60) as response, destination.open("wb") as stream:
        shutil.copyfileobj(response, stream)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo", type=Path, default=Path.cwd())
    parser.add_argument("--only-url", action="append", default=[])
    args = parser.parse_args()
    repo = args.repo.resolve()
    root = repo / "catalogo-fotos"
    inventory_path, manifest_path = root / "inventario-catalogo.json", root / "manifest.json"
    inventory = json.loads(inventory_path.read_text(encoding="utf-8"))
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    images = manifest.setdefault("images", {})
    pending = [item for item in inventory["url_usage"] if item["match_status"] == "pending"]
    if args.only_url:
        wanted = set(args.only_url)
        pending = [item for item in pending if item["url"] in wanted]
    if not pending:
        raise SystemExit("No hay URLs remotas pendientes para procesar")

    records = []
    with tempfile.TemporaryDirectory(prefix="magicoamor-remote-") as temp_name:
        temp = Path(temp_name)
        for item in pending:
            url = item["url"]
            key = hashlib.sha256(url.encode("utf-8")).hexdigest()[:12]
            original = temp / f"{key}.source"
            download(url, original)
            info = image_info(original)
            info["sha256"] = sha256(original)
            entry = {
                "original_file": None,
                "original_url": url,
                "original_sha256": info["sha256"],
            }
            for variant in ("card", "gallery"):
                destination = root / "derivados" / f"{key}-remote-{variant}.webp"
                limit = 150_000 if variant == "card" else 350_000
                remote_webp_reusable = (info["format"] == "WEBP"
                    and max(info["width"], info["height"]) <= SETTINGS[variant]["max_dimension"]
                    and info["bytes"] <= limit)
                if remote_webp_reusable:
                    destination.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copy2(original, destination)
                    result = {"reused_remote_webp": True, **image_info(destination)}
                else:
                    result = generate(original, destination, SETTINGS[variant])
                entry[variant] = destination.relative_to(repo).as_posix()
                entry[f"{variant}_meta"] = result
            images[url] = entry
            item["match_status"] = "remote_url"
            item["original_file"] = None
            item["original_url"] = url
            item["metadata"] = info
            records.append({"url": url, "card": entry["card"], "gallery": entry["gallery"], "source": info})

    manifest.update(version=2, generator="tools/optimize_remote_catalog_images.py", settings=SETTINGS)
    inventory["generated_at"] = time.strftime("%Y-%m-%dT%H:%M:%S%z")
    inventory["summary"]["matched_catalog_urls"] = sum(item["match_status"] in {"exact_url_path", "remote_url"} for item in inventory["url_usage"])
    inventory["summary"]["pending_catalog_urls"] = sum(item["match_status"] == "pending" for item in inventory["url_usage"])
    atomic_json(manifest_path, manifest)
    atomic_json(inventory_path, inventory)
    print(json.dumps({"processed": len(records), "records": records}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
