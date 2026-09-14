# ColorPicker Design Analysis

## What the mock shows

Two side-by-side states of the same popover -- idle (left) and with a selection active (right).

**Popover card**
- White background, rounded-xl corners, subtle drop shadow
- Total width: approximately 260px (6 swatches x 28px hit area + 5 gaps x 12px + 32px padding = 260px)
- Padding: ~16px on all sides

**Title**
- Small semibold label "Color" at top left, approximately 12px
- Sits ~12-16px above the swatch grid

**Swatch grid**
- 6 columns x 3 rows = 18 swatches
- Inner dot diameter: 20px, circular
- Clickable hit area: 28px x 28px (4px transparent padding around the dot)
- Gap between swatches: 12px

**Selected state (right panel)**
- Outer ring: ~2px gray outline, offset ~2.5px from the dot edge
- Centered checkmark SVG on top of the swatch dot
- Checkmark color adapts to the swatch background (see correction 3 below)

**Divider**
- Thin 1px horizontal line below the swatch grid, ~12px margin above and below

**Custom color row**
- Full-width, below divider
- Small "+" icon followed by "Custom color" label text
- No hex value visible by default (see correction 2 below)

---

## Three corrections applied on top of the raw mock

**1. Exact hex values**
The 18 hex values are used verbatim as specified, not approximated from the image.
Pixel-sampling the mock would introduce drift. The values were finalized in a
separate color-accuracy correction round and are locked.

Row 1: #6B7280, #D14343, #E66A5A, #D97706, #B7791F, #C79219
Row 2: #7A9A24, #3C8C5A, #167C5A, #16847B, #1487A6, #2E7DBA
Row 3: #356FD6, #4F61C7, #6E62C6, #8C55B5, #B44B8B, #C84C62

**2. Custom color hex display**
The raw mock erroneously showed a preset hex next to "Custom color." The correct
behavior: no hex text appears next to "Custom color" when the current value matches
any of the 18 preset swatches. A hex value is shown only when the user has selected
a genuinely non-preset color through the secondary native color input.

**3. Automatic checkmark contrast**
White was used on every swatch in the raw mock. Visual testing confirmed white
reads poorly on the gray swatch (#6B7280) and on brighter saturated colors
(amber, gold, lime). The correct behavior is to compute perceived brightness
for each swatch and choose a dark (#1a1a1a) checkmark on bright swatches and
a white checkmark on dark ones.

Formula: perceived brightness = (0.299 * R + 0.587 * G + 0.114 * B) / 255
Threshold: 0.44
- brightness > 0.44: dark checkmark (#1a1a1a)
- brightness <= 0.44: white checkmark (#ffffff)

Sample values:
- #6B7280 gray: brightness = 0.445 -> dark checkmark
- #7A9A24 lime: brightness = 0.514 -> dark checkmark
- #D97706 amber: brightness = 0.531 -> dark checkmark
- #16847B teal: brightness = 0.385 -> white checkmark
- #356FD6 blue: brightness = 0.413 -> white checkmark
- #4F61C7 indigo: brightness = 0.405 -> white checkmark
