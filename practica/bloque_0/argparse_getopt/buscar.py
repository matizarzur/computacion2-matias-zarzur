#!/usr/bin/env python3
"""
Búsqueda de texto en archivos, estilo grep.
Uso: buscar.py <patron> [archivos] [-i] [-n] [-c] [-v]
"""
import argparse
import sys

def crear_parser():
    parser = argparse.ArgumentParser(description="Herramienta mini-grep")
    parser.add_argument("patron", help="Texto a buscar")
    parser.add_argument("archivos", nargs="*", help="Archivos donde buscar")
    parser.add_argument("-i","--ignore-case", action="store_true", help="búsqueda insensible a mayúsculas" )
    parser.add_argument("-n","--line-number", action="store_true", help="mostrar número de línea")
    parser.add_argument("-c", "--count", action="store_true", help="mostrar conteo de conincidencias")
    parser.add_argument("-v", "--invert", action="store_true", help="mostrar lineas que no coinciden")
    return parser

def main():
    parser=crear_parser()
    args = parser.parse_args()
    buscar(args)
    

def buscar(args):
    if args.archivos:
        archivos = args.archivos
    else:
        archivos = [None]

    total = 0

    for archivo in archivos:
        if archivo is None:
            lineas = sys.stdin.readlines()
            nombre = None
        else:
            try:
                with open(archivo, "r") as f:
                    lineas = f.readlines()
                nombre = archivo
            except FileNotFoundError:
                print(f"Error: no se puede leer '{archivo}'", file=sys.stderr)
                continue
        coincidencias = 0
        for num, linea in enumerate(lineas, 1):
            linea = linea.rstrip("\n")
            patron = args.patron
            texto = linea
            
            if args.ignore_case:
                patron = patron.lower()
                texto = texto.lower()
            encontrado = patron in texto
            
            if args.invert:
                encontrado = not encontrado
                
            if encontrado:
                coincidencias += 1
                if not args.count:
                    prefijo = f"{nombre}:{num}: " if nombre else ""
                    print(f"{prefijo}{linea}")
                    
        if args.count:
            print(f"{nombre}: {coincidencias} coincidencias")
            total += coincidencias
            
    if args.count and len(archivos) > 1:
        print(f"Total: {total} coincidencias")

if __name__ == "__main__":
    main()