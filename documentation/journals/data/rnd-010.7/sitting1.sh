set -u
# RND-010.7 sitting 1, headless: the shade walk's skip (this branch) against
# main. The skip is CPU only (an unshaded body draws no pixels in the walk),
# so the dummy driver times it as the screen would. At 150 / 300 and
# 250 / 600 packed, quiet: draw_leads (the walk's pieces), then the draw by
# layer (the `enemies/shade` row), each in ABBA order (before, after,
# after, before); the tree is switched between the two commits for each
# run. It switches the tree, so it runs from a copy outside the repo, from
# the repo root with a clean tree:
#   bash sitting1.sh OUT_DIR BEFORE_SHA AFTER_SHA
S="${1:?usage: bash sitting1.sh OUT_DIR BEFORE AFTER}"; BEFORE="${2:?}"; AFTER="${3:?}"; mkdir -p "$S"
if [ -n "$(git status --porcelain --untracked-files=no)" ]; then echo "STOP: tracked changes"; exit 1; fi
HOME_REF=$(git branch --show-current)
trap 'git switch -q "$HOME_REF"' EXIT
load() { powershell -NoProfile -Command "(Get-CimInstance Win32_Processor | Measure-Object -Property LoadPercentage -Average).Average"; }
stamp() { echo "=== $1  cpu load $(load)%  $(date +%H:%M:%S)" >> "$S/s1_meta.txt"; }
echo "before $BEFORE  after $AFTER  started $(date '+%Y-%m-%d %H:%M:%S')  headless" > "$S/s1_meta.txt"
export SDL_VIDEODRIVER=dummy SDL_AUDIODRIVER=dummy
run() {   # run SIDE TOOL LIVE ELAPSED ROUND
  sha=$BEFORE; [ "$1" = after ] && sha=$AFTER
  git switch -q --detach "$sha" || exit 1
  stamp "$2 $3 $1 $5 ($(git rev-parse --short HEAD))"
  if [ "$2" = leads ]; then
    python -m tools.benchmarks.draw_leads --live "$3" --elapsed "$4" --rounds 400 > "$S/s1_leads_$3_${1}_$5.txt" 2>&1
  else
    python -m tools.benchmarks.spawn_stress --live "$3" --elapsed "$4" --pack --layers --frames 600 \
      > "$S/s1_layers_$3_${1}_$5.txt" 2>&1
  fi
}
for tool in leads layers; do
  for pair in "150 300" "250 600"; do
    set -- $pair
    run before "$tool" "$1" "$2" a
    run after "$tool" "$1" "$2" a
    run after "$tool" "$1" "$2" b
    run before "$tool" "$1" "$2" b
  done
done
echo "finished $(date +%H:%M:%S)  cpu load $(load)%" >> "$S/s1_meta.txt"
