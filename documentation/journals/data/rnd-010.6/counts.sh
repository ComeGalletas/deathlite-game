set -u
# RND-010.6: the counts behind the RLE cache's cap and its memory, headless
# (frames and bytes do not depend on the display or the load; the resident
# memory, `rle_memory.py`, is the process's own and moves a little). From the repo root:
#   bash documentation/journals/data/rnd-010.6/counts.sh
D=documentation/journals/data/rnd-010.6
for pair in "150 300" "250 600"; do
  set -- $pair
  echo "python $D/aura_keys.py $1 $2" > "$D/keys_$1.txt"
  python "$D/aura_keys.py" "$1" "$2" 2>&1 | tail -1 >> "$D/keys_$1.txt"
  echo "python $D/rle_bytes.py $1 $2" > "$D/bytes_$1.txt"
  python "$D/rle_bytes.py" "$1" "$2" 2>&1 | tail -1 >> "$D/bytes_$1.txt"
  echo "python $D/rle_memory.py $1 $2" > "$D/memory_$1.txt"
  python "$D/rle_memory.py" "$1" "$2" 2>&1 | tail -1 >> "$D/memory_$1.txt"
done
