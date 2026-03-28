import argparse
import json
import sys
from pathlib import Path

ARCHIVO_TAREAS = Path.home() / ".tareas.json"


def cargar_tareas():
    if ARCHIVO_TAREAS.exists():
        with open(ARCHIVO_TAREAS, "r") as f:
            return json.load(f)
    return []


def guardar_tareas(tareas):
    with open(ARCHIVO_TAREAS, "w") as f:
        json.dump(tareas, f, indent=2)


def crear_parser():
    parser = argparse.ArgumentParser(description="Gestor de tareas")
    subparsers = parser.add_subparsers(dest="comando")

    # add
    parser_add = subparsers.add_parser("add", help="Agregar tarea")
    parser_add.add_argument("descripcion", help="Descripción de la tarea")
    parser_add.add_argument("--priority", choices=["baja", "media", "alta"], help="Prioridad")

    # list
    parser_list = subparsers.add_parser("list", help="Listar tareas")
    parser_list.add_argument("--pending", action="store_true", help="Solo pendientes")
    parser_list.add_argument("--done", action="store_true", help="Solo completadas")
    parser_list.add_argument("--priority", choices=["baja", "media", "alta"], help="Filtrar por prioridad")

    # done
    parser_done = subparsers.add_parser("done", help="Marcar tarea como completada")
    parser_done.add_argument("id", type=int, help="ID de la tarea")

    # remove
    parser_remove = subparsers.add_parser("remove", help="Eliminar tarea")
    parser_remove.add_argument("id", type=int, help="ID de la tarea")

    return parser


def cmd_add(args):
    tareas = cargar_tareas()
    nueva = {
        "id": len(tareas) + 1,
        "descripcion": args.descripcion,
        "priority": args.priority,
        "completada": False
    }
    tareas.append(nueva)
    guardar_tareas(tareas)
    if args.priority:
        print(f"Tarea #{nueva['id']} agregada (prioridad: {args.priority})")
    else:
        print(f"Tarea #{nueva['id']} agregada")


def cmd_list(args):
    tareas = cargar_tareas()

    for t in tareas:
        if args.pending and t["completada"]:
            continue
        if args.done and not t["completada"]:
            continue
        if args.priority and t["priority"] != args.priority:
            continue

        estado = "x" if t["completada"] else " "
        prioridad = f" [{t['priority'].upper()}]" if t["priority"] else ""
        print(f"#{t['id']} [{estado}] {t['descripcion']}{prioridad}")


def cmd_done(args):
    tareas = cargar_tareas()
    for t in tareas:
        if t["id"] == args.id:
            t["completada"] = True
            guardar_tareas(tareas)
            print(f"Tarea #{args.id} completada")
            return
    print(f"Error: no existe la tarea #{args.id}", file=sys.stderr)
    sys.exit(1)


def cmd_remove(args):
    tareas = cargar_tareas()
    for t in tareas:
        if t["id"] == args.id:
            confirmacion = input(f"¿Eliminar \"{t['descripcion']}\"? [s/N] ")
            if confirmacion.lower() == "s":
                tareas.remove(t)
                guardar_tareas(tareas)
                print(f"Tarea #{args.id} eliminada")
            return
    print(f"Error: no existe la tarea #{args.id}", file=sys.stderr)
    sys.exit(1)


def main():
    parser = crear_parser()
    args = parser.parse_args()

    if args.comando == "add":
        cmd_add(args)
    elif args.comando == "list":
        cmd_list(args)
    elif args.comando == "done":
        cmd_done(args)
    elif args.comando == "remove":
        cmd_remove(args)
    else:
        parser.print_help()
        sys.exit(1)

    sys.exit(0)


if __name__ == "__main__":
    main()