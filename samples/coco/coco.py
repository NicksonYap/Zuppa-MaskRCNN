"""
Mask R-CNN
Configurations and data loading code for MS COCO.

Copyright (c) 2017 Matterport, Inc.
Licensed under the MIT License (see LICENSE for details)
Written by Waleed Abdulla

------------------------------------------------------------

Usage: import the module (see Jupyter notebooks for examples), or run from
       the command line as such:

    # Train a new model starting from pre-trained COCO weights
    python3 coco.py train --dataset=/path/to/coco/ --model=coco

    # Train a new model starting from ImageNet weights. Also auto download COCO dataset
    python3 coco.py train --dataset=/path/to/coco/ --model=imagenet --download=True

    # Continue training a model that you had trained earlier
    python3 coco.py train --dataset=/path/to/coco/ --model=/path/to/weights.h5

    # Continue training the last model you trained
    python3 coco.py train --dataset=/path/to/coco/ --model=last

    # Run COCO evaluatoin on the last model you trained
    python3 coco.py evaluate --dataset=/path/to/coco/ --model=last
"""

import os
import sys
import time
import numpy as np
from imgaug import augmenters as iaa # https://github.com/aleju/imgaug (pip3 install imgaug)

# Download and install the Python COCO tools from https://github.com/waleedka/coco
# That's a fork from the original https://github.com/pdollar/coco with a bug
# fix for Python 3.
# I submitted a pull request https://github.com/cocodataset/cocoapi/pull/50
# If the PR is merged then use the original repo.
# Note: Edit PythonAPI/Makefile and replace "python" with "python3".
from pycocotools.coco import COCO
from pycocotools.cocoeval import COCOeval
from pycocotools import mask as maskUtils

import zipfile
import urllib.request
import shutil

# Root directory of the project
ROOT_DIR = os.path.abspath("../../")
MASK_RCNN_ROOT_DIR = os.path.abspath("../../../Mask_RCNN")

# Import Mask RCNN
sys.path.append(MASK_RCNN_ROOT_DIR)  # To find local version of the library
from mrcnn.config import Config
from mrcnn import model as modellib, utils

# Path to trained weights file
COCO_MODEL_PATH = os.path.join(ROOT_DIR, "mask_rcnn_coco.h5")

# Directory to save logs and model checkpoints, if not provided
# through the command line argument --logs
DEFAULT_LOGS_DIR = os.path.join(ROOT_DIR, "logs")

############################################################
#  Configurations
############################################################


class CocoConfig(Config):
    #ref: https://github.com/matterport/Mask_RCNN/wiki
    """Configuration for training on MS COCO.
    Derives from the base Config class and overrides values specific
    to the COCO dataset.
    """
    # Give the configuration a recognizable name
    NAME = "coco"

    # We use a GPU with 12GB memory, which can fit two images.
    # Adjust down if you use a smaller GPU.
    # IMAGES_PER_GPU = 2
    IMAGES_PER_GPU = 1

    # Uncomment to train on 8 GPUs (default is 1)
    # GPU_COUNT = 8

    # Number of classes (including background)
    # NUM_CLASSES = 1 + 80  # COCO has 80 classes
    # NUM_CLASSES = 1 + 5  # COCO has 5 classes
    NUM_CLASSES = None # need to manually set number of classes!

    MAX_GT_INSTANCES = 10 #maximum instances per image 

    # Number of training steps per epoch
    STEPS_PER_EPOCH = 1000 #default
    # STEPS_PER_EPOCH = 400er

    # RPN_NMS_THRESHOLD=0.7 #default
    RPN_NMS_THRESHOLD=0.95 #for training
    # DETECTION_NMS_THRESHOLD = 0.45 #for detection
    
    def __init__(self, NUM_CLASSES):
        self.NUM_CLASSES = NUM_CLASSES
        super().__init__()




############################################################
#  Dataset
############################################################

