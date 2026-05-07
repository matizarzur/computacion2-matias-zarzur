#!/usr/bin/env python3
"""Pipeline de dos comandos: cmd1 | cmd2"""
import os

def pipeline_dos_comandos(cmd1, args1, cmd2, args2):
    """Ejecuta cmd1 | cmd2"""
    read_fd, write_fd = os.pipe()

    pid1 = os.fork()
    if pid1 == 0:
        os.close(read_fd)
        os.dup2(write_fd, 1)
        os.close(write_fd)
        os.execvp(cmd1, [cmd1] + args1)
        os._exit(1)

    pid2 = os.fork()
    if pid2 == 0:
        os.close(write_fd)
        os.dup2(read_fd, 0)
        os.close(read_fd)
        os.execvp(cmd2, [cmd2] + args2)
        os._exit(1)

    os.close(read_fd)
    os.close(write_fd)
    os.waitpid(pid1, 0)
    os.waitpid(pid2, 0)

if __name__ == "__main__":
    print("=== ls -la | grep '.py' ===")
    pipeline_dos_comandos("ls", ["-la"], "grep", [".py"])