from housing_generator.application.dto.generation_request import GenerationRequest
from housing_generator.application.ports.zoning_strategy_port import ZoningStrategyPort
from housing_generator.application.ports.layout_generator_port import LayoutGeneratorPort
from housing_generator.application.ports.constraint_validator_port import ConstraintValidatorPort
from housing_generator.domain.entities.layout import Layout
from housing_generator.domain.exceptions import LayoutGenerationError


class GenerateLayoutUseCase:
    """Orquesta zonificacion -> colocacion -> validacion para producir un
    Layout valido.

    Las dependencias se inyectan como puertos (interfaces), asi que el
    algoritmo concreto (zonificacion por treemap, generador por grafos,
    genetico...) puede cambiarse sin tocar este caso de uso (principio
    de inversion de dependencias). `constraint_validator` puede ser un
    unico validador o un CompositeConstraintValidator que agrupe varios.
    """

    def __init__(
        self,
        zoning_strategy: ZoningStrategyPort,
        layout_generator: LayoutGeneratorPort,
        constraint_validator: ConstraintValidatorPort,
    ):
        self._zoning_strategy = zoning_strategy
        self._layout_generator = layout_generator
        self._constraint_validator = constraint_validator

    def execute(self, request: GenerationRequest) -> Layout:
        zones = self._zoning_strategy.build_zones(request.program)

        last_result = None
        for _ in range(max(1, request.max_attempts)):
            layout = self._layout_generator.generate(request.program, request.lot, zones)
            result = self._constraint_validator.validate(layout)
            if result.is_valid:
                layout.metadata["violations"] = 0
                layout.metadata["warnings"] = len(result.warnings)
                return layout
            last_result = result

        last_violations = last_result.violations if last_result else []
        raise LayoutGenerationError(
            f"No se pudo generar un layout valido tras {request.max_attempts} intento(s). "
            f"Ultimas violaciones: {last_violations}"
        )
