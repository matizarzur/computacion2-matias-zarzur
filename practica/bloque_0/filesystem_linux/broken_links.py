#!/usr/bin/env python3
"""
Detector de enlaces simbólicos rotos en un directorio.
Uso: broken_links.py <directorio> [--delete] [--quiet]
"""
import argparse
import sys
from pathlib import Path


def crear_parser():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("directorio", help="Directorio donde buscar")
    parser.add_argument("--delete", action="store_true", help="Ofrecer borrar los enlaces rotos")
    parser.add_argument("--quiet", action="store_true", help="Solo mostrar el conteo")
    return parser


def buscar_rotos(args):
    ruta = Path(args.directorio)

    if not ruta.is_dir():
        print(f"Error: '{args.directorio}' no es un directorio válido", file=sys.stderr)
        return False

    rotos = []
    for item in ruta.rglob("*"):
        try:
            if item.is_symlink() and not item.exists():
                destino = item.readlink()
                rotos.append((item, destino))
        except PermissionError:
            continue

    if args.quiet:
        print(len(rotos))
        return True

    if not rotos:
        print("No se encontraron enlaces rotos.")
        return True

    print(f"Buscando enlaces simbólicos rotos en {args.directorio}...\n")
    print("Enlaces rotos encontrados:")
    for enlace, destino in rotos:
        print(f"  {enlace} -> {destino} (no existe)")

    print(f"\nTotal: {len(rotos)} enlaces rotos")

    if args.delete:
        print()
        for enlace, destino in rotos:
            respuesta = input(f"¿Eliminar '{enlace}'? [s/N] ")
            if respuesta.lower() == "s":
                enlace.unlink()
                print(f"  Eliminado.")

    return True


def main():
    parser = crear_parser()
    args = parser.parse_args()
    try:
        exito = buscar_rotos(args)
        sys.exit(0 if exito else 1)
    except KeyboardInterrupt:
        print("\nInterrumpido", file=sys.stderr)
        sys.exit(130)
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()