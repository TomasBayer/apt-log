import itertools
from datetime import datetime
from typing import Annotated, Optional

import humanize
import typer
from click import ClickException
from rich import box
from rich.console import Console
from rich.table import Table

from apt_log.log import InvalidAptLogEntryIDError
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
    table.add_column("ACTION", style='blue')
    table.add_column("PACKAGES", style='yellow')

    for entry in entries:
        base_columns = [str(entry.id), entry.start_date.strftime('%Y-%m-%d %H:%M')]

        if entry.has_changed_packages():
            for base, (action, packages) in zip(
                    itertools.chain((base_columns,), itertools.repeat([""] * len(base_columns))),
                    entry.changed_packages_by_action.items(),
            ):
                if len(packages) > 5:
                    packages_string = f"{len(packages)} packages"
                else:
                    packages_string = ", ".join(
                        f"{p.name} ({p.version})" if show_versions else p.name for p in packages
                    )
                table.add_row(*base, action, packages_string)

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
                    package.name,
                    package.version,
                ]

                if entry.has_version_changes():
                    row.append(package.previous_version)

                table.add_row(*row)

            table.add_section()

        console.print(table)
