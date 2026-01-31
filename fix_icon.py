"""
Script to remove red color from icon and replace it with transparency
"""
from PIL import Image
import numpy as np

def remove_red_make_transparent(input_path, output_path):
    """Remove red color and make it transparent"""
    # Open image
    img = Image.open(input_path).convert('RGBA')
    data = np.array(img)
    
    # Get RGB channels
    red, green, blue, alpha = data.T
    
    # Find red areas (where red > green and red > blue)
    # Adjust threshold as needed
    red_areas = (red > green + 30) & (red > blue + 30)
    
    # Make red areas transparent
    data[..., 3][red_areas.T] = 0
    
    # Save
    result = Image.fromarray(data)
    result.save(output_path, 'PNG')
    print(f"✅ Saved to: {output_path}")
    
    return output_path

if __name__ == "__main__":
    input_icon = "app_icon.png"
    output_icon = "app_icon_fixed.png"
    
    print(f"🔧 Removing red color from {input_icon}...")
    result = remove_red_make_transparent(input_icon, output_icon)
    
    # Replace original
    import shutil
    shutil.copy(result, input_icon)
    print(f"✅ Replaced {input_icon}")
    
    # Also update in assets if exists
    import os
    if os.path.exists("assets"):
        assets_icon = os.path.join("assets", "app_icon.png")
        if os.path.exists(assets_icon):
            shutil.copy(result, assets_icon)
            print(f"✅ Updated {assets_icon}")
    
    print("\n🎉 Done! Icon updated everywhere.")
