#!/usr/bin/env python3
"""Speedup de multiprocessing con tareas CPU-bound."""
from multiprocessing import Pool
import time
import math

def cpu_task(n):
    """Tarea CPU-intensive: sumar raíces cuadradas."""
    return sum(math.sqrt(i) for i in range(n))

N = 500_000
TAREAS = 8

if __name__ == "__main__":
    # Secuencial
    inicio = time.time()
    resultados = [cpu_task(N) for _ in range(TAREAS)]
    t_seq = time.time() - inicio
    print(f"Secuencial:  {t_seq:.2f}s")

    # Con distintos números de workers
    for workers in [1, 2, 4, 8, 16]:
        inicio = time.time()
        with Pool(workers) as pool:
            resultados = pool.map(cpu_task, [N] * TAREAS)
        t_par = time.time() - inicio
        speedup = t_seq / t_par
        print(f"Pool({workers}):    {t_par:.2f}s  (speedup: {speedup:.2f}x)")
        
#Secuencial:  0.66s
#Pool(1):    0.50s  (speedup: 1.34x)    Cuando se agregan mas de 4 workers,
#Pool(4):    0.26s  (speedup: 2.51x)    el tiempo no mejora mucho,
#Pool(8):    0.26s  (speedup: 2.52x)    porque el overhead de crear procesos 
#Pool(16):    0.28s  (speedup: 2.41x)   y comunicarse entre ellos empieza a dominar.gi