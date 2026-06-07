import uuid


def _new_id(prefix: str) -> str:
    return f"{prefix}_{uuid.uuid4().hex[:24]}"


def new_interaction_id() -> str:
    return _new_id("int")


def new_session_id() -> str:
    return _new_id("session")


def new_user_id() -> str:
    return _new_id("usr")


def new_memory_id() -> str:
    return _new_id("mem")


DEV_USER_ID = "dev_user"
