from cyberdrop_dl.cli import app


def show() -> None:
    """Show a list of all supported sites"""
    from cyberdrop_dl import supported_sites

    table = supported_sites.as_rich_table()
    app.console.print(table)
