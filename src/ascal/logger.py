import logging

# ── Root ASCAL logger ──────────────────────────────────────────────────────────
def get_logger(name: str) -> logging.Logger:
    """
    Get a named logger under the 'ascal' hierarchy.

    Usage in any module:
        from ascal.logger import get_logger
        logger = get_logger(__name__)

    Args:
        name: typically __name__ of the calling module

    Returns:
        A logger named 'ascal.<module_name>'
    """
    return logging.getLogger(name)