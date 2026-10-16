"""Pruebas unitarias del protocolo y del formato."""
import unittest
from protocolo import validar_alias, validar_mensaje
from formato import FormateadorMensajes


class PruebasChat(unittest.TestCase):
    def setUp(self):
        self.formateador = FormateadorMensajes()

    def test_alias_valido(self):
        self.assertTrue(validar_alias("Ismael"))

    def test_alias_vacio(self):
        self.assertFalse(validar_alias(""))

    def test_mensaje_valido(self):
        self.assertTrue(validar_mensaje("Hola a todos"))

    def test_mensaje_vacio(self):
        self.assertFalse(validar_mensaje(""))

    def test_formato(self):
        self.assertEqual(self.formateador.formatear_mensaje("Ismael", "Hola"), "[Ismael]: Hola")


if __name__ == "__main__":
    unittest.main()
