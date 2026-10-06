from multiprocessing import Pool
import time

def procesar(x):
    time.sleep(0.5)  # Simular trabajo
    return x ** 2

if __name__ == "__main__":
    # Crear pool con 4 procesos
    with Pool(4) as pool:
        time.sleep(30) 
        # map: aplica función a cada elemento (bloquea hasta terminar todo)
        resultados = pool.map_async(procesar, range(10))
        time.sleep(20)
        print(f"map: {resultados.get()}")