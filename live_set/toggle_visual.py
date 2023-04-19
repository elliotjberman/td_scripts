def toggle_visual(is_on: bool) -> None:
    parent().par.Index = int(is_on)

toggle_visual(args[0])
