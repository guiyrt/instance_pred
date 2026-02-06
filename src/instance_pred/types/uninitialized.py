class UninitializedToken:
    """Singleton marker for state before first data arrival."""
    __slots__ = ()

    def __repr__(self) -> str:
        return "<UninitializedToken>"

    def __bool__(self) -> bool:
        return False

_UNINITIALIZED: UninitializedToken = UninitializedToken()