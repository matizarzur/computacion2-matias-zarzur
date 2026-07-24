# Dudas TP1

Registro de dudas que fueron surgiendo durante el desarrollo del TP,
con su resolución cuando la hubo.

---

### Duda: ¿Por qué el mismo proceso tiene distinto PID adentro y afuera del contenedor?

**Resuelta.** Cada PID namespace tiene su propia numeración. Docker por defecto
crea un namespace nuevo, por eso el PID 1 adentro del contenedor es un PID
distinto (ej: 10704) visto desde el host. Con `pid: host` en docker-compose
se comparte el namespace del host y los PIDs coinciden.

### Duda: ¿Cuál es la diferencia entre `Pid` y `Tgid` en `/proc/<pid>/status`?

**Resuelta.** `Tgid` es el PID del proceso principal (del thread group),
`Pid` es el ID del thread individual. Coinciden cuando el proceso es
single-threaded. Los threads en Linux son LWPs (procesos livianos): cada uno
tiene su propio PID pero comparten Tgid con los demás threads del mismo proceso.

### Duda: ¿Qué partes de `/proc` esconde Docker por defecto?

**Parcialmente resuelta.** Docker restringe `/proc/kcore`, `/proc/sys`,
`/proc/irq`, `/proc/bus`, `/proc/asound`, `/proc/scsi`, `/proc/sysrq-trigger`.
Pendiente: verificar la lista completa consultando la doc oficial de Docker.

### Duda:¿El PID del porceso esta incluido en su lista de theads?
**Resuelta.** Sí. En Linux todo proceso es en realidad un thread: el proceso
principal es simplemente el primer thread, y su TID coincide con el PID del
proceso.

### Duda: ¿Por que no puedo leer /proc/<pid>/maps con SYS_PTRACE?

**Resuelta.** En Linux hay TRES capas de seguridad apiladas para acceder a
info sensible de procesos ajenos:
1. DAC (permisos Unix tradicionales)
2. Capabilities (SYS_PTRACE)
3. LSMs (Yama y AppArmor)

Aunque tengas SYS_PTRACE y bajes,
Docker aplica por default el perfil AppArmor `docker-default` que bloquea el
acceso a /proc/<pid>/maps y /proc/<pid>/fd/* de procesos ajenos. Se resuelve
agregando `security_opt: apparmor:unconfined` al docker-compose.yml.

Aparte, algunas apps (Firefox, Chrome, apps de Snap) tienen sandboxes propios
ademas de AppArmor, pero con apparmor:unconfined en el contenedor eso deja
de ser un problema para las lecturas.
---

## Pendientes

- Confirmar experimentalmente el PID namespace: ver el mismo proceso con
  dos PIDs simultáneos (adentro y afuera del contenedor).