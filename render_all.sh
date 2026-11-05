#!/bin/sh
# vyrenderuje všechny čtverce, které mají připravenou scénu (prep.py): ./render_all.sh [varianty]
set -e
for c in $( (.venv/bin/python 2>/dev/null || .venv/Scripts/python) -c "import geo, os; print(' '.join(f'{i},{j}' for i, j in geo.CHUNKS if os.path.exists(geo.chunk_dir((i, j)) + '/scene.json')))"); do
  ./render_chunk.sh $c "$@"
done
