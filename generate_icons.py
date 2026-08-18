from PIL import Image, ImageDraw

def create_icon(size, filename):
    img = Image.new('RGB', (size, size), color='#040b14')
    d = ImageDraw.Draw(img)
    # Simple rectangle to simulate an icon
    d.rectangle([(size//4, size//4), (size*3//4, size*3//4)], fill='#38bdf8', outline='#10b981', width=5)
    img.save(filename)

if __name__ == "__main__":
    import os
    os.makedirs('static/icons', exist_ok=True)
    create_icon(192, 'static/icons/icon-192x192.png')
    create_icon(512, 'static/icons/icon-512x512.png')
    print("Icons generated successfully in static/icons/")
