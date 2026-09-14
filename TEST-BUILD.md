# Testing

Open Reunion is currently a beta. Campaign progression, setup and controls have
been tested, and player feedback is welcome through
[Issues](https://github.com/scienceandresearch/open-reunion/issues).

## Test coverage

The unit suite uses generated data to check game rules, file formats, saves
and interface behavior. CI runs it on Windows with Python 3.11 and 3.14.
Six optional tests need additional local test data and skip in a clean checkout.

Local integration tests cover asset conversion, import cancellation and retry,
startup, time controls, save/load, graphical screens, battles and the ending.
A campaign test has also reached victory from New Game without resource
assistance. All 23 supplied checkpoints have been loaded against imported assets.

The Windows package has been tested after a fresh extraction and import, without
Python on PATH. Audio tests mute their own process while exercising playback.
Current results and known issues are listed in [status.md](status.md).

## Testing a change

Run the relevant unit tests first. Changes to asset conversion, graphical
screens or audio also need a local check with a supported original copy.
Packaging changes should be checked with `tools/check_tester_archive.py`;
see the [build guide](docs/SOURCE-QUICKSTART.md).

For gameplay reports, include the starting checkpoint or New Game choice, game
date, actions taken and any admin use. The [feedback form](TESTER-FEEDBACK.md)
provides a template.
