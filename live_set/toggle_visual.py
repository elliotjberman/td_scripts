def toggle_visual(is_on: bool) -> None:
    parent().par.Abletonvisuals = int(is_on)

toggle_visual(args[0])