class CocoDataset(utils.Dataset):
    def load_coco(self, dataset_dir, subset, class_ids=None,
                  class_map=None, return_coco=False):
        """Load a subset of the COCO dataset.
        dataset_dir: The root directory of the COCO dataset.
        subset: What to load (train, val)
        class_ids: If provided, only loads images that have the given classes.
        class_map: TODO: Not implemented yet. Supports maping classes from
            different datasets to the same class ID.
        return_coco: If True, returns the COCO object.
        """

        # coco = COCO("{}/annotations/instances_{}.json".format(dataset_dir, subset))
        image_dir = "{}/{}".format(dataset_dir, subset)
        coco = COCO("{}/instances.json".format(image_dir))

        # Load all classes or a subset?
        if not class_ids:
            # All classes
            class_ids = sorted(coco.getCatIds())

        # All images or a subset?
        if class_ids:
            image_ids = []
            for id in class_ids:
                image_ids.extend(list(coco.getImgIds(catIds=[id])))
            # Remove duplicates
            image_ids = list(set(image_ids))
        else:
            # All images
            image_ids = list(coco.imgs.keys())

        # def getClassIdByClassName(class_name, default_class_id):
        #     class_name = class_name.lower()
        #     mapping = {
        #         "sour": 1,
        #         "tiger": 2,
        #         "lychee": 3,
        #         "flower": 4,
        #         "milo": 5,
        #     }
        #     return mapping.get(class_name, default_class_id)

        # Add classes
        for class_id in class_ids:
            class_name = coco.loadCats(class_id)[0]["name"]
            # print(class_id, class_name)
            # self.add_class("coco", class_id, class_name)
            # actual_class_id = getClassIdByClassName(class_name, class_id) # if enable mapping
            actual_class_id = class_id # if disable mapping
            print(actual_class_id, class_name)
            self.add_class("coco", actual_class_id, class_name)

        # Add images
        for i in image_ids:
            self.add_image(
                "coco", image_id=i,
                path=os.path.join(image_dir, coco.imgs[i]['file_name']),
                width=coco.imgs[i]["width"],
                height=coco.imgs[i]["height"],
                annotations=coco.loadAnns(coco.getAnnIds(
                    imgIds=[i], catIds=class_ids, iscrowd=None)))
        if return_coco:
            return coco

    def load_mask(self, image_id):
        """Load instance masks for the given image.

        Different datasets use different ways to store masks. This
        function converts the different mask format to one format
        in the form of a bitmap [height, width, instances].

        Returns:
        masks: A bool array of shape [height, width, instance count] with
            one mask per instance.
        class_ids: a 1D array of class IDs of the instance masks.
        """
        # If not a COCO image, delegate to parent class.
        image_info = self.image_info[image_id]
        if image_info["source"] != "coco":
            return super(CocoDataset, self).load_mask(image_id)

        instance_masks = []
        class_ids = []
        annotations = self.image_info[image_id]["annotations"]
        # Build mask of shape [height, width, instance_count] and list
        # of class IDs that correspond to each channel of the mask.
        for annotation in annotations:
            class_id = self.map_source_class_id(
                "coco.{}".format(annotation['category_id']))
            if class_id:
                m = self.annToMask(annotation, image_info["height"],
                                   image_info["width"])
                # Some objects are so small that they're less than 1 pixel area
                # and end up rounded out. Skip those objects.
                if m.max() < 1:
                    continue
                # Is it a crowd? If so, use a negative class ID.
                if annotation['iscrowd']:
                    # Use negative class ID for crowds
                    class_id *= -1
                    # For crowd masks, annToMask() sometimes returns a mask
                    # smaller than the given dimensions. If so, resize it.
                    if m.shape[0] != image_info["height"] or m.shape[1] != image_info["width"]:
                        m = np.ones([image_info["height"], image_info["width"]], dtype=bool)
                instance_masks.append(m)
                class_ids.append(class_id)

        # Pack instance masks into an array
        if class_ids:
            mask = np.stack(instance_masks, axis=2).astype(np.bool)
            class_ids = np.array(class_ids, dtype=np.int32)
            return mask, class_ids
        else:
            # Call super class to return an empty mask
            return super(CocoDataset, self).load_mask(image_id)

    def image_reference(self, image_id):
        """Return a link to the image in the COCO Website."""
        info = self.image_info[image_id]
        if info["source"] == "coco":
            return "http://cocodataset.org/#explore?id={}".format(info["id"])
        else:
            super(CocoDataset, self).image_reference(image_id)

    # The following two functions are from pycocotools with a few changes.

    def annToRLE(self, ann, height, width):
        """
        Convert annotation which can be polygons, uncompressed RLE to RLE.
        :return: binary mask (numpy 2D array)
        """
        segm = ann['segmentation']
        if isinstance(segm, list):
            # polygon -- a single object might consist of multiple parts
            # we merge all parts into one mask rle code
            rles = maskUtils.frPyObjects(segm, height, width)
            rle = maskUtils.merge(rles)
        elif isinstance(segm['counts'], list):
            # uncompressed RLE
            rle = maskUtils.frPyObjects(segm, height, width)
        else:
            # rle
            rle = ann['segmentation']
        return rle

    def annToMask(self, ann, height, width):
        """
        Convert annotation which can be polygons, uncompressed RLE, or RLE to binary mask.
        :return: binary mask (numpy 2D array)
        """
        rle = self.annToRLE(ann, height, width)
        m = maskUtils.decode(rle)
        return m


