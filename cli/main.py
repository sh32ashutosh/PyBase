import click

@click.group()
def cli():
    """PyBase CLI"""
    pass

@cli.command()
def hw():
    """Prints the hardware profile."""
    from core.hw_adapter import get_hardware_profile
    import pprint
    pprint.pprint(get_hardware_profile())

@cli.command()
def config():
    """Prints the adaptive runtime config."""
    from core.runtime_config import get_runtime_config
    import pprint
    pprint.pprint(get_runtime_config())

if __name__ == "__main__":
    cli()
