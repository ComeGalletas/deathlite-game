set -u
# RND-010.6 sitting 4: the auras blitted from RLE copies (this branch)
# against main, in one sitting. At 150 / 300, 200 / 400 and 250 / 600
# packed: the draw by layer with the hero fighting, then quiet (no aura is
# drawn there, a control), each in ABBA order (before, after, after,
# before), so a drift falls on both sides alike; the tree is switched
# between main and the branch for each run. Run from the repo root with a
# clean tree:
#   bash documentation/journals/data/rnd-010.6/sitting4.sh OUT_DIR BEFORE_SHA AFTER_SHA
S="${1:?usage: bash sitting4.sh OUT_DIR BEFORE AFTER}"; BEFORE="${2:?}"; AFTER="${3:?}"; mkdir -p "$S"
if [ -n "$(git status --porcelain --untracked-files=no)" ]; then echo "STOP: tracked changes"; exit 1; fi
if [ ! -f save.json ]; then echo "STOP: no save.json"; exit 1; fi
HOME_REF=$(git branch --show-current)
trap 'git switch -q "$HOME_REF"' EXIT
load() { powershell -NoProfile -Command "(Get-CimInstance Win32_Processor | Measure-Object -Property LoadPercentage -Average).Average"; }
procs() { powershell -NoProfile -Command "Get-Process | Sort-Object CPU -Descending | Select-Object -First 8 Name, CPU | Format-Table -AutoSize | Out-String -Width 120"; }
windows() { powershell -NoProfile -Command "Get-Process | Where-Object { \$_.MainWindowHandle -ne 0 } | Sort-Object Name | Select-Object -ExpandProperty Name | Get-Unique"; }
gpu() { nvidia-smi --query-gpu=utilization.gpu,memory.used --format=csv,noheader 2>/dev/null || echo "n/a"; }
stamp() { echo "=== $1  cpu load $(load)%  gpu $(gpu)  $(date +%H:%M:%S)" >> "$S/s4_meta.txt"; }
{
  echo "before $BEFORE  after $AFTER  started $(date '+%Y-%m-%d %H:%M:%S')"
  python -c "import json;print('save', json.load(open('save.json'))['settings']['display'])"
  echo "--- processes with a window at the start, by name"; windows
  echo "--- top processes by CPU time at the start"; procs
} > "$S/s4_meta.txt"
export SDL_VIDEODRIVER=windows
run() {   # run SIDE KIND LIVE ELAPSED ROUND
  sha=$BEFORE; [ "$1" = after ] && sha=$AFTER
  git switch -q --detach "$sha" || exit 1
  flag=""; [ "$2" = fight ] && flag="--elements"
  stamp "$2 $3 $1 $5 ($(git rev-parse --short HEAD))"
  python -m tools.benchmarks.spawn_stress --live "$3" --elapsed "$4" --pack --layers $flag --frames 600 \
    > "$S/s4_${2}_$3_${1}_$5.txt" 2>&1
}
for kind in fight quiet; do
  for pair in "150 300" "200 400" "250 600"; do
    set -- $pair
    run before "$kind" "$1" "$2" a
    run after "$kind" "$1" "$2" a
    run after "$kind" "$1" "$2" b
    run before "$kind" "$1" "$2" b
  done
done
{ echo "finished $(date +%H:%M:%S)  cpu load $(load)%  gpu $(gpu)"
  echo "--- processes with a window at the end, by name"; windows
  echo "--- top processes by CPU time at the end"; procs; } >> "$S/s4_meta.txt"
