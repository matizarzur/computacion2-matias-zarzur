# Dudas TP1

Registro de dudas que fueron surgiendo durante el desarrollo del TP,
con su resolución cuando la hubo.

---

## Sesión 1 

### Duda 1: ¿Por qué el mismo proceso tiene distinto PID adentro y afuera del contenedor?

**Resuelta.** Cada PID namespace tiene su propia numeración. Docker por defecto
crea un namespace nuevo, por eso el PID 1 adentro del contenedor es un PID
distinto (ej: 10704) visto desde el host. Con `pid: host` en docker-compose
se comparte el namespace del host y los PIDs coinciden.

### Duda 2: ¿Cuál es la diferencia entre `Pid` y `Tgid` en `/proc/<pid>/status`?

**Resuelta.** `Tgid` es el PID del proceso principal (del thread group),
`Pid` es el ID del thread individual. Coinciden cuando el proceso es
single-threaded. Los threads en Linux son LWPs (procesos livianos): cada uno
tiene su propio PID pero comparten Tgid con los demás threads del mismo proceso.

### Duda 3: ¿Qué partes de `/proc` esconde Docker por defecto?

**Parcialmente resuelta.** Docker restringe `/proc/kcore`, `/proc/sys`,
`/proc/irq`, `/proc/bus`, `/proc/asound`, `/proc/scsi`, `/proc/sysrq-trigger`.
Pendiente: verificar la lista completa consultando la doc oficial de Docker.

---

## Pendientes

- Confirmar experimentalmente el PID namespace: ver el mismo proceso con
  dos PIDs simultáneos (adentro y afuera del contenedor).