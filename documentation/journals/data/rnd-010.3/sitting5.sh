set -u
# RND-010.3 sitting 5: everything the results compare, in one sitting at one
# commit. At 150 / 300 and 250 / 600 packed: the quiet draw and the fight by
# layer in ABBA order (quiet, fight, fight, quiet), so a drift falls on both
# sides alike; the two sprite caches replayed (with the cost of emptying one);
# and wash_lru timed against the draw with the hero fighting (the mean and the
# tails as well as the p50). Then blit_floor at 2560x1080 with the screen fill
# alone (n=0) beside 100 to 300 sprites.
# Run from the repo root with a clean tree: bash sitting5.sh OUT_DIR
S="${1:?usage: bash sitting5.sh OUT_DIR}"; mkdir -p "$S"
if [ -n "$(git status --porcelain --untracked-files=no)" ]; then echo "STOP: tracked changes"; exit 1; fi
if [ ! -f save.json ]; then echo "STOP: no save.json"; exit 1; fi
load() { powershell -NoProfile -Command "(Get-CimInstance Win32_Processor | Measure-Object -Property LoadPercentage -Average).Average"; }
procs() { powershell -NoProfile -Command "Get-Process | Sort-Object CPU -Descending | Select-Object -First 8 Name, CPU | Format-Table -AutoSize | Out-String -Width 120"; }
# Every process with a window of its own, by name only (no window titles).
windows() { powershell -NoProfile -Command "Get-Process | Where-Object { \$_.MainWindowHandle -ne 0 } | Sort-Object Name | Select-Object -ExpandProperty Name | Get-Unique"; }
stamp() { echo "=== $1  cpu load $(load)%  $(date +%H:%M:%S)" >> "$S/r5_meta.txt"; }
{
  echo "commit $(git rev-parse --short HEAD)  started $(date '+%Y-%m-%d %H:%M:%S')"
  python -c "import json;print('save', json.load(open('save.json'))['settings']['display'])"
  echo "--- processes with a window at the start, by name"; windows
  echo "--- top processes by CPU time at the start"; procs
} > "$S/r5_meta.txt"
export SDL_VIDEODRIVER=windows
for pair in "150 300" "250 600"; do
  set -- $pair
  for step in quiet_a fight_a fight_b quiet_b; do
    kind=${step%_*}
    flag=""; [ "$kind" = fight ] && flag="--elements"
    stamp "$step $1"; python -m tools.benchmarks.spawn_stress --live "$1" --elapsed "$2" --pack --layers \
                        $flag --frames 600 > "$S/r5_${kind}_$1${step#*_}.txt" 2>&1
  done
  stamp "caches $1";   python -m tools.benchmarks.sprite_caches --live "$1" --elapsed "$2" > "$S/r5_caches_$1.txt" 2>&1
  stamp "wash_lru $1"; python -m tools.benchmarks.draw_variants --live "$1" --elapsed "$2" --elements \
                         --variants wash_lru > "$S/r5_wash_lru_$1.txt" 2>&1
done
stamp "blit_floor"; python -m tools.benchmarks.blit_floor --sizes 2560x1080 --counts 0,100,200,300 \
                      > "$S/r5_blit_floor.txt" 2>&1
{ echo "finished $(date '+%H:%M:%S')  cpu load $(load)%"
  echo "--- processes with a window at the end, by name"; windows
  echo "--- top processes by CPU time at the end"; procs; } >> "$S/r5_meta.txt"
