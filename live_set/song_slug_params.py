"""TouchDesigner helpers for assigning live-set Songslug parameters.

Run from the TouchDesigner Textport after loading the master project:

    mod.song_slug_params.setup()

The script looks at every operator connected to ableton_switcher and ensures it
has a custom string parameter named Songslug. Existing non-empty values are left
alone; missing values are inferred from names like bedroom_visual_v2.
"""

PARAM_PAGE = "Live Set"
PARAM_NAME = "Songslug"
PARAM_LABEL = "Song Slug"
DEFAULT_SWITCHER = "ableton_switcher"


def setup(switcher_path=DEFAULT_SWITCHER, dry_run=False, save_external_tox=False):
    switcher = op(switcher_path)
    if switcher is None:
        raise ValueError("No switcher found at {}".format(switcher_path))

    rows = []
    seen = {}
    for index, visual in visual_inputs(switcher):
        existing = song_slug(visual)
        slug = existing or infer_song_slug_from_name(visual.name)
        rows.append((index, visual, slug, existing))
        if slug:
            seen.setdefault(slug, []).append(visual)
        if not dry_run:
            ensure_song_slug_parameter(visual, slug)
            if save_external_tox:
                save_external_tox_if_possible(visual)

    print_report(rows, seen, dry_run)
    return rows


def validate(switcher_path=DEFAULT_SWITCHER):
    rows = setup(switcher_path=switcher_path, dry_run=True)
    missing = [visual for _index, visual, slug, _existing in rows if not slug]
    duplicates = duplicate_slugs(rows)
    return {
        "missing": missing,
        "duplicates": duplicates,
        "count": len(rows),
    }


def visual_inputs(switcher):
    for index, connector in enumerate(switcher.inputs):
        visual = connector.parent()
        if visual is not None:
            yield index, visual


def ensure_song_slug_parameter(visual, slug):
    parameter = visual.par[PARAM_NAME]
    if parameter is None:
        page(visual, PARAM_PAGE).appendStr(PARAM_NAME, label=PARAM_LABEL)
        parameter = visual.par[PARAM_NAME]
    if parameter is not None and not parameter.eval():
        parameter.val = slug
    return parameter


def song_slug(visual):
    parameter = visual.par[PARAM_NAME]
    if parameter is None:
        return ""
    return normalize_song_slug(parameter.eval())


def infer_song_slug_from_name(name):
    slug = str(name)
    for suffix in ("_visual_v2", "_visual", "_live_v2", "_live"):
        if slug.endswith(suffix):
            slug = slug[:-len(suffix)]
            break
    return normalize_song_slug(slug)


def normalize_song_slug(value):
    if value is None:
        return ""
    text = str(value).strip().lower()
    return "_".join(text.split())


def duplicate_slugs(rows):
    seen = {}
    for _index, visual, slug, _existing in rows:
        if slug:
            seen.setdefault(slug, []).append(visual)
    return {slug: visuals for slug, visuals in seen.items() if len(visuals) > 1}


def page(operator, name):
    for custom_page in operator.customPages:
        if custom_page.name == name:
            return custom_page
    return operator.appendCustomPage(name)


def save_external_tox_if_possible(visual):
    for parameter_name in ("saveexternaltoxpulse", "saveexternaltox"):
        parameter = visual.par[parameter_name]
        if parameter is not None:
            try:
                parameter.pulse()
                print("Saved external tox for {}".format(visual.path))
                return True
            except Exception as exc:
                print("Could not pulse {} on {}: {}".format(parameter_name, visual.path, exc))
    print("No external tox save pulse found for {}".format(visual.path))
    return False


def print_report(rows, seen, dry_run):
    action = "Would update" if dry_run else "Updated"
    print("{} {} visual Songslug parameters:".format(action, len(rows)))
    for index, visual, slug, existing in rows:
        status = "kept" if existing else "inferred"
        print("  input {}: {} -> {} ({})".format(index, visual.path, slug or "<missing>", status))

    duplicates = {slug: visuals for slug, visuals in seen.items() if len(visuals) > 1}
    if duplicates:
        print("Duplicate Songslug values:")
        for slug, visuals in duplicates.items():
            paths = ", ".join(visual.path for visual in visuals)
            print("  {}: {}".format(slug, paths))
