set -u
# RND-010.2 sitting 8: the bias probe again on the committed tool (the
# hero kept on its anchor), at 150 / 300 and 250 / 600.
# Run from the worktree root with a clean tree: bash <this file>
S="C:/Users/juanp/AppData/Local/Temp/claude/D--Documentos-Work-pygame-deathlite-game/9ec11fc6-cf2e-4f08-bc07-e9215b570e7d/scratchpad"
if [ -n "$(git status --porcelain --untracked-files=no)" ]; then echo "STOP: tracked changes"; exit 1; fi
if [ ! -f save.json ]; then echo "STOP: no save.json"; exit 1; fi
load() { powershell -NoProfile -Command "(Get-CimInstance Win32_Processor | Measure-Object -Property LoadPercentage -Average).Average"; }
procs() { powershell -NoProfile -Command "Get-Process | Sort-Object CPU -Descending | Select-Object -First 8 Name, CPU | Format-Table -AutoSize | Out-String -Width 120"; }
{
  echo "commit $(git rev-parse --short HEAD)  started $(date '+%Y-%m-%d %H:%M:%S')"
  python -c "import json;print('save', json.load(open('save.json'))['settings']['display'])"
  echo "--- top processes by CPU time at the start"; procs
} > "$S/s8_meta.txt"
for pair in "150 300" "250 600"; do
  set -- $pair
  echo "=== bias $1  cpu load $(load)%  $(date +%H:%M:%S)" >> "$S/s8_meta.txt"
  SDL_VIDEODRIVER=windows python -m tools.benchmarks.layer_probes bias --live "$1" --elapsed "$2" \
    > "$S/s8_bias_$1.txt" 2>&1
done
{ echo "finished $(date '+%H:%M:%S')  cpu load $(load)%"; echo "--- top processes by CPU time at the end"; procs; } >> "$S/s8_meta.txt"
