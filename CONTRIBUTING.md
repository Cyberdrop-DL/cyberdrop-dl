# Contributing

## Found an Issue?

If you find a bug in the source code or a mistake in the documentation, you can
[open an Issue](#submitting-an-issue) to the GitHub Repository or you can
[submit a Pull Request](#submitting-a-pull-request-pr) with a fix if you know how to code.

## Want a Feature?

You can _request_ a new feature by [opening an issue](#submitting-an-issue). If you would like to _implement_ a new feature,
please open an issue or a discussion with a proposal first. If your feature is _small_ and easy to implement,
you can craft it and directly [submit it as a Pull Request](#submitting-a-pull-request-pr).

## Submission Guidelines

### Submitting an Issue

Before opening an issue, search through existing issues/PRs to ensure you are not opening a duplicate.
You also must [read the wiki](https://script-ware.gitbook.io/cyberdrop-dl/frequently-asked-questions) to learn how to solve most common problems.

If your issue is a bug and hasn't been reported, open a new issue. Please do not report duplicate issues.

You can open a new issue at <https://github.com/Cyberdrop-DL/cyberdrop-dl/issues/new/choose>.

### Submitting a Pull Request (PR)

Before you submit your Pull Request (PR) consider the following guidelines:

- Search the [repository](https://github.com/Cyberdrop-DL/cyberdrop-dl/pulls) for an open or closed PR
  that relates to your submission. You don't want to duplicate effort.
- Clone the repo and make your changes on a \***\*new branch\*\*** in your fork. The base branch should be `main`
- Follow [code style conventions](#code-style)
- Commit your changes using a descriptive commit message
- Push your fork to GitHub
- In GitHub, create a pull request to the `main` branch of the repository.
- Add a description to your PR. If the PR is small (such as a typo fix), you can go brief. Sometime the title of the PR is enough.
  If it contains a lot of changes, it's better to write more details.
  If your changes are user-facing (e.g. a new feature in the UI, a change in behavior, or a bugfix)
  please include a short message to add to the changelog.
- Wait for a maintainer to review your PR and then address any comments they might have.

If everything is okay, your changes will be merged into the project.

## Setting up the development environment

1. Install `uv` for project management (<https://docs.astral.sh/uv/getting-started/installation/>).

2. Clone the repo

   ```sh
   git clone "https://github.com/Cyberdrop-DL/cyberdrop-dl"
   cd cyberdrop-dl
   ```

3. Setup the dev enviroment with `uv`. It will automatically install a compatible python version (if required)

   ```sh
   uv sync --all-extras
   ```

4. Install the pre-commit hooks:

   ```sh
   uv run prek install
   ```

## Code Style

### Standards

`Formatting`: This project uses [ruff](https://docs.astral.sh/ruff) for formatting, linting and import sorting.

`Type checking`: Not enforced but highly recommended. The project includes hardcoded config options for [`basedpyright`](https://docs.basedpyright.com/latest)

`Line width`: We use a line width of 120.

### Code formatting with pre-commit hooks

This project uses git pre-commit hooks to perform formatting and linting before a commit is created,
to ensure consistent style and catch some common issues early on.

Once installed, hooks will run when you commit. If the formatting isn't quite right or a linter catches something,
the commit will be rejected and `ruff` will try to fix the files. If `ruff` can not fix all the issues,
you will need to look at the output and fix them manually. When everything is fixed (either by `ruff` itself or manually)
all you need to do is `git add` those files again and retry your commit.

### Manual code formatting

We recommend [setting up your IDE](https://docs.astral.sh/ruff/editors/) to format and check with `ruff`, but you can always run
`uv run ruff check --fix` then `uv run ruff format` in the root directory before submitting a pull request.
If you're using VScode, you can set it to [auto format python files with ruff on save](#editor-settings) in your `settings.json`

The project includes predefined [settings for the zed editor](https://github.com/Cyberdrop-DL/cyberdrop-dl/tree/main/.zed), with a recipe to quickly launch CDL in debug mode for testing

## Editor settings

If you use VScode and have `ruff` installed as a formatter, you might find the following `settings.json` useful:

```json
{
  "[python]": {
    "editor.formatOnSave": true,
    "editor.defaultFormatter": "charliermarsh.ruff"
  }
}
```
