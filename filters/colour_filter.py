import os
import sys
from PIL import Image
import numpy as np


def is_color_in_range(r, g, b):
    """
    Check if a color is within the specified RGB range.
    Range: rgb(220,230,230) to rgb(240,240,235)
    Only returns true if both R and B pixels are below 245.
    """
    return (r <= 245) and (b <= 245)


def apply_filter(image_path, output_path=None):
    """
    Apply a color filter similar to dilation.
    Looks for colors within the specified RGB range in a 3x3 neighborhood
    and replaces them with the color from above the image.

    Args:
        image_path: Path to the input image
        output_path: Path to save the output image (optional)

    Returns:
        The filtered PIL Image object
    """
    # Open the image
    img = Image.open(image_path)

    # Convert to RGB if not already
    if img.mode != 'RGB':
        img = img.convert('RGB')

    # Convert to numpy array for easier manipulation
    img_array = np.array(img)
    height, width, _ = img_array.shape

    # Create a copy for the result
    result_array = img_array.copy()

    # Process each pixel (except the top row)
    ctr = 0
    while ctr != 4:
        ctr += 1
        for y in range(1, height):
            for x in range(width):
                # Check the current pixel
                current_pixel = img_array[y, x]
                r, g, b = current_pixel

                # If the current pixel is in the target color range
                if is_color_in_range(r, g, b):
                    # Check 3x3 neighborhood
                    neighborhood_in_range = False

                    # Define neighborhood bounds for 3x3 area
                    y_start = max(0, y - 1)
                    y_end = min(height, y + 2)
                    x_start = max(0, x - 1)
                    x_end = min(width, x + 2)

                    # Check each pixel in the neighborhood
                    for ny in range(y_start, y_end):
                        for nx in range(x_start, x_end):
                            if ny == y and nx == x:
                                continue  # Skip the center pixel

                            nr, ng, nb = img_array[ny, nx]
                            if is_color_in_range(nr, ng, nb):
                                neighborhood_in_range = True
                                break

                        if neighborhood_in_range:
                            break

                    # If any pixel in the neighborhood is in range, replace with pixel above
                    if neighborhood_in_range and y > 0:
                        result_array[y, x] = [0, 0, 0]  # img_array[y-1, x]

    # Convert back to PIL Image
    result_img = Image.fromarray(result_array)

    # Save the result if output path is provided
    if output_path:
        result_img.save(output_path)

    return result_img


def main():
    """
    Main function to process the command line arguments and apply the filter.
    """
    # Check if the image path is provided
    if len(sys.argv) < 2:
        print("Usage: python filters.py <input_image_path> [output_image_path]")
        return

    input_path = sys.argv[1]

    # Default output path if not provided
    if len(sys.argv) >= 3:
        output_path = sys.argv[2]
    else:
        # Create output filename based on input
        name, ext = os.path.splitext(input_path)
        output_path = f"{name}_filtered{ext}"

    # Check if the input file exists
    if not os.path.exists(input_path):
        print(f"Error: Input file '{input_path}' not found.")
        return

    try:
        # Apply the filter
        print(f"Applying filter to '{input_path}'...")
        result_img = apply_filter(input_path, output_path)
        print("Filter applied successfully.")
    except Exception as e:
        print(f"Error applying filter: {e}")


if __name__ == "__main__":
    # Example usage with the provided image
    if len(sys.argv) == 1:
        # If no arguments provided, use the example image
        example_image = "live/1763260389-clock1.jpg"
        if os.path.exists(example_image):
            print(f"No arguments provided. Using example image: {example_image}")
            output_image = "live/1763260389-clock1_filtered.jpg"
            try:
                print(f"Applying filter to example image: {example_image}")
                result_img = apply_filter(example_image, output_image)
                print("Filter applied successfully to example image.")
            except Exception as e:
                print(f"Error applying filter to example image: {e}")
        else:
            print(f"Example image '{example_image}' not found.")
            print("Usage: python filters.py <input_image_path> [output_image_path]")
    else:
        main()
