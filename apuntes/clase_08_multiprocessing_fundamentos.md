Pool
El problema que resuelve Pool es simple: crear un Process por cada tarea es muy caro. Si tenés 1000 tareas, crear y destruir 1000 procesos es lentísimo.
                    ┌─ Worker 1 ─┐
Tareas →  Pool  →   ├─ Worker 2 ─┤  → Resultados
[0..999]            ├─ Worker 3 ─┤
                    └─ Worker 4 ─┘

map-Bloquea hasta que todas las tareas terminen y te devuelve los resultados en el mismo orden que la entrada.

imap — igual que map pero te devuelve un iterador, podés ir consumiendo resultados a medida que terminan sin esperar a todos.

imap_unordered — igual que imap pero te entrega los resultados en el orden en que terminan, no en el orden original. Es el más rápido cuando no te importa el orden.

apply_async — lanzás una sola tarea sin bloquear, te devuelve un objeto "futuro" y después pedís el resultado cuando lo necesitás.

starmap — como map pero para funciones con múltiples argumentos. Le pasás una lista de tuplas y desempaqueta cada una.

¿¿Que es un iterador??