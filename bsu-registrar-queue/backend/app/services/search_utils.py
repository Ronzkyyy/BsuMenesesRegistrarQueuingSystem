"""Helpers for building safe SQL LIKE/ILIKE patterns from user input."""

# Backslash is the escape character we pass to ILIKE (`escape="\\"`), so it must
# be escaped first, then the two LIKE wildcards.
_LIKE_SPECIALS = ("\\", "%", "_")

LIKE_ESCAPE = "\\"


def escape_like(term: str) -> str:
    """Escape LIKE wildcards in a user-supplied search term.

    SQLAlchemy already parameterizes the pattern value, so this is not about SQL
    injection - it stops a user from smuggling `%` / `_` wildcards into what is
    meant to be a literal substring match (e.g. searching "%" matching every
    row). Use with ``.ilike(f"%{escape_like(term)}%", escape=LIKE_ESCAPE)``.
    """
    for ch in _LIKE_SPECIALS:
        term = term.replace(ch, LIKE_ESCAPE + ch)
    return term
