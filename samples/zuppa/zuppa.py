"""
Mask R-CNN
Train on the toy Balloon dataset and implement color splash effect.

Copyright (c) 2018 Matterport, Inc.
Licensed under the MIT License (see LICENSE for details)
Written by Waleed Abdulla

------------------------------------------------------------

Usage: import the module (see Jupyter notebooks for examples), or run from
       the command line as such:

    # Train a new model starting from pre-trained COCO weights
    python3 balloon.py train --dataset=/path/to/balloon/dataset --weights=coco
    python object.py train --dataset=C:/mask/Mask_RCNN/samples/object/dataset --weights=coco
    # Resume training a model that you had trained earlier
    python3 balloon.py train --dataset=/path/to/balloon/dataset --weights=last

    # Train a new model starting from ImageNet weights
    python3 balloon.py train --dataset=/path/to/balloon/dataset --weights=imagenet

    # Apply color splash to an image
    python3 balloon.py splash --weights=/path/to/weights/file.h5 --image=<URL or path to file>

    # Apply color splash to video using the last weights you trained
    python3 balloon.py splash --weights=last --video=<URL or path to file>
"""

import os
import sys
import json
import datetime
import numpy as np
import skimage.draw

# Root directory of the project
ROOT_DIR = os.path.abspath("../../")
MASK_RCNN_ROOT_DIR = os.path.abspath("../../../Mask_RCNN")

# Import Mask RCNN
# sys.path.append(ROOT_DIR)  # To find local version of the library
sys.path.append(MASK_RCNN_ROOT_DIR)  # To find local version of the library
from mrcnn.config import Config
from mrcnn import model as modellib, utils
from imgaug import augmenters as iaa

# Path to trained weights file
COCO_WEIGHTS_PATH = os.path.join(ROOT_DIR, "mask_rcnn_coco.h5")

# Directory to save logs and model checkpoints, if not provided
# through the command line argument --logs
DEFAULT_LOGS_DIR = os.path.join(ROOT_DIR, "logs")

MAX_EPOCHS=200

ENABLE_AUGMENTATION=True

############################################################
#  Configurations
############################################################


class BalloonConfig(Config):
    """Configuration for training on the toy  dataset.
    Derives from the base Config class and overrides some values.
    """
    # Give the configuration a recognizable name
    NAME = "zuppa"

    # We use a GPU with 12GB memory, which can fit two images.
    # Adjust down if you use a smaller GPU.
    # IMAGES_PER_GPU = 1
    IMAGES_PER_GPU = 2

    # Number of classes (including background)
    NUM_CLASSES = 1 + 5  # Background + balloon

    # Number of training steps per epoch
    # STEPS_PER_EPOCH = 100
    STEPS_PER_EPOCH = 400

    # Skip detections with < 90% confidence
    DETECTION_MIN_CONFIDENCE = 0.9


############################################################
#  Dataset
############################################################

