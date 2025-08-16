import click

from fhash._version import __version__
from fhash.cli.add import add
from fhash.cli.application import Application
from fhash.cli.check import check
from fhash.cli.generate import generate
from fhash.common import PROG_NAME, config_log


@click.group(
    context_settings={'help_option_names': ['-h', '--help']},
    invoke_without_command=True,
)
@click.version_option(version=__version__, prog_name=PROG_NAME)
@click.pass_context
def fhash(ctx: click.Context) -> None:
    config_log(PROG_NAME)
    app = Application()

    if not ctx.invoked_subcommand:
        app.echo(ctx.get_help())


fhash.add_command(add)
fhash.add_command(check)
fhash.add_command(generate)
