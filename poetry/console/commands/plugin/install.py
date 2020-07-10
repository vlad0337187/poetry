import os

from typing import TYPE_CHECKING
from typing import Tuple

from cleo.helpers import argument

from ..init import InitCommand


if TYPE_CHECKING:
    from pathlib import Path

    from poetry.core.packages.package import Package
    from poetry.repositories.installed_repository import InstalledRepository
    from poetry.utils.env import Env


class PluginInstallCommand(InitCommand):

    name = "plugin install"

    description = "Install a new plugin."

    arguments = [
        argument("plugins", "The names of the plugins to install.", multiple=True)
    ]

    @property
    def home(self) -> "Path":
        from pathlib import Path

        return Path(os.environ.get("POETRY_HOME", "~/.poetry")).expanduser()

    @property
    def bin(self) -> "Path":
        return self.home / "bin"

    @property
    def lib(self) -> "Path":
        return self.home / "lib"

    @property
    def plugins(self) -> "Path":
        return self.home / "plugins"

    def handle(self) -> int:
        from pathlib import Path

        from appdirs import user_data_dir
        from cleo.io.null_io import NullIO

        from poetry.__version__ import __version__
        from poetry.core.semver import parse_constraint
        from poetry.factory import Factory
        from poetry.installation.executor import Executor
        from poetry.installation.installer import Installer
        from poetry.locations import DATA_DIR
        from poetry.packages.locker import Locker
        from poetry.packages.project_package import ProjectPackage
        from poetry.puzzle.provider import Provider
        from poetry.puzzle.solver import Solver
        from poetry.repositories.installed_repository import InstalledRepository
        from poetry.repositories.pool import Pool
        from poetry.repositories.pypi_repository import PyPiRepository
        from poetry.repositories.repository import Repository
        from poetry.utils.env import EnvManager

        plugins = self.argument("plugins")
        plugins = self._determine_requirements(plugins)

        # Plugins should be installed in the system env to be globally available
        system_env = EnvManager.get_system_env()
        installed_repository = InstalledRepository.load(
            system_env, with_dependencies=True
        )
        repository = Repository()

        root_package = None
        for package in installed_repository.packages:
            if package.name in Provider.UNSAFE_PACKAGES:
                continue

            if package.name == "poetry":
                root_package = ProjectPackage(package.name, package.version)
                for dependency in package.requires:
                    root_package.add_dependency(dependency)

                continue

            repository.add_package(package)

        plugin_names = []
        for plugin in plugins:
            plugin_name = plugin.pop("name")
            root_package.add_dependency(Factory.create_dependency(plugin_name, plugin))
            plugin_names.append(plugin_name)

        root_package.python_versions = ".".join(
            str(v) for v in system_env.version_info[:3]
        )

        pool = Pool()
        pool.add_repository(PyPiRepository())

        data_dir = Path(
            os.getenv("POETRY_HOME") if os.getenv("POETRY_HOME") else DATA_DIR
        )
        locker = Locker(data_dir.joinpath("poetry.lock"), {})
        if not locker.is_locked():
            locker.set_lock_data(root_package, repository.packages)

        installer = Installer(
            self._io,
            system_env,
            root_package,
            locker,
            pool,
            self.poetry.config,
            repository,
        )
        installer.dry_run()
        installer.whitelist(plugin_names)
        installer.update(True)
        installer.remove_untracked(False)

        return installer.run()
