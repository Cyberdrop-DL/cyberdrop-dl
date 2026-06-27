# Contributing

> [!NOTE]
> The words **MAY**, **SHOULD**/**SHOULD NOT** and **MUST**/**MUST NOT** in this document have the same meaning as defined in RFC 2129 <https://www.rfc-editor.org/info/rfc2119>

## Reporting issues

You **SHOULD** search for existing issues before creating a new one. If a bug already has an issue open, you can comment on the existing issue
with extra information that might help reproduce or fix the problem. Duplicate issues will be closed with a
reference to the existing issue.

You **SHOULD** [read the wiki](https://script-ware.gitbook.io/cyberdrop-dl/frequently-asked-questions) as it
includes solutions to some common problems.

If your issue hasn't been reported yet, open a new issue at <https://github.com/Cyberdrop-DL/cyberdrop-dl/issues/new/choose>.

## Feature requests

You can request a new feature by [opening an issue](#submitting-an-issue). If you would like to implement a new feature,
you **SHOULD** open an issue/discussion with a proposal first and at least one use case. You **SHOULD NOT** submit a PR directly unless your feature is small
and has a narrow scope.

## Setting up the development environment

`cyberdrop-dl` uses `uv` as a project management tool and requires python 3.12+. You can install it from <https://docs.astral.sh/uv/getting-started/installation/>.

You don't need to install python as `uv` will automatically install a compatible python version if required.

Once you have `uv` installed, follow these steps:

1. Clone the repo

   ```powershell
   git clone "https://github.com/Cyberdrop-DL/cyberdrop-dl"
   cd cyberdrop-dl
   ```

1. Install the project and its dependencies

   ```powershell
   uv sync --all-extras
   ```

1. Install the pre-commit hooks:

   ```powershell
   uv run prek install
   ```

1. Optionally, run the tests suite to make sure your dev environment is setup correctly

   ```powershell
   uv run pytest
   ```

## Code style

### Standards

#### Formatting

This project uses [ruff](https://docs.astral.sh/ruff) for formatting, linting and import sorting.
We recommend [setting up your IDE](https://docs.astral.sh/ruff/editors/) to format and check with `ruff`, but

#### Type checking

Not enforced but highly recommended. The project includes hardcoded config options for [`basedpyright`](https://docs.basedpyright.com/latest)

#### Line width

120 characters max

The project includes predefined [settings for the zed editor](https://github.com/Cyberdrop-DL/cyberdrop-dl/tree/main/.zed)
with formatting options and a recipe to quickly launch `cyberdrop-dl` with `pdb` (the Python debugger) for testing

### Code formatting with pre-commit hooks

This project uses pre-commit hooks to enforce consistent code style and identify common issues early on.

These hooks run automatically on every `git commit`. If a check fails, the commit is blocked and `ruff` will attempt to
automatically fix the files. You may need to fix some errors manually if `ruff` can not do it automatically.

Once everything is fixed, `git add` the changes and commit again.

> [!TIP]
> To trigger linting and formatting manually, run `uv run ruff check --fix` then `uv run ruff format`

## Implementing new changes

> [!IMPORTANT]
> `cyberdrop-dl` requires python 3.12+. You **MUST NOT** use syntax or features exclusive to newer versions without version guards

> [!IMPORTANT]  
> Before you start writing any code, you **SHOULD** search the [repository](https://github.com/Cyberdrop-DL/cyberdrop-dl/pulls)
> for an open or closed PR that relates to your submission to prevent duplicated effort

### Submitting a Pull Request (PR)

- Checkout a **new** branch before working on any changes, branching from `main`. You **MUST NOT** work directly on `main`
- Implement your changes. Make sure to follow [code style conventions](#code-style). You **SHOULD** add tests for
  any new non-crawler specific functionality you introduce
- Commit your changes using a descriptive commit message
- Fork the repository on GitHub, push your branch to the fork and open a pull request against the `main` branch of base repository
- Make sure your pull request has a descriptive title and a short description. Sometimes the title is enough and no description is required
- You **MUST NOT** use AI to generate your PR title/description. Write it with your own words
- Wait for a maintainer to review your PR and then address any comments they might have

If everything is okay, your changes will be merged into the project.

## Adding support for a new site

There's no standard template for a new crawler, but there are a few conventions. Some of these conventions are enforced by tests.

You **SHOULD** look at the code of another (hopefully similar) crawler
and base your crawler on that. A simple crawler to use as base is [CloudFlareStream](cyberdrop_dl/crawlers/cloudflare_stream.py).

- All crawlers **MUST** inherit from the [base crawler](cyberdrop_dl/crawlers/crawler.py)
- All crawlers **MUST** have the word `Crawler` at the end of their class name
- All crawlers **MUST** override the `fetch` method. It's the primary method that decides what to do with an URL that matches with that crawler
- You **MUST** not call any method that may fail (raise an exception other that `ValueError`) from within `fetch`
- All async method called from within fetch **MUST** be public methods
- All public method **MUST** be decorated with `error_handling_wrapper` to catch any unknown error
- You **SHOULD** catch **expected** errors and re-raise them as a `ScrapeError` with an appropiate code and message.
  A file being deleted is common expected error
- You **SHOULD** use valid HTTP codes for any `ScrapeError`. ex: raise `ScrapeError(410)` (GONE) for deleted files.
  See the [Mozilla Developer documention](https://developer.mozilla.org/en-US/docs/Web/HTTP/Reference/Status) for a list of HTTP codes
- You **MAY** use HTTP code `422` (Unprocessable entity) for **expected** errors if no other HTTP code feels adequate
- You **MAY** use a short string instead of an HTTP code to convey a better context for an error (if required).
  The string **SHOULD** be at most 20 characters long as it will be shown on the `Scrape Errors` sections of the TUI
- You **SHOULD NOT** write logic in a defensive way for **unexpected** errors. If you need to perform an operation that _could_ fail
  but that you do not **expect** to fail (ex: a dictionary key lookup on an API response) and you can not continue the scrape process
  if the operation fails, do not try to catch the exception. Let it bubble up. It will eventually be logged by the `error_handling_wrapper`
- You **SHOULD** model site specific data into dataclasses, if possible
- You **MUST** create a new task for any coroutine whose result is not needed to complete the current task
- You **MUST NOT** create `MediaItem` objects manually. You **MUST** use the `handle_file` method
- You **SHOULD** look at the methods on the base crawler for possible helper functions. Their doctrings explain expected use of each one
- You **MAY** add site specific CLI/config options at [cyberdrop_dl/config/crawlers.py](cyberdrop_dl/config/crawlers.py) to use within the crawler
- You **SHOULD NOT** add crawler specific CLI/options unless absolutely necessary
- You **SHOULD** add at least 1 test case for the crawler

## Creating tests for a new site

1. Create a file with the name `URLs.txt` at the root of the repo
1. Paste all the URLs you want to test inside the file
1. Run [scripts/tools/make_test_cases.py](scripts/tools/make_test_cases.py). If successful, it will generate a
   new file inside [tests/crawlers/test_cases](tests/crawlers/test_cases)
1. Check that the scraped data matches the expected result
1. Rename the generated test file, from `test_case_<domain>.py` to just `<domain>.py`
1. Run the test again manually to confirm it it is reproducible:

```powershell
uv run pytest -x --test-crawlers <domain>
```

## License

By contributing, you agree that your contributions will be licensed under the [GNU General Public License v3.0](LICENSE).
