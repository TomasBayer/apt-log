import argparse
import itertools
import logging

from texttable import Texttable

from apt_log.log import AptLog

def build_argparser():
    main_parser = argparse.ArgumentParser()
    main_parser.add_argument('--verbose', '-v', action='store_true', help="verbose mode")

    main_subparsers = main_parser.add_subparsers(title='available actions', metavar='ACTION', dest='action')
    main_subparsers.required = True

    find_parser = main_subparsers.add_parser('find', help='find log entries for a package')
    find_parser.add_argument('--regex', '-r', action='store_true', help='consider PACKAGE to be a regular expression')
    find_parser.add_argument('package', metavar='PACKAGE', type=str, help="package")

    list_parser = main_subparsers.add_parser('list', help='list log entries')
    list_parser.add_argument('--min-date', '-m', type=str, help="shows only entries that are younger than the given date")
    list_parser.add_argument('--max-date', '-M', type=str, help="shows only entries that are older than the given date")

    show_parser = main_subparsers.add_parser('show', help='inspect a single log entry')
    show_parser.add_argument('id', metavar='ID', type=int, help="id")

    return main_parser


def run():
    # Parse arguments
    parser = build_argparser()
    args = parser.parse_args()

    # Configure logging
    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format='[%(name)s] %(levelname)-8s %(message)s' if args.verbose else '%(message)s',
    )

    log = AptLog()

    def draw_table(entries, action_map=lambda entry: entry.actions, abbreviate=True, include_versions=False):
        table = Texttable(0)
        table.set_deco(Texttable.VLINES | Texttable.HEADER)
        table.header(["ID", "Date", "Action", "Packages"])
        for entry in entries:
            core_data = [entry.id, entry.start_date.strftime('%Y-%m-%d %H:%M')]
            actions = action_map(entry)
            if actions:
                for (core, (action, packages)) in zip(
                        itertools.chain((core_data,), itertools.repeat([''] * len(core_data))), actions.items()):
                    if abbreviate and (len(packages) > 5 or action == 'Auto-Install'):
                        packages_string = "{} packages".format(len(packages))
                    else:
                        packages_string = ', '.join(
                            "{} ({})".format(p.name, p.version) if include_versions else p.name for p in packages)
                    table.add_row(core + [action, packages_string])
            elif entry.error:
                table.add_row(core + ["ERROR", entry.error])
            else:
                table.add_row(core + ["UNKNOWN", ""])
        print(table.draw())

    if args.action == 'find':
        action_map = {}
        entries = []
        for entry, actions in log.find_package_actions(args.package, regex=args.regex):
            action_map[entry] = actions
            entries.append(entry)
        draw_table(entries, action_map.get, abbreviate=False, include_versions=True)

    elif args.action == 'list':
        draw_table(log.get_entries(args.min_date, args.max_date))

    elif args.action == 'show':
        entry = log[args.id]

        table = Texttable(0)
        table.set_deco(0)
        if entry.start_date is not None:
            table.add_row(['Start-Date:', entry.start_date.strftime('%Y-%m-%d %H:%M:%S'), ''])
        if entry.end_date is not None:
            table.add_row(['End-Date:', entry.end_date.strftime('%Y-%m-%d %H:%M:%S'), ''])
        table.add_row(['Duration:', entry.duration, ''])
        if entry.requested_by:
            table.add_row(['Requested-By:', entry.requested_by, ''])
        if entry.error:
            table.add_row(['Error:', entry.error, ''])
        for action, packages in entry.actions.items():
            for key, package in zip(itertools.chain(("{}:".format(action),), itertools.repeat('')), packages):
                table.add_row([key, package.name, package.version])
        print(table.draw())