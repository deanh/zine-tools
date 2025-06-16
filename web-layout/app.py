from flask import Flask, render_template, request, send_file, jsonify
from flask_cors import CORS
from reportlab.lib.pagesizes import A4, A3, landscape, portrait
from reportlab.pdfgen import canvas
from reportlab.lib.utils import ImageReader
from PIL import Image
import io
import base64
import json
import os

app = Flask(__name__)
CORS(app)

# Paper sizes in points (1 inch = 72 points)
PAPER_SIZES = {
    'A4': A4,  # (595.27, 841.89) points
    'A3': A3   # (841.89, 1190.55) points
}

def get_page_dimensions(paper_size, orientation):
    """Get the dimensions for a single page based on paper size and orientation."""
    base_size = PAPER_SIZES[paper_size]
    
    if orientation == 'landscape':
        # For landscape, we get 4 pages per sheet (2x2)
        if paper_size == 'A4':
            # A4 landscape gives us 4 A6 pages
            page_width = base_size[1] / 2  # Half of A4 height
            page_height = base_size[0] / 2  # Half of A4 width
        else:  # A3
            # A3 landscape gives us 4 A5 pages
            page_width = base_size[1] / 2
            page_height = base_size[0] / 2
    else:  # portrait
        # For portrait, we get 4 pages per sheet (2x2)
        if paper_size == 'A4':
            # A4 portrait gives us 4 A6 pages
            page_width = base_size[0] / 2
            page_height = base_size[1] / 2
        else:  # A3
            # A3 portrait gives us 4 A5 pages
            page_width = base_size[0] / 2
            page_height = base_size[1] / 2
    
    return page_width, page_height

def create_booklet_pdf(data):
    """Create a PDF with proper saddle-stitch imposition."""
    paper_size = data.get('paperSize', 'A4')
    orientation = data.get('orientation', 'landscape')
    pages_data = data.get('pages', {})
    
    # Get sheet size
    sheet_size = PAPER_SIZES[paper_size]
    if orientation == 'landscape':
        sheet_size = landscape(sheet_size)
    else:
        sheet_size = portrait(sheet_size)
    
    # Create PDF buffer
    buffer = io.BytesIO()
    c = canvas.Canvas(buffer, pagesize=sheet_size)
    
    # Get individual page dimensions
    page_width, page_height = get_page_dimensions(paper_size, orientation)
    
    # Define page positions on the sheet
    # For landscape: pages are arranged in 2x2 grid
    positions = {
        'front': {
            8: (0, page_height),              # Top-left
            1: (page_width, page_height),      # Top-right
            4: (0, 0),                         # Bottom-left
            5: (page_width, 0)                 # Bottom-right
        },
        'back': {
            2: (0, page_height),               # Top-left
            7: (page_width, page_height),      # Top-right
            6: (0, 0),                         # Bottom-left
            3: (page_width, 0)                 # Bottom-right
        }
    }
    
    # Draw front side
    draw_pages(c, pages_data, positions['front'], page_width, page_height)
    c.showPage()
    
    # Draw back side
    draw_pages(c, pages_data, positions['back'], page_width, page_height)
    
    c.save()
    buffer.seek(0)
    return buffer

def draw_pages(canvas_obj, pages_data, positions, page_width, page_height):
    """Draw pages on the canvas at specified positions."""
    for page_num, (x_offset, y_offset) in positions.items():
        # Draw page border (optional, for debugging)
        canvas_obj.setStrokeColorRGB(0.8, 0.8, 0.8)
        canvas_obj.rect(x_offset, y_offset, page_width, page_height)
        
        # Draw page number (small, for reference)
        canvas_obj.setFillColorRGB(0.7, 0.7, 0.7)
        canvas_obj.setFont("Helvetica", 8)
        canvas_obj.drawString(x_offset + 5, y_offset + page_height - 15, f"Page {page_num}")
        
        # Draw images for this page
        page_images = pages_data.get(str(page_num), [])
        for img_data in page_images:
            draw_image(canvas_obj, img_data, x_offset, y_offset, page_width, page_height)

