"""Pydantic response models for API endpoints.

This module defines data serialization schemas returned by the API routes.
"""

from pydantic import BaseModel, Field


class ConfigMatchResponse(BaseModel):
    """Pydantic model representing a configuration match.

    This is used to serialize the ConfigMatch dataclass into a JSON-friendly
    format for the API response.
    """

    file_path: str = Field(
        ...,
        description="The path to the file where the match was found.",
    )
    line_number: int = Field(
        ...,
        description="The line number in the file where the match occurred.",
    )
    matched_text: str = Field(
        ..., description="The specific text that matched the search criteria."
    )