class BalloonDataset(utils.Dataset):

    def load_balloon(self, dataset_dir, subset):
        """Load a subset of the Balloon dataset.
        dataset_dir: Root directory of the dataset.
        subset: Subset to load: train or val
        """
        # Add classes. We have only one class to add.
        self.add_class("object", 1, "Sour")
        self.add_class("object", 2, "Tiger")
        self.add_class("object", 3, "Lychee")
        self.add_class("object", 4, "Tea")
        self.add_class("object", 5, "Milo")

        # Train or validation dataset?
        # Train or validation dataset?
        assert subset in ["train", "val"]
        dataset_dir = os.path.join(dataset_dir, subset)

        annotations = json.load(open(os.path.join(dataset_dir, "via_region_data.json")))
        annotations = list(annotations.values())  # don't need the dict keys

        # The VIA tool saves images in the JSON even if they don't have any
        # annotations. Skip unannotated images.
        annotations = [a for a in annotations if a['regions']]

        # Add images
        for a in annotations:
            # Get the x, y coordinaets of points of the polygons that make up
            # the outline of each object instance. There are stores in the
            # shape_attributes (see json format above)
            # for b in a['regions'].values():
            #    polygons = [{**b['shape_attributes'], **b['region_attributes']}]
            # print("string=", polygons)
            # for r in a['regions'].values():
            #    polygons = [r['shape_attributes']]
            #    # print("polygons=", polygons)
            #    multi_numbers = [r['region_attributes']]
                # print("multi_numbers=", multi_numbers)
            if type(a['regions']) is dict:
                polygons = [r['shape_attributes'] for r in a['regions'].values()]
            else:
                #print('sa')
                polygons = [r['shape_attributes'] for r in a['regions']]
            if type(a['regions']) is dict:
                objects = [s['region_attributes'] for s in a['regions'].values()]
                print('a')
                print(objects)
            else:
                #print('da')
                objects = [s['region_attributes'] for s in a['regions']]
                #print(objects)
            # print("multi_numbers=", multi_numbers)
            # num_ids = [n for n in multi_numbers['number'].values()]
            # for n in multi_numbers:
            #print(objects)
            num_ids=[]
            '''for n in objects:
                    #print(n)
                    #print(type(n))
                try:
                    if 'Sour' in n.keys():
                            num_ids.append(1)
                    elif 'Tiger' in n.keys():
                            num_ids.append(2)
                    elif 'Lychee' in n.keys():
                            num_ids.append(3)
                    elif 'Tea' in n.keys():
                            num_ids.append(4)
                    elif 'Milo' in n.keys():
                            num_ids.append(5)        
                except:
                    pass
            '''
            for n in objects:
                try:
                    print('b')
                    print(n['products'])
                    if n['products']=='Sour':
                            num_ids.append(1)
                    elif n['products']=='Tiger':
                            num_ids.append(2)
                    elif n['products']=='Lychee':
                            num_ids.append(3)
                    elif n['products']=='Tea':
                            num_ids.append(4)
                    elif n['products']=='Milo':
                            num_ids.append(5)        
                except:
                    pass
            #num_ids = [int(n['object']) for n in objects]
            # print("num_ids=", num_ids)
            # print("num_ids_new=", num_ids_new)
            # categories = [s['region_attributes'] for s in a['regions'].values()]
            # load_mask() needs the image size to convert polygons to masks.
            # Unfortunately, VIA doesn't include it in JSON, so we must read
            # the image. This is only managable since the dataset is tiny.
            image_path = os.path.join(dataset_dir, a['filename'])
            image = skimage.io.imread(image_path)
            height, width = image.shape[:2]
            print(num_ids)
            self.add_image(
                "object",
                image_id=a['filename'],  # use file name as a unique image id
                path=image_path,
                width=width, height=height,
                polygons=polygons,
                num_ids=num_ids)


    def load_mask(self, image_id):
        """Generate instance masks for an image.
       Returns:
        masks: A bool array of shape [height, width, instance count] with
            one mask per instance.
        class_ids: a 1D array of class IDs of the instance masks.
        """
        # If not a number dataset image, delegate to parent class.
        info = self.image_info[image_id]
        if info["source"] != "object":
            return super(self.__class__, self).load_mask(image_id)
        num_ids = info['num_ids']
        #print(num_ids)
        # Convert polygons to a bitmap mask of shape
        # [height, width, instance_count]
        mask = np.zeros([info["height"], info["width"], len(info["polygons"])],
                        dtype=np.uint8)

        for i, p in enumerate(info["polygons"]):
            # Get indexes of pixels inside the polygon and set them to 1
            rr, cc = skimage.draw.polygon(p['all_points_y'], p['all_points_x'])
            mask[rr, cc, i] = 1
        # print("info['num_ids']=", info['num_ids'])
        # Map class names to class IDs.
        num_ids = np.array(num_ids, dtype=np.int32)
        #print(num_ids)
        return mask, num_ids

    def image_reference(self, image_id):
        """Return the path of the image."""
        info = self.image_info[image_id]
        if info["source"] == "object":
            return info["path"]
        else:
            super(self.__class__, self).image_reference(image_id)


