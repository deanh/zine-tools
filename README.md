# Riso Printing Pipeline

A Unix-style pipeline for preparing images for Risograph printing.

## Installation

```bash
pip install -r requirements.txt

# For best performance, build the Cython extension:
cd tools
python setup.py build_ext --inplace
cd ..
```

## Image Size Requirements

### Input Images
- The pipeline accepts images of any size
- For best results, prepare images at the target print resolution:
  - **A3 at 600 DPI**: 7016 × 9933 pixels
  - **A3 at 300 DPI**: 3508 × 4961 pixels
  - **Printable area**: 289 × 409 mm (6803 × 9626 pixels at 600 DPI)

### Pre-processing
Use standard image tools to resize before the pipeline:
```bash
# Resize to A3 at 600 DPI using ImageMagick
convert input.jpg -resize 7016x9933 -density 600 prepared.jpg

# Or fit within printable area
convert input.jpg -resize 6803x9626 -density 600 prepared.jpg
```

## Pipeline Tools

### dither
Applies dithering algorithms with custom color palettes.

**Features:**
- Multiple algorithms: floyd-steinberg, atkinson, ordered (2x2, 4x4, 8x8)
- Custom palettes via hex colors, files, or presets
- Stdin/stdout support for piping

```bash
# Using hex colors
tools/dither.py -i image.jpg -o dithered.png --palette "#FF0080,#0078BF"

# Using palette file
tools/dither.py -i image.jpg --palette palettes/warm-duo.txt --algorithm atkinson

# Using preset
tools/dither.py -i image.jpg --palette riso-fluoro --algorithm ordered-4x4
```

### color-separate
Separates images into grayscale layers for each color.

**Features:**
- Auto-quantization for images with many colors
- Outputs color mapping JSON
- Coverage percentage reporting
- Optional PDF output

```bash
# Basic separation
tools/color-separate.py -i dithered.png --output-prefix layer_

# With quantization
tools/color-separate.py -i photo.jpg --max-colors 3 --output-dir separated/

# Direct to PDF
tools/color-separate.py -i dithered.png --output-format pdf
```

### riso-format
Converts images to print-ready PDFs with proper settings.

**Features:**
- A3 format with proper margins
- Crop marks and bleed support
- 600 DPI default resolution
- Grayscale conversion

```bash
# Basic PDF creation
tools/riso-format.py -i layer_1.png -o pink.pdf

# With crop marks and bleed
tools/riso-format.py -i layer_1.png -o pink.pdf --cropmarks --bleed 4

# Fit modes
tools/riso-format.py -i image.png -o output.pdf --fit-mode contain
```

### riso-preview
Creates a composite preview of separated layers.

**Features:**
- Overlay multiple layers with colors
- Auto-detect colors from JSON mapping
- Color swatches and labels
- Simulates riso overprinting

```bash
# From directory with colormap
tools/riso-preview.py -d separated/ -o preview.png

# Manual layers and colors
tools/riso-preview.py -l layer_1.png -l layer_2.png --colors "#FF0080,#0078BF" -o preview.png
```

## Complete Workflow Examples

### Basic Two-Color Print
```bash
# 1. Prepare image size (using ImageMagick)
convert photo.jpg -resize 6803x9626 -density 600 sized.jpg

# 2. Dither with two colors
tools/dither.py -i sized.jpg -o dithered.png --palette "#FF48B0,#0078BF"

# 3. Separate colors
tools/color-separate.py -i dithered.png --output-dir prints/

# 4. Create PDFs
tools/riso-format.py -i prints/layer_1.png -o prints/pink.pdf --cropmarks
tools/riso-format.py -i prints/layer_2.png -o prints/blue.pdf --cropmarks

# 5. Preview
tools/riso-preview.py -d prints/ -o prints/preview.png
```

### Using Palette Files
```bash
# Create custom palette
echo -e "#FF6C2F\n#00A95C\n#765BA7" > my-palette.txt

# Process with custom palette
tools/dither.py -i photo.jpg --palette my-palette.txt | \
tools/color-separate.py --output-format pdf --output-prefix final_
```

### Batch Processing
```bash
# Process multiple images
for img in *.jpg; do
    base=$(basename "$img" .jpg)
    tools/dither.py -i "$img" --palette riso-warm | \
    tools/color-separate.py --output-dir "$base/" --output-format pdf
done
```

## Available Presets

- `riso-pink-blue`: Classic pink (#FF0080) and blue (#0078BF)
- `riso-fluoro`: Fluorescent pink, yellow, green
- `riso-primary`: Red, blue, yellow
- `riso-warm`: Orange, yellow, pink
- `riso-cool`: Blue, green, purple