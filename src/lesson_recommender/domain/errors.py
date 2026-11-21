"""Erros explícitos do domínio, traduzidos para HTTP na borda da API."""


class RecommenderError(Exception):
    """Base de todos os erros do recomendador."""


class StudentNotFoundError(RecommenderError):
    def __init__(self, student_id: str) -> None:
        super().__init__(f"aluno não encontrado: {student_id}")
        self.student_id = student_id


class InvalidRequestError(RecommenderError):
    """Parâmetro fora do contrato (ex.: k <= 0)."""


class ConfigurationError(RecommenderError):
    """Configuração inválida ou dependência opcional ausente."""


class IntegrationError(RecommenderError):
    """Falha ao falar com o SaaS (rede, credencial ou resposta fora do contrato)."""


class AuthenticationError(RecommenderError):
    """Token ausente, inválido ou expirado."""


class ForbiddenError(RecommenderError):
    """Token válido, mas sem direito sobre o recurso pedido."""


class LessonNotFoundError(RecommenderError):
    def __init__(self, lesson_id: str) -> None:
        super().__init__(f"aula não encontrada: {lesson_id}")
        self.lesson_id = lesson_id


class BookingRejectedError(RecommenderError):
    """A reserva viola uma regra dura (lotação, nível ou contraindicação)."""

    def __init__(self, lesson_id: str, reason: str) -> None:
        super().__init__(f"reserva recusada para {lesson_id}: {reason}")
        self.lesson_id = lesson_id
        self.reason = reason
