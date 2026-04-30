from cyberdrop_dl.supported_sites import as_markdown, as_rich_table


def test_rich_table() -> None:
    table = as_rich_table()
    assert len(table.rows) >= 166


def test_markdown_table() -> None:
    as_markdown()
