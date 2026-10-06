set -u
# RND-010.3 sitting 3: the quiet draw by layer at this branch's code (the
# fight's baseline, rounds a and b, as RND-010.2's sitting 7 took it), and the
# two sprite caches again with the miss cost over passes and the bytes held.
# Run from the repo root with a clean tree: bash sitting3.sh OUT_DIR
S="${1:?usage: bash sitting3.sh OUT_DIR}"; mkdir -p "$S"
if [ -n "$(git status --porcelain --untracked-files=no)" ]; then echo "STOP: tracked changes"; exit 1; fi
if [ ! -f save.json ]; then echo "STOP: no save.json"; exit 1; fi
load() { powershell -NoProfile -Command "(Get-CimInstance Win32_Processor | Measure-Object -Property LoadPercentage -Average).Average"; }
procs() { powershell -NoProfile -Command "Get-Process | Sort-Object CPU -Descending | Select-Object -First 8 Name, CPU | Format-Table -AutoSize | Out-String -Width 120"; }
stamp() { echo "=== $1  cpu load $(load)%  $(date +%H:%M:%S)" >> "$S/r3_meta.txt"; }
{
  echo "commit $(git rev-parse --short HEAD)  started $(date '+%Y-%m-%d %H:%M:%S')"
  python -c "import json;print('save', json.load(open('save.json'))['settings']['display'])"
  echo "--- top processes by CPU time at the start"; procs
} > "$S/r3_meta.txt"
export SDL_VIDEODRIVER=windows
for pair in "150 300" "250 600"; do
  set -- $pair
  for round in a b; do
    stamp "quiet $1$round"; python -m tools.benchmarks.spawn_stress --live "$1" --elapsed "$2" --pack --layers \
                              --frames 600 > "$S/r3_quiet_$1$round.txt" 2>&1
  done
  stamp "caches $1"; python -m tools.benchmarks.sprite_caches --live "$1" --elapsed "$2" > "$S/r3_caches_$1.txt" 2>&1
done
{ echo "finished $(date '+%H:%M:%S')  cpu load $(load)%"; echo "--- top processes by CPU time at the end"; procs; } >> "$S/r3_meta.txt"
