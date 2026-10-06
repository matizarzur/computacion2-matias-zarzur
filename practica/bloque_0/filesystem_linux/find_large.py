#!/usr/bin/env python3
"""
Buscador de archivos grandes en un directorio.
Uso: find_large.py <directorio> --min-size <tamaño> [--type f|d] [--top N]
"""
import argparse
import sys
from pathlib import Path


def crear_parser():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("directorio", help="Directorio donde buscar")
    parser.add_argument("--min-size", default="1M", help="Tamaño mínimo (ej: 100K, 1M, 1G)")
    parser.add_argument("--type", choices=["f", "d"], help="Filtrar por tipo: f=archivo, d=directorio")
    parser.add_argument("--top", type=int, help="Mostrar solo los N más grandes")
    return parser


def parsear_tamanio(texto):
    texto = texto.strip()
    unidades = {"K": 1024, "M": 1024**2, "G": 1024**3}
    if texto[-1].upper() in unidades:
        return int(float(texto[:-1]) * unidades[texto[-1].upper()])
    return int(texto)


def tamanio_legible(bytes):
    for unidad in ["bytes", "KB", "MB", "GB"]:
        if bytes < 1024:
            return f"{bytes:.1f} {unidad}"
        bytes /= 1024
    return f"{bytes:.1f} TB"


def buscar(args):
    ruta = Path(args.directorio)

    if not ruta.is_dir():
        print(f"Error: '{args.directorio}' no es un directorio válido", file=sys.stderr)
        return False

    min_bytes = parsear_tamanio(args.min_size)
    resultados = []

    for item in ruta.rglob("*"):
        try:
            if item.is_symlink():
                continue
            if args.type == "f" and not item.is_file():
                continue
            if args.type == "d" and not item.is_dir():
                continue
            tamanio = item.stat().st_size
            if tamanio >= min_bytes:
                resultados.append((item, tamanio))
        except PermissionError:
            continue

    resultados.sort(key=lambda x: x[1], reverse=True)

    if args.top:
        print(f"Los {args.top} archivos más grandes:")
        resultados = resultados[:args.top]
        for i, (item, tamanio) in enumerate(resultados, 1):
            print(f"  {i}. {item} ({tamanio_legible(tamanio)})")
    else:
        for item, tamanio in resultados:
            print(f"{item} ({tamanio_legible(tamanio)})")
        total = sum(t for _, t in resultados)
        print(f"Total: {len(resultados)} archivos, {tamanio_legible(total)}")

    return True


def main():
    parser = crear_parser()
    args = parser.parse_args()
    try:
        exito = buscar(args)
        sys.exit(0 if exito else 1)
    except KeyboardInterrupt:
        print("\nInterrumpido", file=sys.stderr)
        sys.exit(130)
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()