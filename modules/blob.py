# modules/blob.py -support for blob objects including files and other classes

import copy
from typing import Any


class Blob:
    def __init__(self, obj: Any):
        self._object = obj

    def get(self) -> Any:
        return self._object

    def get_safe(self) -> Any:
        return copy.deepcopy(self._object)

    def type(self) -> str:
        return type(self._object).__name__

    def is_instance(self, cls: type) -> bool:
        return isinstance(self._object, cls)

    def to_dict(self) -> dict:
        if hasattr(self._object, "__dict__"):
            return vars(self._object)
        elif isinstance(self._object, dict):
            return copy.deepcopy(self._object)
        raise TypeError("Object cannot be converted to dict")

    def to_str(self) -> str:
        return str(self._object)

    def is_callable(self) -> bool:
        return callable(self._object)

    def is_mutable(self) -> bool:
        mutable_types = (dict, list, set, bytearray)
        return isinstance(self._object, mutable_types)

    def is_none(self) -> bool:
        return self._object is None

    def clear(self) -> None:
        self._object = None

    def replace(self, new_object: Any) -> None:
        self._object = new_object

    def clone(self) -> "Blob":
        return Blob(copy.deepcopy(self._object))

    def __repr__(self) -> str:
        return f"<Blob type={self.type()}>"

