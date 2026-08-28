"""API router for MAC address search operations.

Provides REST API endpoints for querying MAC address assignments across
Asterisk configuration files and IP phone provisioning XML configurations.
"""

from fastapi import APIRouter, HTTPException, Path

from asterisk_phone_management.api.responses import ConfigMatchResponse
from asterisk_phone_management.core.validators import validate_mac_addr
from asterisk_phone_management.schemas.models import ConfigMatch
from asterisk_phone_management.services.search import search_for_mac_address

router = APIRouter()


@router.get(
    "/api/v1/mac_address/{mac_address}/search",
    response_model=list[ConfigMatchResponse],
    summary="Search for a MAC address",
    description="Search Asterisk config & XML files for a MAC address",
)
def search_mac_address(
    mac_address: str = Path(
        ..., description="The MAC address to search for (e.g., AABBCCDDEEFF)."
    ),
) -> list[ConfigMatchResponse]:
    """Search for a given MAC address within the Asterisk configuration files.

    Args:
        mac_address: Target MAC address to search for,
            provided as path parameter.

    Returns:
        List of Pydantic models containing the search results.

    Raises:
        HTTPException: Raised with 400 status code if validation fails.
        HTTPException: Raised with 404 status code if no matches are found.
    """
    validation_result = validate_mac_addr(mac_address)

    if validation_result is not True:
        raise HTTPException(status_code=400, detail=str(validation_result))

    matches: list[ConfigMatch] = search_for_mac_address(mac_address)

    if not matches:
        raise HTTPException(
            status_code=404,
            detail=f"No references to MAC address {mac_address} were found.",
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
