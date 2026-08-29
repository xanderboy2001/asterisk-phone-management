"""API router for search operations.

Provides REST API endpoints for querying extension or MAC address
assignments across Asterisk configuration files and IP phone
provisioning XML configurations.
"""

from fastapi import APIRouter, HTTPException, Path

from asterisk_phone_management.api.responses import ConfigMatchResponse
from asterisk_phone_management.core.validators import (
    validate_extension,
    validate_mac_addr,
)
from asterisk_phone_management.schemas.models import ConfigMatch
from asterisk_phone_management.services.search import (
    search_for_caller_id,
    search_for_extension,
    search_for_mac_address,
)

router = APIRouter()


@router.get(
    "/extension/{extension}",
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


@router.get(
    "/mac_address/{mac_address}",
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


@router.get(
    "/caller_id/{caller_id}",
    response_model=list[ConfigMatchResponse],
    summary="Search for a caller ID",
    description="Search sip.conf for a given caller ID.",
)
def search_caller_id(
    caller_id: str = Path(
        ..., description="The caller ID to search for (e.g., John)."
    ),
) -> list[ConfigMatchResponse]:
    """Search for a given caller ID within sip.conf.

    Args:
        caller_id: Target caller ID to search for,
            provided as path parameter.

    Returns:
        List of Pydantic models containing the search results.

    Raises:
        HTTPException: Raised with 400 status code if validation fails.
        HTTPException: Raised with 404 status code if no matches are found.
    """
    matches: list[ConfigMatch] = search_for_caller_id(caller_id)

    if not matches:
        raise HTTPException(
            status_code=404,
            detail=f"No references to caller ID {caller_id} were found.",
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
