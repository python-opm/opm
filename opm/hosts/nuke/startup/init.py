import logging


def init_opm() -> None:
    try:
        from opm.hosts.nuke.host import NukeHost

        host = NukeHost()
        host.install()
    except Exception as e:
        logging.exception(e)


if __name__ == '__main__':
    init_opm()
