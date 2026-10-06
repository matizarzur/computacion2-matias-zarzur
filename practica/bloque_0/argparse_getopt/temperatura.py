#!/usr/bin/env python3
"""
Convierte temperaturas entre Celsius y Fahrenheit.
Uso: temperatura.py <valor> -t {celsius,fahrenheit}
"""
import argparse
import sys


def crear_parser():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("valor", type=float, help="Temperatura a convertir")
    parser.add_argument("-t", "--to", required=True, choices=["celsius", "fahrenheit"], help="Unidad de destino")
    return parser


def procesar(args):
    if args.to == "fahrenheit":
        resultado = (args.valor * 9 / 5) + 32
        print(f"{args.valor:g}°C = {resultado:.1f}°F")
    else:
        resultado = (args.valor - 32) * 5 / 9
        print(f"{args.valor:g}°F = {resultado:.2f}°C")
    return True


def main():
    parser = crear_parser()
    args = parser.parse_args()
    try:
        exito = procesar(args)
        sys.exit(0 if exito else 1)
    except KeyboardInterrupt:
        print("\nInterrumpido", file=sys.stderr)
        sys.exit(130)
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()