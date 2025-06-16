#!/usr/bin/env python3

import click
from PIL import Image
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import A3
from reportlab.lib.units import mm
import sys
from pathlib import Path

# A3 dimensions
A3_WIDTH_MM = 297
A3_HEIGHT_MM = 420
A3_WIDTH_PT = A3_WIDTH_MM * mm
A3_HEIGHT_PT = A3_HEIGHT_MM * mm

# Printable area (289 x 409 mm)
PRINTABLE_WIDTH_MM = 289
PRINTABLE_HEIGHT_MM = 409
PRINTABLE_WIDTH_PT = PRINTABLE_WIDTH_MM * mm
PRINTABLE_HEIGHT_PT = PRINTABLE_HEIGHT_MM * mm

def add_crop_marks(c, x, y, width, height, mark_length=5*mm, mark_offset=3*mm):
    """Add crop marks to the canvas"""
    c.setStrokeColorRGB(0, 0, 0)
    c.setLineWidth(0.5)
    
    # Top-left
    c.line(x - mark_offset - mark_length, y + height, x - mark_offset, y + height)
    c.line(x, y + height + mark_offset, x, y + height + mark_offset + mark_length)
    
    # Top-right
    c.line(x + width + mark_offset, y + height, x + width + mark_offset + mark_length, y + height)
    c.line(x + width, y + height + mark_offset, x + width, y + height + mark_offset + mark_length)
    
    # Bottom-left
    c.line(x - mark_offset - mark_length, y, x - mark_offset, y)
    c.line(x, y - mark_offset, x, y - mark_offset - mark_length)
    
    # Bottom-right
    c.line(x + width + mark_offset, y, x + width + mark_offset + mark_length, y)
    c.line(x + width, y - mark_offset, x + width, y - mark_offset - mark_length)

def process_image(image_path, output_path, size, dpi, cropmarks, bleed, fit_mode, position):
    """Process image and create PDF"""
    
    # Load image
    if image_path:
        image = Image.open(image_path)
    else:
        image = Image.open(sys.stdin.buffer)
    
    # Ensure grayscale
    if image.mode != 'L':
        image = image.convert('L')
    
    # Get image dimensions
    img_width, img_height = image.size
    
    # Determine target size
    if size == 'A3':
        page_width, page_height = A3_WIDTH_PT, A3_HEIGHT_PT
        max_width, max_height = PRINTABLE_WIDTH_PT, PRINTABLE_HEIGHT_PT
    else:
        # Custom size handling could go here
        page_width, page_height = A3_WIDTH_PT, A3_HEIGHT_PT
        max_width, max_height = PRINTABLE_WIDTH_PT, PRINTABLE_HEIGHT_PT
    
    # Account for bleed
    if bleed > 0:
        bleed_pt = bleed * mm
        content_width = img_width
        content_height = img_height
    else:
        bleed_pt = 0
        content_width = img_width
        content_height = img_height
    
    # Calculate scaling
    if fit_mode == 'none':
        # Use image at current resolution/size
        if dpi:
            # Calculate size based on DPI
            scale = dpi / 72.0  # PDF uses 72 DPI
            display_width = img_width / scale
            display_height = img_height / scale
        else:
            display_width = img_width
            display_height = img_height
    elif fit_mode == 'contain':
        # Fit within printable area while maintaining aspect ratio
        scale = min(max_width / content_width, max_height / content_height)
        display_width = content_width * scale
        display_height = content_height * scale
    elif fit_mode == 'cover':
        # Cover the entire printable area while maintaining aspect ratio
        scale = max(max_width / content_width, max_height / content_height)
        display_width = content_width * scale
        display_height = content_height * scale
    
    # Calculate position
    if position == 'center':
        x = (page_width - display_width) / 2
        y = (page_height - display_height) / 2
    elif position == 'top-left':
        x = (page_width - max_width) / 2
        y = page_height - (page_height - max_height) / 2 - display_height
    else:
        # Default to center
        x = (page_width - display_width) / 2
        y = (page_height - display_height) / 2
    
    # Create PDF
    if output_path:
        c = canvas.Canvas(output_path, pagesize=(page_width, page_height))
    else:
        import io
        buffer = io.BytesIO()
        c = canvas.Canvas(buffer, pagesize=(page_width, page_height))
    
    # Save the image temporarily
    import tempfile
    with tempfile.NamedTemporaryFile(suffix='.png', delete=False) as tmp:
        image.save(tmp.name, 'PNG', dpi=(dpi, dpi) if dpi else (600, 600))
        
        # Draw image
        c.drawImage(tmp.name, x, y, display_width, display_height, preserveAspectRatio=True)
        
        # Add crop marks if requested
        if cropmarks:
            # Calculate actual content area (excluding bleed)
            content_x = x + bleed_pt
            content_y = y + bleed_pt
            content_display_width = display_width - 2 * bleed_pt
            content_display_height = display_height - 2 * bleed_pt
            
            add_crop_marks(c, content_x, content_y, content_display_width, content_display_height)
        
        # Clean up temp file
        Path(tmp.name).unlink()
    
    # Add metadata
    c.setAuthor("riso-format")
    c.setTitle(f"Riso Print - Grayscale Layer")
    c.setSubject(f"Resolution: {dpi or 600} DPI")
    
    # Save PDF
    c.save()
    
    if not output_path:
        buffer.seek(0)
        sys.stdout.buffer.write(buffer.read())

@click.command()
@click.option('-i', '--input', 'input_path', type=click.Path(exists=True), help='Input image path')
@click.option('-o', '--output', 'output_path', type=click.Path(), help='Output PDF path')
@click.option('--size', type=click.Choice(['A3']), default='A3', help='Paper size')
@click.option('--dpi', type=int, default=600, help='Resolution in DPI (default: 600)')
@click.option('--cropmarks/--no-cropmarks', default=False, help='Add crop marks')
@click.option('--bleed', type=float, default=0, help='Bleed in mm (default: 0)')
@click.option('--fit-mode', type=click.Choice(['none', 'contain', 'cover']), default='contain', 
              help='How to fit image: none (original size), contain (fit within), cover (fill)')
@click.option('--position', type=click.Choice(['center', 'top-left']), default='center', 
              help='Image position on page')
def main(input_path, output_path, size, dpi, cropmarks, bleed, fit_mode, position):
    """Convert grayscale images to print-ready PDFs for Risograph printing"""
    
    if not input_path and sys.stdin.isatty():
        click.echo("Error: No input provided. Use -i flag or pipe image data.", err=True)
        sys.exit(1)
    
    process_image(input_path, output_path, size, dpi, cropmarks, bleed, fit_mode, position)
    
    if output_path:
        click.echo(f"Created PDF: {output_path}", err=True)

if __name__ == '__main__':
    main()