import logging

from opm.manager import Manager
from tests import application


def main() -> None:
    logging.basicConfig(level=logging.DEBUG, force=True)
    with application():
        widget = Manager()
        widget.show()


if __name__ == '__main__':
    main()
