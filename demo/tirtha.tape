# tirtha · vhs tape
#
# Record this with:
#     brew install vhs
#     vhs demo/tirtha.tape
#
# Produces demo/tirtha.gif — drops cleanly into the README.
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

# 1. Show that tirtha is installed and what it can do.
Type "tirtha --help"
Enter
Sleep 3s

# 2. Show the accessibility subcommand.
Type "clear && tirtha accessibility --help"
Enter
Sleep 3s

# 3. Run the pipeline on a real region (Brownsville, Brooklyn).
#    Uses cached data on second run — under 30s end-to-end.
Type "clear && tirtha accessibility run \"
Enter
Type "  --region 'Brownsville, Brooklyn' \"
Enter
Type "  --resolution 10 \"
Enter
Type "  --out ./demo-out"
Enter
Sleep 30s

# 4. Show the outputs that were produced.
Type "clear && ls -la demo-out/"
Enter
Sleep 2s

Type "cat demo-out/summary.txt"
Enter
Sleep 6s

# 5. Same pipeline, different application — schools instead of healthcare.
Type "clear && tirtha accessibility run \"
Enter
Type "  --region 'Brownsville, Brooklyn' \"
Enter
Type "  --preset schools \"
Enter
Type "  --out ./demo-out-schools --no-figure --quiet"
Enter
Sleep 25s

# 6. Compare the headline numbers.
Type "diff demo-out/summary.txt demo-out-schools/summary.txt"
Enter
Sleep 5s

Type "echo 'same pipeline, different humanitarian application.'"
Enter
Sleep 3s
