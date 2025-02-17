import dataclasses

from opm.core.package import Component


@dataclasses.dataclass
class Gizmo(Component):
    target: str = 'gizmos'


@dataclasses.dataclass
class Script(Component):
    target: str = 'scripts'


@dataclasses.dataclass
class Template(Component):
    target: str = 'templates'


@dataclasses.dataclass
class Toolset(Component):
    target: str = 'toolsets'


@dataclasses.dataclass
class Init(Component):
    target: str = 'init'


@dataclasses.dataclass
class Menu(Component):
    target: str = 'menu'
