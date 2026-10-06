set -u
# RND-010.3 sitting 2: the wash cache lead from sitting 1's fight, on screen,
# at 150 / 300 and 250 / 600 packed with the hero fighting: the two sprite
# caches replayed on the fight's own requests, the wash_lru variant timed
# against the draw, and a second round of the draw by layer in the fight.
# Run from the repo root with a clean tree: bash <this file> OUT_DIR
S="${1:?usage: bash r3_sitting2.sh OUT_DIR}"; mkdir -p "$S"
if [ -n "$(git status --porcelain --untracked-files=no)" ]; then echo "STOP: tracked changes"; exit 1; fi
if [ ! -f save.json ]; then echo "STOP: no save.json"; exit 1; fi
load() { powershell -NoProfile -Command "(Get-CimInstance Win32_Processor | Measure-Object -Property LoadPercentage -Average).Average"; }
procs() { powershell -NoProfile -Command "Get-Process | Sort-Object CPU -Descending | Select-Object -First 8 Name, CPU | Format-Table -AutoSize | Out-String -Width 120"; }
stamp() { echo "=== $1  cpu load $(load)%  $(date +%H:%M:%S)" >> "$S/r2_meta.txt"; }
{
  echo "commit $(git rev-parse --short HEAD)  started $(date '+%Y-%m-%d %H:%M:%S')"
  python -c "import json;print('save', json.load(open('save.json'))['settings']['display'])"
  echo "--- top processes by CPU time at the start"; procs
} > "$S/r2_meta.txt"
export SDL_VIDEODRIVER=windows
for pair in "150 300" "250 600"; do
  set -- $pair
  stamp "caches $1";   python -m tools.benchmarks.sprite_caches --live "$1" --elapsed "$2" > "$S/r2_caches_$1.txt" 2>&1
  stamp "wash_lru $1"; python -m tools.benchmarks.draw_variants --live "$1" --elapsed "$2" --elements \
                         --variants wash_lru > "$S/r2_wash_lru_$1.txt" 2>&1
  stamp "fight $1";    python -m tools.benchmarks.spawn_stress --live "$1" --elapsed "$2" --pack --layers \
                         --elements --frames 600 > "$S/r2_fight_$1.txt" 2>&1
done
{ echo "finished $(date '+%H:%M:%S')  cpu load $(load)%"; echo "--- top processes by CPU time at the end"; procs; } >> "$S/r2_meta.txt"
