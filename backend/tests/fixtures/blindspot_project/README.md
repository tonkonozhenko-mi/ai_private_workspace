# Blind-spot fixture

A project shaped like a real one: infrastructure in `infra/`, automation in
`scripts/`, and a note in a format nobody can read in `data/`. Nothing lives in
`src/`.

That last part is the whole point. Release 0.7.3 taught the file classifier
Bicep and PowerShell but not the walk that feeds it, and the walk only reached
`src/`, `app/`, `backend/` and a handful of other privileged folders. So these
two files were cut before the classifier saw them — and because a rule cut them,
they did not even appear in the "files I can't read yet" line. Invisible in the
index and invisible in the confession.

Used by `backend/tests/test_scan_sees_ordinary_folders.py`, and by hand for the
live check: open this folder as a workspace and Home should say it is built with
Bicep and PowerShell, and admit one `.xyz` it cannot read.
