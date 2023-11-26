from datetime import datetime
from itertools import takewhile
from typing import Annotated, Optional

import humanize
import typer
from click import ClickException
from rich import box
from rich.console import Console
from rich.table import Table

from apt_log.log import ChangedPackage, InvalidAptLogEntryIDError
from apt_log.reader import build_system_apt_log

app = typer.Typer()
console = Console()


@app.command("list", help="List APT log entries.")
def list_entries(
        *,
        start_date: Annotated[Optional[datetime], typer.Option(
            "--start-date", "-s",
            help="Show only entries younger than the given date.",
        )] = None,
        end_date: Annotated[Optional[datetime], typer.Option(
            "--end-date", "-e",
            help="Show only entries older than the given date.",
        )] = None,
        show_versions: Annotated[bool, typer.Option(
            "--show-versions", "-v",
            help="Show versions of packages.",
        )] = False,
        show_commands: Annotated[bool, typer.Option(
            "--show-commands", "-c",
            help="Show commands that triggered the transactions.",
        )] = False,
        package_name: Annotated[Optional[str], typer.Option(
            "--package", "-p",
            metavar='PACKAGE_NAME',
            help="Filter entries by the name of the package (supports glob-style pattern matching).",
        )] = None,
):
    entries = build_system_apt_log().get_entries(
        start_date=start_date,
        end_date=end_date,
        package_name=package_name,
    )

    table = Table(header_style='bold magenta', box=box.SIMPLE_HEAD)
    table.add_column("ID", style='cyan')
    table.add_column("DATE", style='green')

    if show_commands:
        table.add_column("COMMAND", style='yellow')

    table.add_column("ACTION", style='blue')
    table.add_column("PACKAGES", style='yellow')

    def _join_strings(strings: list[str], *, use_and: bool = True) -> str:
        if use_and and len(strings) > 1:
            return f"{_join_strings(strings[:-1], use_and=False)} [dim]and[/dim] {strings[-1]}"
        else:
            return "[dim],[/dim] ".join(strings)

    def _build_packages_string(
            packages: list[ChangedPackage] | None = None,
            other_package_count: int = 0,
            dependency_count: int = 0,
    ) -> str:
        strings = []

        if packages:
            if show_versions:
                strings.extend(f"{package.name} [dim]({package.version})[/dim]" for package in packages)
            else:
                strings.extend(package.name for package in packages)
        if other_package_count > 0:
            strings.append(f"[dim]{other_package_count} other packages[/dim]")
        if dependency_count > 0:
            strings.append(f"[dim]{dependency_count} dependencies[/dim]")

        return _join_strings(strings, use_and=other_package_count + dependency_count > 0)

    for entry in entries:
        base_columns = [str(entry.id), entry.start_date.strftime('%Y-%m-%d %H:%M')]

        if show_commands:
            base_columns.append(entry.command_line)

        if entry.has_changed_packages():
            for n, (action, packages) in enumerate(entry.changed_packages_by_action.items()):
                # Packages that are marked as 'automatic' are considered dependencies. They should not be displayed.

                # Count dependencies (Since packages is sorted, dependencies come last.)
                dependencies_count = sum(
                    1 for _ in
                    takewhile(lambda package: package.is_automatic, reversed(packages))
                ) if package_name is None else 0
                non_dependencies_count = len(packages) - dependencies_count

                if non_dependencies_count > 3:
                    packages_string = _build_packages_string(
                        packages[:2],
                        other_package_count=non_dependencies_count - 2,
                        dependency_count=dependencies_count,
                    )
                else:
                    packages_string = _build_packages_string(
                        packages[:non_dependencies_count],
                        dependency_count=dependencies_count,
                    )

                table.add_row(
                    *(base_columns if n == 0 else [""] * len(base_columns)),
                    action,
                    packages_string,
                )

        elif entry.error:
            table.add_row(*base_columns, "ERROR", entry.error)

        else:
            table.add_row(*base_columns, "UNKNOWN", "")

    console.print(table)


@app.command("show", help="Inspect a single log entry.")
def show_entry(
        entry_id: int = typer.Argument(
            metavar="ENTRY_ID", help="The ID of the log entry.",
        ),
):
    try:
        entry = build_system_apt_log().get_entry_by_id(entry_id)
    except InvalidAptLogEntryIDError as err:
        raise ClickException(str(err)) from err

    table = Table(show_header=False, box=None)
    table.add_column(style='bold magenta')
    table.add_column(style='blue')

    if entry.start_date is not None:
        table.add_row("DATE", entry.start_date.strftime('%Y-%m-%d %H:%M:%S'))

    if entry.command_line is not None:
        table.add_row("COMMAND", f"[yellow]{entry.command_line}")

    if entry.duration is not None:
        table.add_row("DURATION", humanize.naturaldelta(entry.duration))

    if entry.requested_by:
        table.add_row("USER", entry.requested_by)

    if entry.error:
        table.add_row("ERROR MESSAGE", entry.error)

    console.print(table)

    if entry.has_changed_packages():
        table = Table(header_style='bold magenta', box=box.SIMPLE_HEAD)
        table.add_column("ACTION", style='blue')
        table.add_column("PACKAGES", style='yellow')
        table.add_column("VERSION", style='cyan')

        if entry.has_version_changes():
            table.add_column("PREVIOUS VERSION", style='cyan dim')

        for action, packages in entry.changed_packages_by_action.items():
            for n, package in enumerate(packages):
                row = [
                    str(action) if n == 0 else "",
                    f"{package.name} [dim](automatic)[/dim]" if package.is_automatic else package.name,
                    package.version,
                ]

                if entry.has_version_changes():
                    row.append(package.previous_version)

                table.add_row(*row)

            table.add_section()

        console.print(table)
