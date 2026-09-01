def to_nicegui_validation(result: bool | str) -> str | None:  # ruff: ignore[boolean-type-hint-positional-argument]
    """Convert a validator response into format required by NiceGUI inputs.

    Args:
        result: True if validation succeeds, or error message if invalid.

    Returns:
        None if validation succeeds, or the error string if validation fails.
    """
    return None if result is True else str(result)
