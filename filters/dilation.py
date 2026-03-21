import os
import sys
from PIL import Image
import numpy as np


def calculate_luminosity(r, g, b):
    """
    Calculate the luminosity of a pixel using the standard formula.
    Luminosity = 0.299 * R + 0.587 * G + 0.114 * B

    Args:
        r, g, b: RGB values (0-255)

    Returns:
        Luminosity value (0-255)
    """
    return 0.299 * r + 0.587 * g + 0.114 * b


def apply_filter(image_path, output_path=None, iterations=4):
    """
    Apply morphological dilation to an image.
    For each pixel, finds the second darkest pixel in its 3x3 neighborhood
    and assigns that value to the processed pixel.

    Args:
        image_path: Path to the input image
        output_path: Path to save the output image (optional)
        iterations: Number of times to apply the dilation (default: 4)

    Returns:
        The dilated PIL Image object
    """
    # Open the image
    img = Image.open(image_path)

    # Convert to RGB if not already
    if img.mode != 'RGB':
        img = img.convert('RGB')

    # Convert to numpy array for easier manipulation
    result_array = np.array(img)

    # Apply dilation for the specified number of iterations
    for iteration in range(iterations):
        # Create a copy for this iteration
        img_array = result_array.copy()
        height, width, _ = img_array.shape

        # Process each pixel
        for y in range(height):
            for x in range(width):
                # Define neighborhood bounds for 3x3 area
                y_start = max(0, y - 1)
                y_end = min(height, y + 2)
                x_start = max(0, x - 1)
                x_end = min(width, x + 2)

                # Collect all pixels and their luminosities in the neighborhood
                neighborhood_pixels = []
                neighborhood_luminosities = []

                for ny in range(y_start, y_end):
                    for nx in range(x_start, x_end):
                        neighborhood_pixel = img_array[ny, nx]
                        neighborhood_luminosity = calculate_luminosity(*neighborhood_pixel)
                        neighborhood_pixels.append(neighborhood_pixel)
                        neighborhood_luminosities.append(neighborhood_luminosity)

                # Sort by luminosity (ascending - darkest first)
                sorted_indices = np.argsort(neighborhood_luminosities)

                # Handle edge cases: if neighborhood has only 1 pixel, use it
                # If neighborhood has 2+ pixels, use the second darkest
                if len(sorted_indices) >= 2:
                    second_darkest_index = sorted_indices[1]
                    second_darkest_pixel = neighborhood_pixels[second_darkest_index]
                else:
                    # Fallback to darkest if only one pixel available
                    second_darkest_pixel = neighborhood_pixels[sorted_indices[0]]

                # Set the processed pixel to the second darkest found
                result_array[y, x] = second_darkest_pixel

    # Convert back to PIL Image
    result_img = Image.fromarray(result_array)

    # Save the result if output path is provided
    if output_path:
        result_img.save(output_path)

    return result_img


def replace_with_white(image_path, output_path=None,
                       min_red=110, max_green=100, max_blue=150,
                       red_dominance_ratio=1.5,
                       save_mask=False, mask_path=None):
    """
    Replace red/pinkish colors in an image with white.

    Detects red/pinkish pixels based on RGB thresholds and replaces them
    with white (255, 255, 255). Useful for preprocessing clock images
    with red digits.

    Args:
        image_path: Path to the input image
        output_path: Optional path to save the output image
        min_red: Minimum red channel value (default: 150)
        max_green: Maximum green channel value (default: 100)
        max_blue: Maximum blue channel value (default: 150)
        red_dominance_ratio: Minimum R/G ratio for red detection (default: 1.5)
        save_mask: If True, save a visualization mask (default: False)
        mask_path: Path for mask visualization (auto-generated if not provided)

    Returns:
        PIL Image object with red/pinkish colors replaced by white
    """
    # Open the image
    img = Image.open(image_path)

    # Convert to RGB if not already
    if img.mode != 'RGB':
        img = img.convert('RGB')

    # Convert to numpy array for easier manipulation
    img_array = np.array(img)

    # Extract RGB channels
    r_channel = img_array[:, :, 0]
    g_channel = img_array[:, :, 1]
    b_channel = img_array[:, :, 2]

    # Create condition masks for red/pinkish detection
    red_condition = r_channel >= min_red
    green_condition = g_channel <= max_green
    blue_condition = b_channel <= max_blue

    # Calculate R/G ratio with zero division protection
    with np.errstate(divide='ignore', invalid='ignore'):
        rg_ratio = np.where(g_channel > 0, r_channel / g_channel, np.inf)
    dominance_condition = rg_ratio >= red_dominance_ratio

    # Combine all conditions
    red_mask = red_condition & green_condition & blue_condition & dominance_condition

    # Create a copy for the result
    result_array = img_array.copy()

    # Replace red/pinkish pixels with white
    result_array[red_mask] = [255, 255, 255]

    # Convert back to PIL Image
    result_img = Image.fromarray(result_array)

    # Save mask visualization if requested
    if save_mask:
        # Generate mask path if not provided
        if mask_path is None:
            name, ext = os.path.splitext(image_path)
            mask_path = f"{name}_mask{ext}"

        # Create binary mask (white for detected pixels, black for others)
        mask_array = np.zeros_like(img_array)
        mask_array[red_mask] = [255, 255, 255]
        mask_img = Image.fromarray(mask_array)
        mask_img.save(mask_path)
        print(f"Detection mask saved to: {mask_path}")

    # Save the result if output path is provided
    if output_path:
        result_img.save(output_path)

    return result_img


