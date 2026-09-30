#!/usr/bin/env python3
"""Construye un artefacto mínimo y seguro para magicoamor-preview."""
from __future__ import annotations
import argparse, json, re, shutil
from pathlib import Path

DEFAULT_URL = "https://magicoamorbebe-bot.github.io/magicoamor-preview/"

def replace_once(text: str, old: str, new: str) -> str:
    if text.count(old) != 1:
        raise RuntimeError(f"Se esperaba una coincidencia exacta y se encontraron {text.count(old)}: {old[:80]}")
    return text.replace(old, new, 1)

def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--repo", type=Path, default=Path.cwd())
    ap.add_argument("--output", type=Path, required=True)
    ap.add_argument("--base-url", default=DEFAULT_URL)
    args = ap.parse_args()
    repo, output = args.repo.resolve(), args.output.resolve()
    if output == repo or repo in output.parents:
        raise SystemExit("El artefacto debe generarse fuera del repositorio fuente")
    if output.exists() and any(output.iterdir()):
        raise SystemExit("La carpeta de salida debe estar vacía")
    output.mkdir(parents=True, exist_ok=True)

    manifest = json.loads((repo / "catalogo-fotos" / "manifest.json").read_text(encoding="utf-8"))
    inventory = json.loads((repo / "catalogo-fotos" / "inventario-catalogo.json").read_text(encoding="utf-8"))
    references = sorted({entry[variant] for entry in manifest["images"].values() for variant in ("card", "gallery")})
    if any("://" in ref or ref.startswith(("/", "\\")) or ".." in Path(ref).parts for ref in references):
        raise SystemExit("El manifiesto contiene una ruta optimizada no relativa")

    html = (repo / "index.html").read_text(encoding="utf-8")
    html = replace_once(html, '<meta name="viewport" content="width=device-width, initial-scale=1.0">',
        '<meta name="viewport" content="width=device-width, initial-scale=1.0">\n<meta name="robots" content="noindex,nofollow,noarchive">')
    html = html.replace("https://magicoamor.com.ar/", args.base_url)
    html = replace_once(html, "const API='https://script.google.com/macros/s/AKfycbwMPJaJR-gaCL2I1zqeM8AZqCxfve_3EeoqlpeIZndvHE0OHP7gOLjCKo6YH3pBl7o/exec';",
        "const API='https://script.google.com/macros/s/AKfycbwMPJaJR-gaCL2I1zqeM8AZqCxfve_3EeoqlpeIZndvHE0OHP7gOLjCKo6YH3pBl7o/exec';\nconst PREVIEW_MODE=true;")
    html = replace_once(html, "emailjs.init(EJS_PUBLIC_KEY);", "// EmailJS deshabilitado en la vista previa")
    html = replace_once(html, "async function enviarExperiencia(){", "async function enviarExperiencia(){\nif(PREVIEW_MODE){alert('Vista previa: envíos deshabilitados.');return;}")
    html = replace_once(html, "async function sendOrderEmail(p){", "async function sendOrderEmail(p){\nif(PREVIEW_MODE)return;")
    html = replace_once(html, "function openCheckout(){", "function openCheckout(){\nif(PREVIEW_MODE){alert('Vista previa: pedidos deshabilitados.');return;}")
    html = replace_once(html, "window.confirmOrder=async function(){", "window.confirmOrder=async function(){\nif(PREVIEW_MODE){alert('Vista previa: pedidos deshabilitados.');return;}")
    html = replace_once(html, "async function sendChat(){", "async function sendChat(){\nif(PREVIEW_MODE){addMsg('Vista previa: chat deshabilitado.','bot');return;}")
    banner = '<div style="position:sticky;top:0;z-index:1000;background:#7a5110;color:white;text-align:center;padding:7px;font:600 12px system-ui">VISTA PREVIA — pedidos y envíos deshabilitados</div>'
    html = replace_once(html, "<body>", "<body>\n" + banner)
    (output / "index.html").write_text(html, encoding="utf-8", newline="\n")

    for filename in ("logo.png", "agus-mateo.jpg"):
        shutil.copy2(repo / filename, output / filename)
    target_manifest = output / "catalogo-fotos" / "manifest.json"
    target_manifest.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(repo / "catalogo-fotos" / "manifest.json", target_manifest)
    for ref in references:
        source, target = repo / ref, output / ref
        if not source.is_file():
            raise SystemExit(f"Falta un optimizado: {ref}")
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, target)
    (output / ".nojekyll").write_text("", encoding="utf-8")
    (output / "robots.txt").write_text("User-agent: *\nDisallow: /\n", encoding="utf-8", newline="\n")
    summary = {"products_expected": inventory["summary"]["catalog_products"], "manifest_entries": len(manifest["images"]),
               "optimized_files": len(references), "base_url": args.base_url,
               "contains_cname": (output / "CNAME").exists(), "preview_mode": True}
    (output / "preview-summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False))

if __name__ == "__main__":
    main()