def train(model):
    """Train the model."""
    # Training dataset.
    dataset_train = BalloonDataset()
    dataset_train.load_balloon(args.dataset, "train")
    dataset_train.prepare()

    # Validation dataset
    dataset_val = BalloonDataset()
    dataset_val.load_balloon(args.dataset, "val")
    dataset_val.prepare()

    if(ENABLE_AUGMENTATION):
        # ref: https://github.com/matterport/Mask_RCNN/issues/1229#issuecomment-462735941
        # augmentation = iaa.Sequential([
        #     # iaa.Crop(px=(0, 16)), # crop images from each side by 0 to 16px (randomly chosen)
        #     iaa.Fliplr(0.5),  # horizontally flip 50% of the images
        # #     iaa.Dropout([0.05, 0.1]),
        #     # blur images with a sigma of 0 to 3.0
        # #     iaa.Affine(scale=(0.8, 1.2)),
        #     iaa.Affine(shear=(-16, 16)),
        #     iaa.GaussianBlur(sigma=(0, 1.0)),
        # #     iaa.GammaContrast([0.5, 1.55]),
        #     iaa.PiecewiseAffine(scale=(0.00, 0.02))
        # #     iaa.ElasticTransformation(alpha=(0, 5.0), sigma=0.25),
        # ])

    #     augmentation = iaa.Sequential([
    #     # iaa.Crop(px=(0, 16)), # crop images from each side by 0 to 16px (randomly chosen)
    #     iaa.Fliplr(0.5),  # horizontally flip 50% of the images
    # #     iaa.Dropout([0.05, 0.1]),
    #     # blur images with a sigma of 0 to 3.0
    #     iaa.Sometimes(0.5, iaa.Affine(scale=(0.9, 1.1))),
    #     iaa.Sometimes(0.5, iaa.Affine(shear=(-16, 16))),
    # #     iaa.GaussianBlur(sigma=(0, 1.0)),
    #     iaa.Sometimes(0.5, iaa.ContrastNormalization((0.7, 1.3))),
    #     iaa.Sometimes(0.5, iaa.PiecewiseAffine(scale=(0.00, 0.015))),
    #     iaa.Sometimes(0.5, iaa.ElasticTransformation(alpha=(0, 5.0), sigma=0.25))

        
        augmentation = iaa.Sequential([
        # iaa.Crop(px=(0, 16)), # crop images from each side by 0 to 16px (randomly chosen)
        iaa.Fliplr(0.5),  # horizontally flip 50% of the images
    #     iaa.Dropout([0.05, 0.1]),
        # blur images with a sigma of 0 to 3.0
        iaa.Sometimes(0.75, iaa.Affine(scale=(0.8, 1.2))),
        iaa.Sometimes(0.75, iaa.Affine(shear=(-18, 18))),
    #     iaa.GaussianBlur(sigma=(0, 1.0)),
        iaa.Sometimes(0.75, iaa.ContrastNormalization((0.6, 1.4))),
        iaa.Sometimes(0.75, iaa.PiecewiseAffine(scale=(0.00, 0.02))),
        iaa.Sometimes(0.75, iaa.ElasticTransformation(alpha=(0, 6.0), sigma=0.25))

    ])
    else:
        augmentation=None

    # *** This training schedule is an example. Update to your needs ***
    # Since we're using a very small dataset, and starting from
    # COCO trained weights, we don't need to train too long. Also,
    # no need to train all layers, just the heads should do it.
    print("Training network heads")
    model.train(dataset_train, dataset_val,
                learning_rate=config.LEARNING_RATE,
                epochs=MAX_EPOCHS,
                layers='heads', augmentation=augmentation)


def color_splash(image, mask):
    """Apply color splash effect.
    image: RGB image [height, width, 3]
    mask: instance segmentation mask [height, width, instance count]

    Returns result image.
    """
    # Make a grayscale copy of the image. The grayscale copy still
    # has 3 RGB channels, though.
    gray = skimage.color.gray2rgb(skimage.color.rgb2gray(image)) * 255
    # Copy color pixels from the original color image where mask is set
    if mask.shape[-1] > 0:
        # We're treating all instances as one, so collapse the mask into one layer
        mask = (np.sum(mask, -1, keepdims=True) >= 1)
        splash = np.where(mask, image, gray).astype(np.uint8)
    else:
        splash = gray.astype(np.uint8)
    return splash