############################################################
#  COCO Evaluation
############################################################

def build_coco_results(dataset, image_ids, rois, class_ids, scores, masks):
    """Arrange resutls to match COCO specs in http://cocodataset.org/#format
    """
    # If no results, return an empty list
    if rois is None:
        return []

    results = []
    for image_id in image_ids:
        # Loop through detections
        for i in range(rois.shape[0]):
            class_id = class_ids[i]
            score = scores[i]
            bbox = np.around(rois[i], 1)
            mask = masks[:, :, i]

            result = {
                "image_id": image_id,
                "category_id": dataset.get_source_class_id(class_id, "coco"),
                "bbox": [bbox[1], bbox[0], bbox[3] - bbox[1], bbox[2] - bbox[0]],
                "score": score,
                "segmentation": maskUtils.encode(np.asfortranarray(mask))
            }
            results.append(result)
    return results


def evaluate_coco(model, dataset, coco, eval_type="bbox", limit=0, image_ids=None):
    """Runs official COCO evaluation.
    dataset: A Dataset object with valiadtion data
    eval_type: "bbox" or "segm" for bounding box or segmentation evaluation
    limit: if not 0, it's the number of images to use for evaluation
    """
    # Pick COCO images from the dataset
    image_ids = image_ids or dataset.image_ids

    # Limit to a subset
    if limit:
        image_ids = image_ids[:limit]

    # Get corresponding COCO image IDs.
    coco_image_ids = [dataset.image_info[id]["id"] for id in image_ids]

    t_prediction = 0
    t_start = time.time()

    results = []
    for i, image_id in enumerate(image_ids):
        # Load image
        image = dataset.load_image(image_id)

        # Run detection
        t = time.time()
        r = model.detect([image], verbose=0)[0]
        t_prediction += (time.time() - t)

        # Convert results to COCO format
        # Cast masks to uint8 because COCO tools errors out on bool
        image_results = build_coco_results(dataset, coco_image_ids[i:i + 1],
                                           r["rois"], r["class_ids"],
                                           r["scores"],
                                           r["masks"].astype(np.uint8))
        results.extend(image_results)

    # Load results. This modifies results with additional attributes.
    coco_results = coco.loadRes(results)

    # Evaluate
    cocoEval = COCOeval(coco, coco_results, eval_type)
    cocoEval.params.imgIds = coco_image_ids
    cocoEval.evaluate()
    cocoEval.accumulate()
    cocoEval.summarize()

    print("Prediction time: {}. Average {}/image".format(
        t_prediction, t_prediction / len(image_ids)))
    print("Total time: ", time.time() - t_start)


