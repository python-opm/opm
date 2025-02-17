import dataclasses
from collections.abc import Sequence


class Package: ...


@dataclasses.dataclass
class Component:
    name: str
    dependencies: Sequence = ()
    target: str = ''


class Pip(Component): ...
