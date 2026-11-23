"""Errors raised by the data-collection layer."""


class DataError(Exception):
    """Base class for data-collection problems."""


class InvalidSymbolError(DataError, ValueError):
    """The input cannot be turned into a supported NSE/BSE/index ticker."""


class NoDataError(DataError):
    """The source answered, but returned no data (unknown or delisted symbol, empty statement)."""


class DataSourceError(DataError):
    """The source could not be reached or kept failing (network, rate limit, format change)."""