def main():
    """
    Main function to process command line arguments and apply dilation.
    """
    # Parse command line arguments
    args = sys.argv[1:]

    # Default values
    iterations = 1
    input_path = None
    output_path = None

    # Parse arguments
    i = 0
    while i < len(args):
        arg = args[i]
        if arg == '--iterations' or arg == '-i':
            if i + 1 < len(args):
                try:
                    iterations = int(args[i + 1])
                    if iterations < 1:
                        print("Error: Iterations must be a positive integer.")
                        return
                except ValueError:
                    print("Error: Iterations must be a valid integer.")
                    return
                i += 1
            else:
                print("Error: --iterations requires a value.")
                return
        elif arg.startswith('--iterations='):
            try:
                iterations = int(arg.split('=')[1])
                if iterations < 1:
                    print("Error: Iterations must be a positive integer.")
                    return
            except ValueError:
                print("Error: Iterations must be a valid integer.")
                return
        elif input_path is None:
            input_path = arg
        elif output_path is None:
            output_path = arg
        else:
            print(f"Warning: Unexpected argument '{arg}' ignored")
        i += 1

    # Check if the image path is provided
    if input_path is None:
        print("Usage: python dilation.py [--iterations N | -i N] <input_image_path> [output_image_path]")
        print("  --iterations N: Number of dilation iterations (default: 1)")
        print("  -i N:           Short form for --iterations")
        return

    # Default output path if not provided
    if output_path is None:
        name, ext = os.path.splitext(input_path)
        if iterations == 1:
            output_path = f"{name}_dilated{ext}"
        else:
            output_path = f"{name}_dilated_{iterations}x{ext}"

    # Check if the input file exists
    if not os.path.exists(input_path):
        print(f"Error: Input file '{input_path}' not found.")
        return

    try:
        # Apply dilation
        iteration_text = f"{iterations} iteration{'s' if iterations != 1 else ''}"
        print(f"Applying dilation ({iteration_text}) to '{input_path}'...")
        result_img = apply_filter(input_path, output_path, iterations)
        print("Dilation applied successfully.")
    except Exception as e:
        print(f"Error applying dilation: {e}")


if __name__ == "__main__":
    # Example usage with the provided image
    if len(sys.argv) == 1:
        # If no arguments provided, use the example image
        example_image = "live/1763260389-clock1.jpg"
        if os.path.exists(example_image):
            print(f"No arguments provided. Using example image: {example_image}")
            output_image = "live/1763260389-clock1_dilated.jpg"
            try:
                print(f"Applying dilation to example image: {example_image}")
                result_img = apply_filter(example_image, output_image)
                print("Dilation applied successfully to example image.")
            except Exception as e:
                print(f"Error applying dilation to example image: {e}")
        else:
            print(f"Example image '{example_image}' not found.")
            print("Usage: python dilation.py <input_image_path> [output_image_path]")
    else:
        main()
