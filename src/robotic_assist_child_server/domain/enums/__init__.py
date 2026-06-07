from enum import Enum


class Role(str, Enum):
    ADMIN = "admin"
    PARENT = "parent"
    CHILD = "child"
    DEVICE = "device"


class ClientType(str, Enum):
    MOBILE = "mobile"
    RPI = "rpi"
    UNKNOWN = "unknown"


class MemoryType(str, Enum):
    PREFERENCE = "preference"
    ROUTINE = "routine"
    RESTRICTION = "restriction"
    INTEREST = "interest"
    INTERACTION_SUMMARY = "interaction_summary"
    SAFETY_NOTE = "safety_note"
    PARENT_INSTRUCTION = "parent_instruction"
