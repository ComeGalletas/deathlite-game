# RND-010.5 raw measurements

The outputs behind the RND-010.5 results in
[`crowd_draw_journal.md`](../../crowd_draw_journal.md), kept as printed.
Each file's first line is the command that made it.

`tools/benchmarks/debug_lines.py` on the packed scene, seed 35, headless
(`SDL_VIDEODRIVER=dummy`), on the owner's machine on 2026-10-07, from
this branch. The work timed is CPU only: `report_debug` draws nothing,
so the display driver does not change it.

| File | Scene |
|---|---|
| `live_150_elapsed_200.txt` | 150 packed, quiet |
| `live_250_elapsed_600.txt` | 250 packed, quiet |
| `live_150_elapsed_200_elements.txt` | 150 packed, the hero fighting (`--elements`) |
| `live_250_elapsed_600_elements.txt` | 250 packed, the hero fighting |

Each line prints the median of 2000 `report_debug` calls in microseconds
(with the p90), that median in milliseconds a frame, and the median of
2000 `active_auras` calls alone.
