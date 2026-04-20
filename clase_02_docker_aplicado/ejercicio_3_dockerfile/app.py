import cowsay
import sys

mensaje = ' '.join(sys.argv[1:]) if len(sys.argv) > 1 else "Hola Mati!"
cowsay.cow(mensaje)

