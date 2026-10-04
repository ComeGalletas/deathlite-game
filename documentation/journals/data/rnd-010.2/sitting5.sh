set -u
# RND-010.2 sitting 5: the committed tool, 150 / 200 / 250 packed, two
# interleaved rounds, then the two probes on the same scenes.
# Run from the worktree root with a clean tree: bash <this file>
S="C:/Users/juanp/AppData/Local/Temp/claude/D--Documentos-Work-pygame-deathlite-game/9ec11fc6-cf2e-4f08-bc07-e9215b570e7d/scratchpad"
if [ -n "$(git status --porcelain --untracked-files=no)" ]; then echo "STOP: tracked changes"; exit 1; fi
load() { powershell -NoProfile -Command "(Get-CimInstance Win32_Processor | Measure-Object -Property LoadPercentage -Average).Average"; }
{
  echo "commit $(git rev-parse --short HEAD)  started $(date '+%Y-%m-%d %H:%M')"
  python -c "import json;print('save', json.load(open('save.json'))['settings']['display'])"
} > "$S/s5_meta.txt"
for round in a b; do
  for pair in "150 300" "200 400" "250 600"; do
    set -- $pair
    echo "=== $1$round  cpu load $(load)%  $(date +%H:%M:%S)" >> "$S/s5_meta.txt"
    SDL_VIDEODRIVER=windows python -m tools.benchmarks.spawn_stress --live "$1" --elapsed "$2" \
      --pack --layers --frames 600 > "$S/s5_$1$round.txt" 2>&1
  done
done
for pair in "150 300" "250 600"; do
  set -- $pair
  echo "=== bias $1  cpu load $(load)%  $(date +%H:%M:%S)" >> "$S/s5_meta.txt"
  SDL_VIDEODRIVER=windows python -m tools.benchmarks.layer_probes bias --live "$1" --elapsed "$2" \
    > "$S/s5_bias_$1.txt" 2>&1
  echo "=== nested $1  cpu load $(load)%  $(date +%H:%M:%S)" >> "$S/s5_meta.txt"
  SDL_VIDEODRIVER=windows python -m tools.benchmarks.layer_probes nested --live "$1" --elapsed "$2" \
    > "$S/s5_nested_$1.txt" 2>&1
done
echo "finished $(date '+%H:%M')" >> "$S/s5_meta.txt"
