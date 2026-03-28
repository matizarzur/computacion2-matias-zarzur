#!/usr/bin/env python3
"""
Lista archivos de un directorio.
Uso: listar.py [directorio] [-a] [--extension .ext]
"""
import argparse
from pathlib import Path
import sys

def main():
    parser = argparse.ArgumentParser(description="Lista archivos de un directorio.")
    parser.add_argument("directorio", nargs="?", default=".", help="Directorio a listar")
    parser.add_argument("-a", "--all", action="store_true", help="Incluir archivos ocultos")
    parser.add_argument("--extension", help="Filtrar por extensión (ej: .py)")
    args = parser.parse_args()

    ruta = Path(args.directorio)

    if not ruta.exists() or not ruta.is_dir():
        print(f"Error: '{args.directorio}' no es un directorio válido", file=sys.stderr)
        sys.exit(1)

    for item in sorted(ruta.iterdir()):
        if not args.all and item.name.startswith("."):
            continue
        if args.extension and item.suffix != args.extension:
            continue
        nombre = item.name + "/" if item.is_dir() else item.name
        print(nombre)

    sys.exit(0)

if __name__ == "__main__":
    main()