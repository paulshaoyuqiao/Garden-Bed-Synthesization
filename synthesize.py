# !/usr/bin/env python3

import cv2
import numpy as np
import matplotlib.pyplot as plt
import json

# Sample encoding mapping leaf types (ordinal) to RGB values.
ENCODING = {
    0: [255, 0, 0],
    1: [0, 255, 0],
    2: [0, 0, 255]
}

def create_mask(leaf, leaf_type):
    """This method creates a mask over the leaf based on the provided encoding.
    The encoding determines the color of the mask (type-based).
    """
    gray_scaled = cv2.cvtColor(leaf, cv2.COLOR_RGB2GRAY)
    _, mask = cv2.threshold(gray_scaled, 10, 255, cv2.THRESH_BINARY)
    rows, cols = mask.shape
    remasked = np.zeros((rows, cols, 3), dtype=np.uint8)
    remasked[mask[:, :] > 0, :] = ENCODING[leaf_type]
    return remasked

def rotate_image(mat, angle):
    """Rotates an image (angle in degrees) about the center and expands image to avoid cropping
    """

    height, width = mat.shape[:2] # image shape has 3 dimensions
    image_center = (width/2, height/2) # getRotationMatrix2D needs coordinates in reverse order (width, height) compared to shape
    rotation_mat = cv2.getRotationMatrix2D(image_center, angle, 1.)

    # rotation calculates the cos and sin, taking absolutes of those.
    abs_cos = abs(rotation_mat[0,0]) 
    abs_sin = abs(rotation_mat[0,1])

    # find the new width and height bounds
    bound_w = int(height * abs_sin + width * abs_cos)
    bound_h = int(height * abs_cos + width * abs_sin)

    # subtract old image center (bringing image back to origo) and adding the new image center coordinates
    rotation_mat[0, 2] += bound_w/2 - image_center[0]
    rotation_mat[1, 2] += bound_h/2 - image_center[1]

    # rotate image with the new bounds and translated rotation matrix
    rotated_mat = cv2.warpAffine(mat, rotation_mat, (bound_w, bound_h))
    return rotated_mat

def build_randomized_layout(leaves_src, background_src, background_mask_src, num_iters=15, seed=15):
    """This method builds a newly synthesized garden bed by randomly
    overlaying augmented single leaves on top of the original background.
    In the end, an updated garden bed along with its mask are returned.
    """
    # Fix random seed for reproducible results.
    np.random.seed(seed)
    
    leaves = [[np.copy(leaf_src[0]), leaf_src[1]] for leaf_src in leaves_src]
    leaves_mask = [create_mask(leaf_src[0]) for leaf_src in leaves_src]

    max_rows, max_cols, _ = background_src.shape
    background = np.copy(background_src)
    background_mask = np.copy(background_mask_src)
    
    for i in range(num_iters):
        idx = i % len(leaves)
        leaf = np.copy(leaves[idx])
        leaf_mask = np.copy(leaves_mask[idx])

        # Randomly resize the leaf and its mask between 0.75x and 1.25x.
        dim_ratio = np.random.uniform(0.75, 1.25)
        leaf = cv2.resize(leaf, (0, 0), fx=dim_ratio, fy=dim_ratio)
        leaf_mask = cv2.resize(leaf_mask, (0, 0), fx=dim_ratio, fy=dim_ratio)

        # Randomly rotate the leaf and its mask between 0 and 360 degrees.
        rot = int(np.random.uniform(0, 360))
        leaf = rotate_image(leaf, rot)
        leaf_mask = rotate_image(leaf_mask, rot)

        rows, cols, channels = leaf.shape

        # Randomly picks a location to place the leaf from its top left corner.
        rot = np.random.randint(0, 360)
        d_row = int(np.random.uniform(0, max_rows - rows))
        d_col = int(np.random.uniform(0, max_cols - cols))

        # The specification of the ROI determines where the masked leaf will be placed.
        roi = background[d_row:rows + d_row, d_col:cols + d_col, :]
        roi_mask = background_mask[d_row:rows + d_row, d_col:cols + d_col, :]

        # Now create a mask of the leaf and its inverse mask 
        img2gray = cv2.cvtColor(leaf,cv2.COLOR_RGB2GRAY)
        ret, mask = cv2.threshold(img2gray, 10, 255, cv2.THRESH_BINARY)
        mask_inv = cv2.bitwise_not(mask)

        # Now black-out the area of leaf in ROI
        cropped_background = cv2.bitwise_and(roi,roi, mask=mask_inv)
        cropped_background_mask = cv2.bitwise_and(roi_mask, roi_mask, mask=mask_inv)

        # Take only region of leaf from leaf image.
        target = cv2.bitwise_and(leaf, leaf, mask=mask)
        target_mask = cv2.bitwise_and(leaf_mask, leaf_mask, mask=mask)

        # Put the leaf in ROI and modify the background image
        dst = cv2.add(cropped_background,target)
        background[d_row:rows + d_row, d_col:cols + d_col] = dst

        dst_mask = cv2.add(cropped_background_mask, target_mask)
        background_mask[d_row:rows + d_row, d_col:cols + d_col] = dst_mask
    
    return background, background_mask

if __name__ == "__main__":
    try:
        f = open("config.json")
        config = json.load(f)
    except FileNotFoundError:
        print("Please specify a config json file.")
    except:
        print("Encountered errors while parsing json")
    
    background_path = config["background"]
    background_mask_path = config["background_mask"]
    background_src = cv2.cvtColor(cv2.imread(background_path), cv2.COLOR_BGR2RGB)
    background_mask_src = cv2.cvtColor(cv2.imread(background_mask_path), cv2.COLOR_BGR2RGB)
    max_background_row, max_background_col, _ = background_src.shape

    leaves = config["leaves"]
    leaves_src = [[cv2.cvtColor(cv2.imread(leaf[0]), cv2.COLOR_BGR2RGB), leaf[1]] for leaf in leaves]

    encodings = config["encodings"]
    num_leaves = config["iterations"]
    num_simulations = config["num_copies"]
    side_len = config["dim"]

    for i in range(num_simulations):
        r = int(np.random.uniform(0, max_background_row - side_len))
        c = int(np.random.uniform(0, max_background_col - side_len))
        background_patch = background_src[r:r+side_len, c:c+side_len, :]
        background_mask_patch = background_mask_src[r:r+side_len, c:c+side_len, :]
        synthesized_background, synthesized_mask = build_randomized_layout(
            leaves_src, background_patch, background_mask_patch, num_leaves)
        plt.imsave("{}-{}.png".format("Synthesized-Background", i), synthesized_background)
        plt.imsave("{}-{}.png".format("Synthesized-Mask", i), synthesized_mask)


