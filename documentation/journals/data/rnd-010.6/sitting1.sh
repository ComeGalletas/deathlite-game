set -u
# RND-010.6 sitting 1: the elemental under-layer on screen, at this branch's
# one commit. At 150 / 300 and 250 / 600 packed with the hero fighting:
# the draw by layer (the under-layer split into its passes), twice; the
# leads probe; then the four candidate variants, each checked byte for
# byte and timed in ABBA blocks. Run from the repo root with a clean tree:
#   bash documentation/journals/data/rnd-010.6/sitting1.sh OUT_DIR
S="${1:?usage: bash sitting1.sh OUT_DIR}"; mkdir -p "$S"
if [ -n "$(git status --porcelain --untracked-files=no)" ]; then echo "STOP: tracked changes"; exit 1; fi
if [ ! -f save.json ]; then echo "STOP: no save.json"; exit 1; fi
load() { powershell -NoProfile -Command "(Get-CimInstance Win32_Processor | Measure-Object -Property LoadPercentage -Average).Average"; }
procs() { powershell -NoProfile -Command "Get-Process | Sort-Object CPU -Descending | Select-Object -First 8 Name, CPU | Format-Table -AutoSize | Out-String -Width 120"; }
windows() { powershell -NoProfile -Command "Get-Process | Where-Object { \$_.MainWindowHandle -ne 0 } | Sort-Object Name | Select-Object -ExpandProperty Name | Get-Unique"; }
stamp() { echo "=== $1  cpu load $(load)%  $(date +%H:%M:%S)" >> "$S/s1_meta.txt"; }
{
  echo "commit $(git rev-parse --short HEAD)  started $(date '+%Y-%m-%d %H:%M:%S')"
  python -c "import json;print('save', json.load(open('save.json'))['settings']['display'])"
  echo "--- processes with a window at the start, by name"; windows
  echo "--- top processes by CPU time at the start"; procs
} > "$S/s1_meta.txt"
export SDL_VIDEODRIVER=windows
for pair in "150 300" "250 600"; do
  set -- $pair
  for round in a b; do
    stamp "layers $1 $round"
    python -m tools.benchmarks.spawn_stress --live "$1" --elapsed "$2" --pack --layers --elements \
      --frames 600 > "$S/s1_layers_$1_$round.txt" 2>&1
  done
  stamp "leads $1"
  python -m tools.benchmarks.under_leads --live "$1" --elapsed "$2" > "$S/s1_leads_$1.txt" 2>&1
  stamp "variants $1"
  python -m tools.benchmarks.draw_variants --live "$1" --elapsed "$2" --elements \
    --variants shape_cached,ring_cached,aura_rle,aura_lookup_once > "$S/s1_variants_$1.txt" 2>&1
done
{ echo "finished $(date '+%H:%M:%S')  cpu load $(load)%"
  echo "--- processes with a window at the end, by name"; windows
  echo "--- top processes by CPU time at the end"; procs; } >> "$S/s1_meta.txt"
