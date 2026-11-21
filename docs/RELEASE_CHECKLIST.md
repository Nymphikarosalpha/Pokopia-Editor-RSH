# Release checklist

- [ ] Fork retains upstream git history, LICENSE and original author notices.
- [ ] Run `python tools/prepare_fork.py --check-only`.
- [ ] Build Windows executable from the fork source.
- [ ] Confirm the application starts and original pages still work.
- [ ] Back up a game save externally; test all write actions on a **copy**.
- [ ] Validate resident add/remove and home link/unlink against the supported save format.
- [ ] Validate habitat placement and event-item preparation on each claimed island.
- [ ] Mark unverified spawn and story-event functionality clearly as experimental.
- [ ] Remove any private save files, keys, console dumps, debug logs or personal paths.
- [ ] Check source/license notices and any bundled third-party dependencies.
- [ ] Only then create a GitHub release and attach the tested EXE.
