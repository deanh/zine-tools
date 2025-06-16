# 8-Page Booklet Maker

A web application for creating 8-page saddle-stitched booklets with proper imposition for printing on A4 or A3 paper.

## Features

- Drag-and-drop image placement on 8 pages
- Support for A4 and A3 paper sizes
- Landscape and portrait orientations
- Visual preview of print imposition
- Generates print-ready PDF with correct page ordering
- Resize and position images on pages

## Installation

1. Install Python dependencies:
```bash
pip install -r requirements.txt
```

2. Run the application:
```bash
python app.py
```

3. Open your browser to `http://localhost:5000`

## Usage

1. **Select paper size and orientation**: Choose A4/A3 and landscape/portrait
2. **Upload images**: Click "Upload Images" to add images to your library
3. **Place images**: Drag images from the library onto pages
4. **Adjust images**: Click to select, drag to move, use corner handles to resize
5. **Generate PDF**: Click "Generate PDF" to create your print-ready booklet

## Printing Instructions

The PDF is formatted for saddle-stitch binding:
- Print double-sided (flip on short edge)
- Fold the printed sheet in half
- The pages will be in correct reading order (1-8)

## Page Imposition

Front side: 8, 1, 4, 5
Back side: 2, 7, 6, 3

This arrangement ensures proper page order when folded.