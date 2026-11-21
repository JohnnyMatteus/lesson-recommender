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