############################################################
#  Training
############################################################


if __name__ == '__main__':
    import argparse

    # Parse command line arguments
    parser = argparse.ArgumentParser(
        description='Train Mask R-CNN on MS COCO.')
    parser.add_argument("command",
                        metavar="<command>",
                        help="'train' or 'evaluate' on MS COCO")
    parser.add_argument('--dataset', required=True,
                        metavar="/path/to/coco/",
                        help='Directory of the MS-COCO dataset')
    parser.add_argument('--model', required=True,
                        metavar="/path/to/weights.h5",
                        help="Path to weights .h5 file or 'coco'")
    parser.add_argument('--logs', required=False,
                        default=DEFAULT_LOGS_DIR,
                        metavar="/path/to/logs/",
                        help='Logs and checkpoints directory (default=logs/)')
    parser.add_argument('--limit', required=False,
                        default=500,
                        metavar="<image count>",
                        help='Images to use for evaluation (default=500)')
    parser.add_argument('--download', required=False,
                        default=False,
                        metavar="<True|False>",
                        help='Automatically download and unzip MS-COCO files (default=False)',
                        type=bool)
    parser.add_argument('--no_run', help='Do not run training', action='store_true')
    parser.add_argument('--stage_1', help='Stage 1 (Training network heads)', action='store_true')
    parser.add_argument('--stage_2', help='Stage 2 (Fine tune Resnet stage 4 and up', action='store_true')
    parser.add_argument('--stage_3', help='Stage 3 (Fine tune all layers)', action='store_true')

    args = parser.parse_args()
    print("Command: ", args.command)
    print("Model: ", args.model)
    print("Dataset: ", args.dataset)
    print("Logs: ", args.logs)
    print("Auto Download: ", args.download)
    print("No Run: ", args.no_run)
    print("Stage 1: ", args.stage_1)
    print("Stage 2: ", args.stage_2)
    print("Stage 3: ", args.stage_3)

    #get number of classes from coco json file
    image_dir = "{}/{}".format(args.dataset, 'train')
    coco = COCO("{}/instances.json".format(image_dir))
    NUM_CLASSES = 1 + len(sorted(coco.getCatIds())) # background + classes
    
    # Configurations
    if args.command == "train":

        config = CocoConfig(NUM_CLASSES)
        
    else:
        class InferenceConfig(CocoConfig):
            # Set batch size to 1 since we'll be running inference on
            # one image at a time. Batch size = GPU_COUNT * IMAGES_PER_GPU
            GPU_COUNT = 1
            IMAGES_PER_GPU = 1
            DETECTION_MIN_CONFIDENCE = 0
        config = InferenceConfig(NUM_CLASSES)
    config.display()

    # Create model
    if args.command == "train":
        model = modellib.MaskRCNN(mode="training", config=config,
                                  model_dir=args.logs)
    else:
        model = modellib.MaskRCNN(mode="inference", config=config,
                                  model_dir=args.logs)

    # Select weights file to load
    if args.model.lower() == "coco":
        model_path = COCO_MODEL_PATH
    elif args.model.lower() == "last":
        # Find last trained weights
        model_path = model.find_last()
    elif args.model.lower() == "imagenet":
        # Start from ImageNet trained weights
        model_path = model.get_imagenet_weights()
    else:
        model_path = args.model

    # Load weights
    print("Loading weights ", model_path)

    # Exclude the last layers because they require a matching
    # number of classes
    model.load_weights(model_path, by_name=True, exclude=[
        "mrcnn_class_logits", "mrcnn_bbox_fc",
        "mrcnn_bbox", "mrcnn_mask"])

    # model.load_weights(model_path, by_name=True)

    # Train or evaluate
    if args.command == "train":
        # Training dataset. Use the training set and 35K from the
        # validation set, as as in the Mask RCNN paper.
        dataset_train = CocoDataset()
        dataset_train.load_coco(args.dataset, "train")
        dataset_train.prepare()

        # Validation dataset
        dataset_val = CocoDataset()
        dataset_val.load_coco(args.dataset, "val")
        dataset_val.prepare()


        if not args.no_run:
            # Image Augmentation
            # Right/Left flip 50% of the time
            # augmentation = iaa.Fliplr(0.5)
            
            # ref: https://github.com/matterport/Mask_RCNN/issues/1229#issuecomment-462735941
            augmentation = iaa.Sequential([
                iaa.Crop(px=(0, 20)), # crop images from each side by 0 to 16px (randomly chosen)
                iaa.Fliplr(0.5),  # horizontally flip 50% of the images
            #     iaa.Flipud(0.5), #vertically flip
                iaa.Affine(scale=(0.85, 1.1)),
                iaa.Multiply((0.85, 1.1)),
                
                iaa.Sometimes(0.5, iaa.GaussianBlur(sigma=(0, 1.0))),
                iaa.Sometimes(0.5, iaa.ShearX((-8, 8))),
                iaa.Sometimes(0.5, iaa.ShearY((-4, 4))),
                iaa.Sometimes(0.5, iaa.ContrastNormalization((0.9, 1.1))),
                iaa.Sometimes(0.5, iaa.PiecewiseAffine(scale=(0.005, 0.01255))),
                iaa.Sometimes(0.5, iaa.ElasticTransformation(alpha=(0, 1), sigma=0.05))
            ])

            # *** This training schedule is an example. Update to your needs ***

            # Training - Stage 1
            if args.stage_1:
                print("Training network heads")
                model.train(dataset_train, dataset_val,
                            learning_rate=config.LEARNING_RATE/2,
                            epochs=40*2,
                            layers='heads',
                            augmentation=augmentation)

            if args.stage_2:
                # Training - Stage 2

                # print("Fine tune Resnet stage 3 and up")
                # model.train(dataset_train, dataset_val,
                #             learning_rate=config.LEARNING_RATE/2,
                #             epochs=80*2,
                #             layers='3+',
                #             augmentation=augmentation)

                # Finetune layers from ResNet stage 4 and up
                print("Fine tune Resnet stage 4 and up")
                model.train(dataset_train, dataset_val,
                            learning_rate=config.LEARNING_RATE/2,
                            epochs=120*2,
                            layers='4+',
                            augmentation=augmentation)

            if args.stage_3:
                # Training - Stage 3

                # print("Fine tune Resnet stage 5 and up")
                # model.train(dataset_train, dataset_val,
                #             learning_rate=config.LEARNING_RATE/ 5 / 2,
                #             epochs=140*2,
                #             layers='5+',
                #             augmentation=augmentation)
                            
                # Fine tune all layers
                print("Fine tune all layers")
                model.train(dataset_train, dataset_val,
                            learning_rate=config.LEARNING_RATE / 10 / 2,
                            epochs=160*2,
                            layers='all',
                            augmentation=augmentation)

            # layers: Allows selecting wich layers to train. It can be:
            # - A regular expression to match layer names to train
            # - One of these predefined values:
            #   heads: The RPN, classifier and mask heads of the network
            #   all: All the layers
            #   3+: Train Resnet stage 3 and up
            #   4+: Train Resnet stage 4 and up
            #   5+: Train Resnet stage 5 and up

    elif args.command == "evaluate":
        # Validation dataset
        dataset_val = CocoDataset()
        coco = dataset_val.load_coco(args.dataset, "val", return_coco=True)
        dataset_val.prepare()
        if not args.no_run:
            print("Running COCO evaluation on {} images.".format(args.limit))
            evaluate_coco(model, dataset_val, coco, "bbox", limit=int(args.limit))
    else:
        print("'{}' is not recognized. "
              "Use 'train' or 'evaluate'".format(args.command))
