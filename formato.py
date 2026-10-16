"""Presentación de mensajes; separada de la lógica de red."""

class FormateadorMensajes:
    def formatear_mensaje(self, alias, contenido):
        return f"[{alias}]: {contenido}"

    def formatear_conexion(self, alias):
        return f"*** {alias} se ha conectado ***"

    def formatear_desconexion(self, alias):
        return f"*** {alias} se ha desconectado ***"
