"""Custom exception hierarchy for the Asterisk CLI application."""


class AsteriskCliError(Exception):
    """Base exception for all Asterisk CLI errors."""


class AsteriskServiceError(AsteriskCliError):
    """Raised when an Asterisk service or provisioning operation fails."""


class FileTransactionError(AsteriskCliError):
    """Raised when a file transaction fails and rollback is triggered."""


class DeviceCommunicationError(AsteriskCliError):
    """Raised when SSH or network communication with a phone fails."""
