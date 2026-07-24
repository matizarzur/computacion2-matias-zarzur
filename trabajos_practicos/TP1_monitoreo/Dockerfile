# Imagen base: Python 3.11 sobre Debian slim.
# - slim: minimalista (~150 MB), sin paquetes innecesarios.
# - Debian: misma familia que Ubuntu, /proc idéntico al del host.
# - Descartamos Alpine (musl libc puede dar sorpresas con capabilities).
FROM python:3.11-slim

# Metadata del mantenedor (opcional pero prolijo).
LABEL maintainer="Matias Zarzur <matiaszarzur@um.edu.ar>"
LABEL description="Monitor de procesos - TP1 Computacion II 2026"

# Instalamos utilidades mínimas del sistema que nos van a servir para debuggear
# adentro del contenedor: procps (ps, top), htop (para comparar con nuestro
# monitor), strace (por si necesitamos ver syscalls).
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
        procps \
        htop \
        strace && \
    rm -rf /var/lib/apt/lists/*

# Directorio de trabajo adentro del contenedor.
WORKDIR /app

# Copiamos primero requirements.txt y instalamos deps. Este orden es
# a proposito: si solo cambia el codigo (no las dependencias), Docker
# reusa la cache de esta capa y no reinstala todo cada vez.
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Ahora si, copiamos el resto del proyecto.
COPY . .

# Comando por defecto durante desarrollo: bash interactivo.
# Al final del proyecto cambiar a: CMD ["python", "src/main.py"]
CMD ["bash"]