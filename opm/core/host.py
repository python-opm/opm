import logging
import os
import subprocess
import sys
from abc import ABC

import platformdirs

from opm.core.package import Package

appname = 'opm'

logger = logging.getLogger(__name__)


class Host(ABC):
    name: str
    version: str

    @property
    def data_dir(self) -> str:
        user_data_dir = platformdirs.user_data_dir(appname)
        host_name = f'{self.name}_{self.version}'
        return os.path.join(user_data_dir, host_name)

    @property
    def sys_python(self) -> str:
        return sys.executable

    @property
    def venv_path(self) -> str:
        return os.path.join(self.data_dir, 'venv')

    @property
    def venv_python(self) -> str:
        venv_bin_dir = 'Scripts' if sys.platform == 'win32' else 'bin'
        return os.path.join(self.venv_path, venv_bin_dir, 'python')

    def install(self) -> None:
        """Installs the host."""

        if not os.path.exists(self.venv_path):
            self.create_venv()
            self.upgrade_pip()

        dirnames = ('repos',)

        cache_path = os.path.join(self.data_dir, 'cache')
        if not os.path.exists(cache_path):
            os.makedirs(cache_path)

        cache_path = os.path.join(self.data_dir, 'manifests')
        if not os.path.exists(cache_path):
            os.makedirs(cache_path)

        logger.info(f'Installed Host {self.name!r}')

    def create_venv(self) -> None:
        cmd = (self.sys_python, '-m', 'venv', self.venv_path)
        subprocess.check_call(cmd)
        logger.info(f'Created virtual environment: {self.venv_path!r}')

    def upgrade_pip(self) -> None:
        cmd = (self.venv_python, '-m', 'pip', 'install', '--upgrade', 'pip')
        subprocess.check_call(cmd)
        logger.info(f'Upgraded pip: {self.venv_path!r}')

    def install_package(self, package: Package) -> None: ...
