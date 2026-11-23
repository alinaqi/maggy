"""Error raised when existing content cannot be edited safely."""


class RegionError(ValueError):
    """Existing content cannot be parsed safely; it must never be overwritten."""
