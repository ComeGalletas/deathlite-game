set -u
# RND-010.2: a sitting on the committed tool, 150 / 200 / 250 packed, two
# interleaved rounds, then the two probes on the same scenes.
# Run from the repo root with a clean tree: bash <this file> OUT_DIR [PREFIX]
S="${1:?usage: bash sitting.sh OUT_DIR [PREFIX]}"; P="${2:-s9}"; mkdir -p "$S"
if [ -n "$(git status --porcelain --untracked-files=no)" ]; then echo "STOP: tracked changes"; exit 1; fi
# Without the save the window falls back to the default display: stop.
if [ ! -f save.json ]; then echo "STOP: no save.json in the repo root (see the journal)"; exit 1; fi
load() { powershell -NoProfile -Command "(Get-CimInstance Win32_Processor | Measure-Object -Property LoadPercentage -Average).Average"; }
procs() { powershell -NoProfile -Command "Get-Process | Sort-Object CPU -Descending | Select-Object -First 8 Name, CPU | Format-Table -AutoSize | Out-String -Width 120"; }
{
  echo "commit $(git rev-parse --short HEAD)  started $(date '+%Y-%m-%d %H:%M')"
  python -c "import json;print('save', json.load(open('save.json'))['settings']['display'])"
  echo "--- top processes by CPU time at the start"; procs
} > "$S/${P}_meta.txt"
for round in a b; do
  for pair in "150 300" "200 400" "250 600"; do
    set -- $pair
    echo "=== $1$round  cpu load $(load)%  $(date +%H:%M:%S)" >> "$S/${P}_meta.txt"
    SDL_VIDEODRIVER=windows python -m tools.benchmarks.spawn_stress --live "$1" --elapsed "$2" \
      --pack --layers --frames 600 > "$S/${P}_$1$round.txt" 2>&1
  done
done
for pair in "150 300" "250 600"; do
  set -- $pair
  echo "=== bias $1  cpu load $(load)%  $(date +%H:%M:%S)" >> "$S/${P}_meta.txt"
  SDL_VIDEODRIVER=windows python -m tools.benchmarks.layer_probes bias --live "$1" --elapsed "$2" \
    > "$S/${P}_bias_$1.txt" 2>&1
  echo "=== nested $1  cpu load $(load)%  $(date +%H:%M:%S)" >> "$S/${P}_meta.txt"
  SDL_VIDEODRIVER=windows python -m tools.benchmarks.layer_probes nested --live "$1" --elapsed "$2" \
    > "$S/${P}_nested_$1.txt" 2>&1
done
{ echo "finished $(date '+%H:%M')  cpu load $(load)%"; echo "--- top processes by CPU time at the end"; procs; } >> "$S/${P}_meta.txt"
