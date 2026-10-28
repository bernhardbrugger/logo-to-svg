"""Small shared helpers."""


class LogoError(Exception):
    """A problem the user can fix (bad input, missing font, ...). The CLI prints it without a traceback."""


def fmt(v):
    """Number with at most 2 decimals, no trailing zeros."""
    return ("%.2f" % v).rstrip("0").rstrip(".")
