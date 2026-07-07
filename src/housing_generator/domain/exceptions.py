"""Excepciones propias del dominio. Nunca se deben lanzar excepciones
genericas (ValueError, Exception) desde la capa de dominio o aplicacion;
usar siempre estas clases o subclases especificas de infraestructura."""


class HousingGeneratorError(Exception):
    """Excepcion base de todo el sistema."""


class InvalidProgramError(HousingGeneratorError):
    """El programa (lista de estancias + requisitos) es inconsistente."""


class LayoutGenerationError(HousingGeneratorError):
    """No se pudo generar un layout valido para un programa/solar dados."""


class ConstraintViolationError(HousingGeneratorError):
    """Un layout generado viola una restriccion dura."""
