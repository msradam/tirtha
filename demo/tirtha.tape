# tirtha · vhs tape
#
# Record this with:
#     brew install vhs
#     vhs demo/tirtha.tape
#
# Produces demo/tirtha.gif. Drops cleanly into the README.
#
# Why Kew Gardens, Queens? It is the author's home neighborhood. Small,
# residential, every walking-time result is intuit-checkable from local
# knowledge. Nominatim does not have it as a polygon, so we use --bbox.
#
# References:
#   https://github.com/charmbracelet/vhs

Output demo/tirtha.gif

Set FontSize 14
Set Width 1200
Set Height 720
Set Padding 18
Set Theme "Dracula"
Set Shell "zsh"
Set TypingSpeed 30ms

# 1. The CLI surface.
Type "tirtha --help"
Enter
Sleep 3s

# 2. Run the pipeline on Kew Gardens, Queens (author's home neighborhood).
Type "clear && tirtha accessibility run \"
Enter
Type "  --bbox '-73.835,40.700,-73.810,40.725' \"
Enter
Type "  --region 'Kew Gardens, Queens' \"
Enter
Type "  --resolution 10 \"
Enter
Type "  --out ./demo-out/kew-health"
Enter
Sleep 25s

# 3. Show what got written.
Type "clear && ls -la demo-out/kew-health/"
Enter
Sleep 3s

Type "cat demo-out/kew-health/summary.txt"
Enter
Sleep 5s

# 4. Same pipeline, schools instead of healthcare.
Type "clear && tirtha accessibility run \"
Enter
Type "  --bbox '-73.835,40.700,-73.810,40.725' \"
Enter
Type "  --region 'Kew Gardens, Queens' \"
Enter
Type "  --preset schools \"
Enter
Type "  --out ./demo-out/kew-schools --no-figure --quiet"
Enter
Sleep 20s

# 5. Side-by-side comparison. Same code, different humanitarian question.
Type "diff demo-out/kew-health/summary.txt demo-out/kew-schools/summary.txt"
Enter
Sleep 5s

# 6. Now the graph artifact. Pixels + roads + facilities as one graph.
Type "clear && tirtha graph build \"
Enter
Type "  --bbox '-73.835,40.700,-73.810,40.725' \"
Enter
Type "  --region 'Kew Gardens, Queens' \"
Enter
Type "  --resolution 30 \"
Enter
Type "  --out demo-out/kew.graph.npz"
Enter
Sleep 60s

# 7. Inspect the graph. One-line summary of pixel + road nodes.
Type "tirtha graph inspect demo-out/kew.graph.npz"
Enter
Sleep 4s

Type "echo 'same pipeline → travel-time map AND graph artifact, in two commands.'"
Enter
Sleep 4s
