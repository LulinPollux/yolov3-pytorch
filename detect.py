import argparse
import os
import tqdm

from torch.utils.data import DataLoader
from torch.autograd import Variable
import matplotlib.pyplot as plt
import matplotlib.patches as patches
from matplotlib.ticker import NullLocator

from model_new import *
from utils.utils import *
from utils.datasets import *
from utils.parse_config import *


parser = argparse.ArgumentParser()
parser.add_argument("--image_folder", type=str, default="../../data/voc_test", help="path to image folder")
parser.add_argument("--data_config", type=str, default="config/voc.data", help="path to data config file")
parser.add_argument("--pretrained_weights", type=str, default="weights/yolov3_voc.pth",
                    help="path to pretrained weights file")
parser.add_argument("--conf_thres", type=float, default=0.5, help="object confidence threshold")
parser.add_argument("--nms_thres", type=float, default=0.5, help="iou thresshold for non-maximum suppression")
parser.add_argument("--batch_size", type=int, default=16, help="size of the batches")
parser.add_argument("--n_cpu", type=int, default=8, help="number of cpu threads to use during batch generation")
parser.add_argument("--img_size", type=int, default=416, help="size of each image dimension")
parser.add_argument("--save_folder", type=str, default='../../detect', help='path to saving result folder')
args = parser.parse_args()
print(args)

device = torch.device("cuda" if torch.cuda.is_available() else "cpu")

data_config = parse_data_config(args.data_config)
classes = load_classes(data_config["names"])  # Extracts class labels from file

# Set up model
model = YOLOv3(args.img_size, int(data_config['classes'])).to(device)
if args.pretrained_weights.endswith('.pth'):
    model.load_state_dict(torch.load(args.pretrained_weights))
else:
    model.load_darknet_weights(args.pretrained_weights)

model.eval()  # Set in evaluation mode

dataloader = DataLoader(
    ImageFolder(args.image_folder, img_size=args.img_size),
    batch_size=args.batch_size,
    shuffle=False,
    num_workers=args.n_cpu,
)

Tensor = torch.cuda.FloatTensor if torch.cuda.is_available() else torch.FloatTensor

imgs = []  # Stores image paths
img_detections = []  # Stores detections for each image index

print("\nPerforming object detection:")
for batch_i, (img_paths, input_imgs) in enumerate(tqdm.tqdm(dataloader, desc='Batch')):
    # Configure input
    input_imgs = Variable(input_imgs.type(Tensor))

    # Get detections
    with torch.no_grad():
        detections = model(input_imgs)
        detections = non_max_suppression(detections, args.conf_thres, args.nms_thres)

    # Save image and detections
    imgs.extend(img_paths)
    img_detections.extend(detections)

# Bounding-box colors
cmap = plt.get_cmap("tab20b")
colors = [cmap(i) for i in np.linspace(0, 1, 20)]

os.makedirs(args.save_folder, exist_ok=True)

print("\nSaving images:")
# Iterate through images and save plot of detections
for img_i, (path, detections) in enumerate(zip(imgs, img_detections)):

    # Replace Windows path separator to Linux path separator
    path = path.replace('\\', '/')

    print("(%d) Image: '%s'" % (img_i, path))

    # Create plot
    img = np.array(Image.open(path))
    plt.figure()
    fig, ax = plt.subplots(1)
    ax.imshow(img)

    # Draw bounding boxes and labels of detections
    if detections is not None:
        # Rescale boxes to original image
        detections = rescale_boxes(detections, args.img_size, img.shape[:2])
        unique_labels = detections[:, -1].cpu().unique()
        n_cls_preds = len(unique_labels)
        bbox_colors = random.sample(colors, n_cls_preds)
        for x1, y1, x2, y2, conf, cls_conf, cls_pred in detections:
            print("\tLabel: %s, Conf: %.5f" % (classes[int(cls_pred)], cls_conf.item()))

            box_w = x2 - x1
            box_h = y2 - y1

            color = bbox_colors[int(np.where(unique_labels == int(cls_pred))[0])]
            # Create a Rectangle patch
            bbox = patches.Rectangle((x1, y1), box_w, box_h, linewidth=2, edgecolor=color, facecolor="none")
            # Add the bbox to the plot
            ax.add_patch(bbox)
            # Add label
            plt.text(x1, y1,
                     s=classes[int(cls_pred)],
                     color="white",
                     verticalalignment="top",
                     bbox={"color": color, "pad": 0})

    # Save generated image with detections
    plt.axis("off")
    plt.gca().xaxis.set_major_locator(NullLocator())
    plt.gca().yaxis.set_major_locator(NullLocator())
    filename = path.split("/")[-1].split(".")[0]
    plt.savefig("{}/{}.png".format(args.save_folder, filename), bbox_inches="tight", pad_inches=0.0)
    plt.close()
