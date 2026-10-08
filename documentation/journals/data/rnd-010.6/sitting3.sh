set -u
# RND-010.6 sitting 3: `aura_rle`, `shape_cached` and `ring_cached` again, their caches warm from block to block (sitting
# 2 emptied it at every undo) and holding every aura frame the fight asks
# for. At 150 / 300 and 250 / 600 packed with the
# hero fighting, checked byte for byte and timed in ABBA blocks. Run from
# the repo root with a clean tree:
#   bash documentation/journals/data/rnd-010.6/sitting3.sh OUT_DIR
S="${1:?usage: bash sitting3.sh OUT_DIR}"; mkdir -p "$S"
if [ -n "$(git status --porcelain --untracked-files=no)" ]; then echo "STOP: tracked changes"; exit 1; fi
if [ ! -f save.json ]; then echo "STOP: no save.json"; exit 1; fi
load() { powershell -NoProfile -Command "(Get-CimInstance Win32_Processor | Measure-Object -Property LoadPercentage -Average).Average"; }
procs() { powershell -NoProfile -Command "Get-Process | Sort-Object CPU -Descending | Select-Object -First 8 Name, CPU | Format-Table -AutoSize | Out-String -Width 120"; }
windows() { powershell -NoProfile -Command "Get-Process | Where-Object { \$_.MainWindowHandle -ne 0 } | Sort-Object Name | Select-Object -ExpandProperty Name | Get-Unique"; }
stamp() { echo "=== $1  cpu load $(load)%  $(date +%H:%M:%S)" >> "$S/s3_meta.txt"; }
{
  echo "commit $(git rev-parse --short HEAD)  started $(date '+%Y-%m-%d %H:%M:%S')"
  python -c "import json;print('save', json.load(open('save.json'))['settings']['display'])"
  echo "--- processes with a window at the start, by name"; windows
  echo "--- top processes by CPU time at the start"; procs
} > "$S/s3_meta.txt"
export SDL_VIDEODRIVER=windows
for pair in "150 300" "250 600"; do
  set -- $pair
  stamp "variants $1"
  python -m tools.benchmarks.draw_variants --live "$1" --elapsed "$2" --elements \
    --variants aura_rle,shape_cached,ring_cached > "$S/s3_variants_$1.txt" 2>&1
done
{ echo "finished $(date '+%H:%M:%S')  cpu load $(load)%"
  echo "--- processes with a window at the end, by name"; windows
  echo "--- top processes by CPU time at the end"; procs; } >> "$S/s3_meta.txt"
