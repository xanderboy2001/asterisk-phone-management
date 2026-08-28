"""API router for extension search operations.

Provides REST API endpoints for querying extension assignments across Asterisk
configuration files and IP phone provisioning XML configurations.
"""

from fastapi import APIRouter, HTTPException, Path

from asterisk_phone_management.api.responses import ConfigMatchResponse
from asterisk_phone_management.core.validators import validate_extension
from asterisk_phone_management.schemas.models import ConfigMatch
from asterisk_phone_management.services.search import search_for_extension

router = APIRouter()


@router.get(
    "/api/v1/extensions/{extension}/search",
    response_model=list[ConfigMatchResponse],
    summary="Search for an extension",
    description="Search Asterisk config & XML files for a 4-digit extension",
)
def search_extension(
    extension: str = Path(
        ..., description="The 4-digit extension to search for (e.g., 1234)."
    ),
) -> list[ConfigMatchResponse]:
    """Search for a given extension within the Asterisk configuration files.

    Args:
        extension: Target extension to search for, provided as path parameter.

    Returns:
        List of Pydantic models containing the search results.

    Raises:
        HTTPException: Raised w/ 400 status code if extension validation fails.
        HTTPException: Raised with a 404 status code if no matches are found.
    """
    validation_result = validate_extension(extension)

    if validation_result is not True:
        raise HTTPException(status_code=400, detail=str(validation_result))

    matches: list[ConfigMatch] = search_for_extension(extension)

    if not matches:
        raise HTTPException(
            status_code=404,
            detail=f"No references to extension {extension} were found.",
        )

    response_data: list[ConfigMatchResponse] = [
        ConfigMatchResponse(
            file_path=str(match.file_path),
            line_number=match.line_number,
            matched_text=match.matched_text,
        )
        for match in matches
    ]

    return response_data
