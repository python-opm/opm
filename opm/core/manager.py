import io
import os.path
import shutil
import zipfile

import requests
from opm.core.package import Package


def get_remote_packages() -> tuple[Package, ...]:
    packages = ()
    return packages


def get_repo(target: str) -> None:
    url = 'https://github.com/beatreichenbach/qt-logging/archive/refs/heads/main.zip'
    response = requests.get(url)

    if os.path.exists(target):
        shutil.rmtree(target)

    with zipfile.ZipFile(io.BytesIO(response.content)) as zip_ref:
        zip_ref.extractall(target)
