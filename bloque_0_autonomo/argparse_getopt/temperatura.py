import sys
import argparse


def main():
    parser = argparse.ArgumentParser(
        description="Convierte temperaturas entre Celsius y Fahrenheit."
    )

    parser.add_argument(
        "valor",
        type=float,
        help="Temperatura a convertir"
    )

    parser.add_argument(
        "-t", "--to",
        required=True,
        choices=["celsius", "fahrenheit"],
        help="Unidad de destino"
    )

    args = parser.parse_args()

    if args.to == "fahrenheit":
        resultado = (args.valor * 9 / 5) + 32
        print(f"{args.valor:g}°C = {resultado:.1f}°F")
    else:
        resultado = (args.valor - 32) * 5 / 9
        print(f"{args.valor:g}°F = {resultado:.2f}°C")

    sys.exit(0)


if __name__ == "__main__":
    main()
