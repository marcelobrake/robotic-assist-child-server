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


def new_image_id() -> str:
    return _new_id("img")


def new_audio_id() -> str:
    return _new_id("aud")


DEV_USER_ID = "dev_user"
