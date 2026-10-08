set -u
# RND-010.7: the walk's shapes against the walk, headless, in one process
# each (`walk_shapes.py`). From the repo root:
#   bash documentation/journals/data/rnd-010.7/shapes.sh
D=documentation/journals/data/rnd-010.7
for pair in "150 300" "250 600"; do
  set -- $pair
  echo "python $D/walk_shapes.py $1 $2" > "$D/shapes_$1.txt"
  python "$D/walk_shapes.py" "$1" "$2" 2>&1 | tail -5 >> "$D/shapes_$1.txt"
done
