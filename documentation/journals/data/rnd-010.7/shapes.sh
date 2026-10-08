set -u
# RND-010.7: the walk's shapes against the walk, headless, in one process
# each (`walk_shapes.py`), twice at each count so the run-to-run spread is
# on record; the CPU load and the commit stamped before each run. From the
# repo root:
#   bash documentation/journals/data/rnd-010.7/shapes.sh
D=documentation/journals/data/rnd-010.7
load() { powershell -NoProfile -Command "(Get-CimInstance Win32_Processor | Measure-Object -Property LoadPercentage -Average).Average"; }
for pair in "150 300" "250 600"; do
  set -- $pair
  for round in a b; do
    out="$D/shapes_$1_$round.txt"
    echo "python $D/walk_shapes.py $1 $2" > "$out"
    echo "commit $(git rev-parse --short HEAD)  cpu load $(load)%  $(date '+%Y-%m-%d %H:%M:%S')" >> "$out"
    python "$D/walk_shapes.py" "$1" "$2" 2>&1 | tail -6 >> "$out"
  done
done
