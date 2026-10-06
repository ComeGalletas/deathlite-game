set -u
# RND-010.3 sitting 1: the committed tools, on screen, at 150 / 300 and 250 / 600
# packed: the leads probe, the variant probe, the draw by layer with the hero
# fighting (--elements), then the plan's two appendix probes.
# Run from the repo root with a clean tree: bash <this file> OUT_DIR
S="${1:?usage: bash r3_sitting.sh OUT_DIR}"; mkdir -p "$S"
if [ -n "$(git status --porcelain --untracked-files=no)" ]; then echo "STOP: tracked changes"; exit 1; fi
if [ ! -f save.json ]; then echo "STOP: no save.json"; exit 1; fi
load() { powershell -NoProfile -Command "(Get-CimInstance Win32_Processor | Measure-Object -Property LoadPercentage -Average).Average"; }
procs() { powershell -NoProfile -Command "Get-Process | Sort-Object CPU -Descending | Select-Object -First 8 Name, CPU | Format-Table -AutoSize | Out-String -Width 120"; }
stamp() { echo "=== $1  cpu load $(load)%  $(date +%H:%M:%S)" >> "$S/r1_meta.txt"; }
{
  echo "commit $(git rev-parse --short HEAD)  started $(date '+%Y-%m-%d %H:%M:%S')"
  python -c "import json;print('save', json.load(open('save.json'))['settings']['display'])"
  echo "--- top processes by CPU time at the start"; procs
} > "$S/r1_meta.txt"
export SDL_VIDEODRIVER=windows
for pair in "150 300" "250 600"; do
  set -- $pair
  stamp "leads $1";    python -m tools.benchmarks.draw_leads --live "$1" --elapsed "$2" > "$S/r1_leads_$1.txt" 2>&1
  stamp "variants $1"; python -m tools.benchmarks.draw_variants --live "$1" --elapsed "$2" > "$S/r1_variants_$1.txt" 2>&1
  stamp "fight $1";    python -m tools.benchmarks.spawn_stress --live "$1" --elapsed "$2" --pack --layers \
                         --elements --frames 600 > "$S/r1_fight_$1.txt" 2>&1
done
stamp "gc_probe";   python -m tools.benchmarks.gc_probe --pack > "$S/r1_gc.txt" 2>&1
stamp "blit_floor"; python -m tools.benchmarks.blit_floor --sizes 2560x1080 > "$S/r1_blit_floor.txt" 2>&1
{ echo "finished $(date '+%H:%M:%S')  cpu load $(load)%"; echo "--- top processes by CPU time at the end"; procs; } >> "$S/r1_meta.txt"
