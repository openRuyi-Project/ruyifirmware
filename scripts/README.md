# Release tags

Use `tag-release.py` to create the same annotated tag in Ruyi Firmware and
each openRuyi component. The script tags the commits recorded in Ruyi
Firmware's current `HEAD`, including components with no new commits.
Linux keeps its existing tag. The upstream TianoCore `edk2-platforms`
repository is skipped.

Keep the component development repositories beside `ruyifirmware`, with
the names used in `.gitmodules`. Use `--repos-dir` for another directory.
The script does not tag the validation checkouts under `src/`.

Commit the release changes and submodule updates. Preview the targets:

```sh
python3 scripts/tag-release.py 20261108 --dry-run
```

Create the local tags:

```sh
python3 scripts/tag-release.py 20261108
```

The script checks every target before creating tags. It reuses a local
tag at the required commit and rejects a local tag at a different commit.
Use a new name, such as `20261108-1`, if a release tag already points to
another commit.

Run the printed push commands in order. Stop if any push fails.
A command also pushes `ruyi`
when that branch points to the tagged commit. The script never pushes or
replaces a tag. Git rejects conflicting remote tags when you push.
Push the Ruyi Firmware tag only after all component pushes succeed.
This starts the build and prerelease workflow.
