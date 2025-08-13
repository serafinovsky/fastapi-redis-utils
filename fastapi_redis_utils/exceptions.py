class RepositoryError(Exception):
    """Base exception for repository errors."""


class DeserializationError(RepositoryError):
    """Error deserializing data saved to Redis."""


class SerializationError(RepositoryError):
    """Error serializing model before saving to Redis."""


class NotFoundError(RepositoryError):
    """Entity not found in the repository."""


class ResultModelCreationError(RepositoryError):
    """Error building result model before saving."""


class TransientRepositoryError(RepositoryError):
    """Transient error that may succeed on retry."""


class AtomicUpdateError(TransientRepositoryError):
    """An atomic update failed (optimistic lock conflict)."""


__all__ = [
    "RepositoryError",
    "DeserializationError",
    "SerializationError",
    "NotFoundError",
    "ResultModelCreationError",
    "TransientRepositoryError",
    "AtomicUpdateError",
]