def detect_and_color_splash(model, image_path=None, video_path=None):
    assert image_path or video_path

    # Image or video?
    if image_path:
        # Run model detection and generate the color splash effect
        print("Running on {}".format(args.image))
        # Read image
        image = skimage.io.imread(args.image)
        # Detect objects
        r = model.detect([image], verbose=1)[0]
        # Color splash
        splash = color_splash(image, r['masks'])
        # Save output
        file_name = "splash_{:%Y%m%dT%H%M%S}.png".format(datetime.datetime.now())
        skimage.io.imsave(file_name, splash)
    elif video_path:
        import cv2
        # Video capture
        vcapture = cv2.VideoCapture(video_path)
        width = int(vcapture.get(cv2.CAP_PROP_FRAME_WIDTH))
        height = int(vcapture.get(cv2.CAP_PROP_FRAME_HEIGHT))
        fps = vcapture.get(cv2.CAP_PROP_FPS)

        # Define codec and create video writer
        file_name = "splash_{:%Y%m%dT%H%M%S}.avi".format(datetime.datetime.now())
        vwriter = cv2.VideoWriter(file_name,
                                  cv2.VideoWriter_fourcc(*'MJPG'),
                                  fps, (width, height))

        count = 0
        success = True
        while success:
            print("frame: ", count)
            # Read next image
            success, image = vcapture.read()
            if success:
                # OpenCV returns images as BGR, convert to RGB
                image = image[..., ::-1]
                # Detect objects
                r = model.detect([image], verbose=0)[0]
                # Color splash
                splash = color_splash(image, r['masks'])
                # RGB -> BGR to save image to video
                splash = splash[..., ::-1]
                # Add image to video writer
                vwriter.write(splash)
                count += 1
        vwriter.release()
    print("Saved to ", file_name)


############################################################
#  Training
############################################################

if __name__ == '__main__':
    import argparse

    # Parse command line arguments
    parser = argparse.ArgumentParser(
        description='Train Mask R-CNN to detect balloons.')
    parser.add_argument("command",
                        metavar="<command>",
                        help="'train' or 'splash'")
    parser.add_argument('--dataset', required=False,
                        metavar="/path/to/balloon/dataset/",
                        help='Directory of the Balloon dataset')
    parser.add_argument('--weights', required=True,
                        metavar="/path/to/weights.h5",
                        help="Path to weights .h5 file or 'coco'")
    parser.add_argument('--logs', required=False,
                        default=DEFAULT_LOGS_DIR,
                        metavar="/path/to/logs/",
                        help='Logs and checkpoints directory (default=logs/)')
    parser.add_argument('--image', required=False,
                        metavar="path or URL to image",
                        help='Image to apply the color splash effect on')
    parser.add_argument('--video', required=False,
                        metavar="path or URL to video",
                        help='Video to apply the color splash effect on')
    args = parser.parse_args()

    # Validate arguments
    if args.command == "train":
        assert args.dataset, "Argument --dataset is required for training"
    elif args.command == "splash":
        assert args.image or args.video,\
               "Provide --image or --video to apply color splash"

    print("Weights: ", args.weights)
    print("Dataset: ", args.dataset)
    print("Logs: ", args.logs)

    # Configurations
    if args.command == "train":
        config = BalloonConfig()
    else:
        class InferenceConfig(BalloonConfig):
            # Set batch size to 1 since we'll be running inference on
            # one image at a time. Batch size = GPU_COUNT * IMAGES_PER_GPU
            GPU_COUNT = 1
            IMAGES_PER_GPU = 1
        config = InferenceConfig()
    config.display()

    # Create model
    if args.command == "train":
        model = modellib.MaskRCNN(mode="training", config=config,
                                  model_dir=args.logs)
    else:
        model = modellib.MaskRCNN(mode="inference", config=config,
                                  model_dir=args.logs)

    # Select weights file to load
    if args.weights.lower() == "coco":
        weights_path = COCO_WEIGHTS_PATH
        # Download weights file
        if not os.path.exists(weights_path):
            utils.download_trained_weights(weights_path)
    elif args.weights.lower() == "last":
        # Find last trained weights
        weights_path = model.find_last()
    elif args.weights.lower() == "imagenet":
        # Start from ImageNet trained weights
        weights_path = model.get_imagenet_weights()
    else:
        weights_path = args.weights

    # Load weights
    print("Loading weights ", weights_path)
    if args.weights.lower() == "coco":
        # Exclude the last layers because they require a matching
        # number of classes
        model.load_weights(weights_path, by_name=True, exclude=[
            "mrcnn_class_logits", "mrcnn_bbox_fc",
            "mrcnn_bbox", "mrcnn_mask"])
    else:
        model.load_weights(weights_path, by_name=True)

    # Train or evaluate
    if args.command == "train":
        train(model)
    elif args.command == "splash":
        detect_and_color_splash(model, image_path=args.image,
                                video_path=args.video)
    else:
        print("'{}' is not recognized. "
              "Use 'train' or 'splash'".format(args.command))
