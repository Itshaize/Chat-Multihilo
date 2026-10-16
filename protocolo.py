"""Parámetros compartidos entre cliente y servidor."""
IP_SERVIDOR = "0.0.0.0"
PUERTO = 5000
CODIFICACION = "utf-8"
COMANDO_SALIR = "/salir"
MAXIMO_ALIAS = 20
MAXIMO_MENSAJE = 1000

def validar_alias(alias):
    return (1 <= len(alias.strip()) <= MAXIMO_ALIAS
            and "\n" not in alias and "\r" not in alias)

def validar_mensaje(mensaje):
    return (1 <= len(mensaje.strip()) <= MAXIMO_MENSAJE
            and "\n" not in mensaje and "\r" not in mensaje)
