import asyncio

CENTINELA = object()

async def procesar(tarea):
    await asyncio.sleep(0.05)
    print(f"{tarea} termino ok.")

async def worker(cola):
    while True:
        item = await cola.get()
        if item is CENTINELA:
            cola.task_done()
            break                             # salida ordenada
        try:
            await procesar(item)
        finally:
            cola.task_done()

#faltaba el MAIN LOOP:

async def main():
    cola = asyncio.Queue()
    workers = [asyncio.create_task(worker(cola)) for _ in range (3)]

#encolar tareas
    for i in range (6):
        await cola.put(f"tareas-{i}")

# Para parar N workers, hay que poner N centinelas
    for _ in range(len(workers)):
        await cola.put(CENTINELA)

    await asyncio.gather(*workers)


asyncio.run(main())