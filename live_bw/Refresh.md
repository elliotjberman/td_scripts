# Updating a visual

Edit the standalone song project, then use **Save Component** on its mapped
wrapper to overwrite the canonical TOX registered in [setlist.json](setlist.json).
Save the authoring TOE too. Saving the TOE alone does not export the component.

Pulse **Load Set** in the master, or reopen it. The loader rereads component
files and warms the selected set. The master file does not need to be edited,
rebuilt or saved to consume an updated visual.

The earlier `dev/live_bw/refresh.py` snapshot-repackaging workflow is retired.
See [README.md](README.md) for component paths and
[Visual Structure](../VISUAL_STRUCTURE.md#mapped-component-contract-v1) for the
portable wrapper contract. Adding another song is a component plus config entry.
