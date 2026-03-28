import argparse
import sys
import secrets
import string

symbols= "!@#$%&"
letras= string.ascii_letters
numeros=string.digits


def crear_parser():
    parser= argparse.ArgumentParser(description="Generador de contraseñas sguras.")
    parser.add_argument("-n", "--length", type=int, default=12, help="Longitud de la contraseña por predeterminado")
    parser.add_argument("--no-symbols", action="store_true", help="Contraseña sin simbolos")
    parser.add_argument("--no-numbers",action="store_true", help="Contraseña sin numeros")
    parser.add_argument("--count",type=int, default=1, help="Cantidad de contraseñas a generar")
    return parser

def main():
    parser = crear_parser()
    args = parser.parse_args()
    generar_contraseñas(args)

def generar_contraseñas(args):
    pool = letras
    if not args.no_numbers:
        pool += numeros
    if not args.no_symbols:
        pool += symbols
    
    for i in range(args.count):
        password= "".join(secrets.choice(pool) for i in range(args.length))
        print(password)

if __name__== "__main__":
    main()