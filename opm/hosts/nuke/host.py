import logging
import os
import sys

import nuke

from opm.core.host import Host

logger = logging.getLogger(__name__)


class NukeHost(Host):
    name = 'nuke'
    version = nuke.NUKE_VERSION_MAJOR

    @property
    def sys_python(self) -> str:
        bin_dir = os.path.dirname(sys.executable)
        return os.path.join(bin_dir, 'python')

    def install(self) -> None:
        super().install()

        for extra_dir in ('gizmos', 'toolsets', 'plugins'):
            path = os.path.join(self.data_dir, extra_dir)
            if not os.path.exists(path):
                os.makedirs(path)