def draw_image(canvas_obj, img_data, page_x, page_y, page_width, page_height):
    """Draw an image on the canvas with rotation and flip support."""
    try:
        # Extract image data
        src = img_data.get('src', '')
        x = img_data.get('x', 0)
        y = img_data.get('y', 0)
        width = img_data.get('width', 100)
        height = img_data.get('height', 'auto')
        rotation = img_data.get('rotation', 0)
        scale_x = img_data.get('scaleX', 1)
        
        if src.startswith('data:image'):
            # Decode base64 image
            header, data = src.split(',', 1)
            image_data = base64.b64decode(data)
            image = Image.open(io.BytesIO(image_data))
            
            # Calculate actual height if 'auto'
            if height == 'auto':
                img_width, img_height = image.size
                aspect_ratio = img_height / img_width
                height = width * aspect_ratio
            else:
                height = float(height)
            
            # Apply transformations to the image if needed
            if scale_x < 0:
                image = image.transpose(Image.FLIP_LEFT_RIGHT)
            
            # Create ImageReader object
            img_reader = ImageReader(image)
            
            # Save current canvas state
            canvas_obj.saveState()
            
            # Use dimensions directly - no scaling needed
            pdf_width = width
            pdf_height = height
            pdf_x = page_x + x
            pdf_y = page_y + page_height - y - pdf_height
            
            # Calculate center point for rotation
            center_x = pdf_x + pdf_width / 2
            center_y = pdf_y + pdf_height / 2
            
            # Apply rotation around center if needed
            if rotation != 0:
                canvas_obj.translate(center_x, center_y)
                canvas_obj.rotate(rotation)
                canvas_obj.translate(-center_x, -center_y)
            
            # Set clipping rectangle to page bounds
            from reportlab.pdfgen.canvas import Canvas
            from reportlab.lib.pagesizes import inch
            from reportlab.pdfgen import canvas as canvaslib
            
            # Create a clipping path
            p = canvas_obj.beginPath()
            p.rect(page_x, page_y, page_width, page_height)
            canvas_obj.clipPath(p, stroke=0, fill=0)
            
            # Draw the image at full size (will be clipped by page bounds)
            canvas_obj.drawImage(img_reader, pdf_x, pdf_y, width=pdf_width, height=pdf_height)
            
            # Restore canvas state
            canvas_obj.restoreState()
            
    except Exception as e:
        print(f"Error drawing image: {e}")

@app.route('/')
def index():
    return send_file('index.html')

@app.route('/style.css')
def style():
    return send_file('style.css')

@app.route('/script.js')
def script():
    return send_file('script.js')

@app.route('/palettes', methods=['GET'])
def get_palettes():
    """Get available color palettes from the palettes directory."""
    try:
        palettes_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'palettes')
        palettes = {}
        
        # Load built-in presets
        presets = {
            'riso-pink-blue': ['#FF0080', '#0078BF'],
            'riso-fluoro': ['#FF48B0', '#FFE800', '#00A95C'],
            'riso-primary': ['#FF0000', '#0000FF', '#FFFF00'],
            'riso-warm': ['#FF6600', '#FFE800', '#FF0080'],
            'riso-cool': ['#0078BF', '#00A95C', '#5C55A6'],
        }
        
        for name, colors in presets.items():
            palettes[name] = colors
        
        # Load palette files
        if os.path.exists(palettes_dir):
            for filename in os.listdir(palettes_dir):
                if filename.endswith('.txt'):
                    filepath = os.path.join(palettes_dir, filename)
                    palette_name = filename[:-4]  # Remove .txt
                    colors = []
                    
                    with open(filepath, 'r') as f:
                        for line in f:
                            line = line.strip()
                            # Skip comments and empty lines
                            if line and line.startswith('#') and len(line) >= 7:
                                # Check if it's a hex color (not a comment)
                                if all(c in '0123456789ABCDEFabcdef' for c in line[1:7]):
                                    colors.append(line)
                    
                    if colors:
                        palettes[palette_name] = colors
        
        return jsonify(palettes)
    except Exception as e:
        print(f"Error loading palettes: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/generate-pdf', methods=['POST'])
def generate_pdf():
    try:
        data = request.json
        pdf_buffer = create_booklet_pdf(data)
        
        return send_file(
            pdf_buffer,
            mimetype='application/pdf',
            as_attachment=True,
            download_name='booklet.pdf'
        )
    except Exception as e:
        print(f"Error generating PDF: {e}")
        return jsonify({'error': str(e)}), 500

if __name__ == '__main__':
    app.run(debug=True, port=5000)