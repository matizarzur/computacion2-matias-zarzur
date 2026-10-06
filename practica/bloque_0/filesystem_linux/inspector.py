#!/usr/bin/env python3
"""
Inspector de archivos: muestra información detallada sobre cualquier archivo.
Uso: inspector.py <ruta>
"""
import argparse
import grp
import os
import pwd
import stat
import sys
from datetime import datetime
from pathlib import Path


def crear_parser():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("ruta", help="Ruta del archivo a inspeccionar")
    return parser


def tipo_archivo(modo):
    if stat.S_ISREG(modo):
        return "archivo regular"
    elif stat.S_ISDIR(modo):
        return "directorio"
    elif stat.S_ISLNK(modo):
        return "enlace simbólico"
    elif stat.S_ISCHR(modo):
        return "dispositivo de caracteres"
    elif stat.S_ISBLK(modo):
        return "dispositivo de bloques"
    elif stat.S_ISFIFO(modo):
        return "pipe (FIFO)"
    elif stat.S_ISSOCK(modo):
        return "socket"
    return "desconocido"


def permisos_str(modo):
    perms = ""
    for quien in [(stat.S_IRUSR, stat.S_IWUSR, stat.S_IXUSR),
                  (stat.S_IRGRP, stat.S_IWGRP, stat.S_IXGRP),
                  (stat.S_IROTH, stat.S_IWOTH, stat.S_IXOTH)]:
        perms += "r" if modo & quien[0] else "-"
        perms += "w" if modo & quien[1] else "-"
        perms += "x" if modo & quien[2] else "-"
    return perms


def tamanio_legible(bytes):
    for unidad in ["bytes", "KB", "MB", "GB"]:
        if bytes < 1024:
            return f"{bytes:.2f} {unidad}"
        bytes /= 1024
    return f"{bytes:.2f} TB"


def formato_fecha(timestamp):
    return datetime.fromtimestamp(timestamp).strftime("%Y-%m-%d %H:%M:%S")


def inspeccionar(ruta_str):
    ruta = Path(ruta_str)

    if not ruta.exists() and not ruta.is_symlink():
        print(f"Error: '{ruta_str}' no existe", file=sys.stderr)
        return False

    info = ruta.lstat()
    modo = info.st_mode
    tipo = tipo_archivo(modo)

    if ruta.is_symlink():
        destino = os.readlink(ruta)
        tipo = f"enlace simbólico -> {destino}"

    try:
        usuario = pwd.getpwuid(info.st_uid).pw_name
    except KeyError:
        usuario = str(info.st_uid)

    try:
        grupo = grp.getgrgid(info.st_gid).gr_name
    except KeyError:
        grupo = str(info.st_gid)

    perms = permisos_str(modo)
    octal = oct(stat.S_IMODE(modo))[2:]
    tamanio = info.st_size

    print(f"Archivo: {ruta}")
    print(f"Tipo: {tipo}")
    print(f"Tamaño: {tamanio} bytes ({tamanio_legible(tamanio)})")
    print(f"Permisos: {perms} ({octal})")
    print(f"Propietario: {usuario} (uid: {info.st_uid})")
    print(f"Grupo: {grupo} (gid: {info.st_gid})")
    print(f"Inodo: {info.st_ino}")
    print(f"Enlaces duros: {info.st_nlink}")
    print(f"Último acceso: {formato_fecha(info.st_atime)}")
    print(f"Última modificación: {formato_fecha(info.st_mtime)}")
    print(f"Último cambio: {formato_fecha(info.st_ctime)}")

    if ruta.is_dir() and not ruta.is_symlink():
        elementos = len(list(ruta.iterdir()))
        print(f"Contenido: {elementos} elementos")

    return True


def main():
    parser = crear_parser()
    args = parser.parse_args()
    try:
        exito = inspeccionar(args.ruta)
        sys.exit(0 if exito else 1)
    except KeyboardInterrupt:
        print("\nInterrumpido", file=sys.stderr)
        sys.exit(130)
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()