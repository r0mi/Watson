from .utils import create_watson, parse_tags


def _bypass_click_bug_to_ensure_watson(ctx):
    # When pallets/click#942 is fixed, this won't be needed...
    if ctx.obj is None:
        ctx.obj = create_watson()
    return ctx.obj


def _prior_tokens(ctx, param):
    """Return the tokens already parsed for ``param`` as a list of strings.

    Click 8 invokes shell_complete callbacks with ``(ctx, param, incomplete)``
    where ``param`` is a :class:`click.Parameter`; earlier Click (and the test
    suite here) passes the tokens directly as a list.  Accept both so the rest
    of this module can keep operating on a plain list of strings.
    """
    if isinstance(param, (list, tuple)):
        return [str(v) for v in param]

    name = getattr(param, "name", None)
    if name is None:
        return []

    value = ctx.params.get(name)
    if value is None:
        return []
    if isinstance(value, (list, tuple)):
        return [str(v) for v in value]
    return [str(value)]


def get_project_or_task_completion(ctx, param, incomplete):
    """Function to autocomplete either organisations or tasks, depending on the
       shape of the current argument."""

    assert isinstance(incomplete, str)

    args = _prior_tokens(ctx, param)

    def get_incomplete_tag(args, incomplete):
        """Get incomplete tag from command line string."""
        cmd_line = " ".join(args + [incomplete])
        found_tags = parse_tags(cmd_line)
        return found_tags[-1] if found_tags else ""

    def fix_broken_tag_parsing(incomplete_tag):
        """
        Remove spaces from parsed tag

        The function `parse_tags` inserts a space after each character. In
        order to obtain the actual command line part, the space needs to be
        removed.
        """
        return "".join(char for char in incomplete_tag.split(" "))

    _bypass_click_bug_to_ensure_watson(ctx)

    project_is_completed = any(
        tok.startswith("+") for tok in args + [incomplete]
    )
    if project_is_completed:
        incomplete_tag = get_incomplete_tag(args, incomplete)
        fixed_incomplete_tag = fix_broken_tag_parsing(incomplete_tag)
        tag_suggestions = get_tags(ctx, param, fixed_incomplete_tag)
        return ["+{}".format(tag) for tag in tag_suggestions]
    else:
        return get_projects(ctx, param, incomplete)


def get_projects(ctx, param, incomplete):
    """Function to return all projects matching the prefix."""
    watson = _bypass_click_bug_to_ensure_watson(ctx)
    return [p for p in watson.projects if p.startswith(incomplete)]


def get_rename_name(ctx, param, incomplete):
    """
    Function to return all projects or tasks matching the prefix

    Depending on the specified rename_type, either a list of projects or a list
    of tasks must be returned. This function takes care of this distinction and
    returns the appropriate names.

    If the passed in type is unknown, e.g. due to a typo, an empty completion
    is generated.
    """

    in_type = ctx.params["rename_type"]
    if in_type == "project":
        return get_projects(ctx, param, incomplete)
    elif in_type == "tag":
        return get_tags(ctx, param, incomplete)

    return []


def get_rename_types(ctx, param, incomplete):
    """Function to return all rename types matching the prefix."""
    return [t for t in ("project", "tag") if t.startswith(incomplete)]


def get_tags(ctx, param, incomplete):
    """Function to return all tags matching the prefix."""
    watson = _bypass_click_bug_to_ensure_watson(ctx)
    return [t for t in watson.tags if t.startswith(incomplete)]


def get_frames(ctx, param, incomplete):
    """
    Return all matching frame IDs

    This function returns all frame IDs that match the given prefix in a
    generator. If no ID matches the prefix, it returns the empty generator.
    """
    watson = _bypass_click_bug_to_ensure_watson(ctx)
    return [f.id for f in watson.frames if f.id.startswith(incomplete)]
