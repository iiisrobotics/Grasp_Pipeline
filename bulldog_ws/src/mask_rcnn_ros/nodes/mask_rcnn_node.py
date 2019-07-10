from __future__ import absolute_import
from __future__ import print_function
from __future__ import division

import os
import threading
import numpy as np
import tensorflow as tf

import rospy
from cv_bridge import CvBridge
import sensor_msgs.msg
import mask_rcnn_ros.msg
import mask_rcnn_ros.srv

import coco
import utils
import model as modellib
import visualize
import matplotlib.pyplot as plt
from matplotlib.backends.backend_agg import FigureCanvasAgg
from matplotlib.figure import Figure

# Local path to trained weights file
ROS_HOME = os.environ.get('ROS_HOME', os.path.join(os.environ['HOME'], '.ros'))
COCO_MODEL_PATH = os.path.join(ROS_HOME, 'mask_rcnn_coco.h5')

# COCO Class names
# Index of the class in the list is its ID. For example, to get ID of
# the teddy bear class, use: CLASS_NAMES.index('teddy bear')
CLASS_NAMES = ['BG', 'person', 'bicycle', 'car', 'motorcycle', 'airplane',
               'bus', 'train', 'truck', 'boat', 'traffic light',
               'fire hydrant', 'stop sign', 'parking meter', 'bench', 'bird',
               'cat', 'dog', 'horse', 'sheep', 'cow', 'elephant', 'bear',
               'zebra', 'giraffe', 'backpack', 'umbrella', 'handbag', 'tie',
               'suitcase', 'frisbee', 'skis', 'snowboard', 'sports ball',
               'kite', 'baseball bat', 'baseball glove', 'skateboard',
               'surfboard', 'tennis racket', 'bottle', 'wine glass', 'cup',
               'fork', 'knife', 'spoon', 'bowl', 'banana', 'apple',
               'sandwich', 'orange', 'broccoli', 'carrot', 'hot dog', 'pizza',
               'donut', 'cake', 'chair', 'couch', 'potted plant', 'bed',
               'dining table', 'toilet', 'tv', 'laptop', 'mouse', 'remote',
               'keyboard', 'cell phone', 'microwave', 'oven', 'toaster',
               'sink', 'refrigerator', 'book', 'clock', 'vase', 'scissors',
               'teddy bear', 'hair drier', 'toothbrush']


class InferenceConfig(coco.CocoConfig):
    # Set batch size to 1 since we'll be running inference on
    # one image at a time. Batch size = GPU_COUNT * IMAGES_PER_GPU
    GPU_COUNT = 1
    IMAGES_PER_GPU = 1


class MaskRCNNNode:
    def __init__(self):
        """Initialize a MaskRCNNNode

        Parameters
        ----------

        Returns
        ----------
        - <obj>: MaskRCNNNode
            A Mask RCNN instantiation.

        """
        self._cv_bridge = CvBridge()
        self._class_names = rospy.get_param('~class_names', CLASS_NAMES)
        self._class_colors = visualize.random_colors(len(CLASS_NAMES))
        self._visualization = rospy.get_param('~visualization', True)
        self._topic_and_srv = rospy.get_param('~topic_and_srv', '~detection')

        #
        # network configuration
        #
        config = InferenceConfig()
        config.display()

        #
        # model in inference mode
        #
        self._model = modellib.MaskRCNN(mode="inference", model_dir="",
                                        config=config)

        #
        # mutual exclusive lock for handling image messages.
        #
        self._last_msg = None
        self._msg_lock = threading.Lock()

        #
        # publisher
        #
        self._detection_pub = rospy.Publisher(self._topic_and_srv,
                                              mask_rcnn_ros.msg.Detection,
                                              queue_size=1)
        self._vis_pub = rospy.Publisher('~visualization',
                                        sensor_msgs.msg.Image,
                                        queue_size=1)

        self._publish_rate = rospy.get_param('~publish_rate', 100)

        #
        # tensorflow graph
        #
        self._graph = tf.get_default_graph()

        #
        # Load weights trained on MS-COCO, download COCO trained weights from
        # releases if needed
        #
        model_path = rospy.get_param('~model_path', COCO_MODEL_PATH)
        if model_path == COCO_MODEL_PATH and not os.path.exists(
                COCO_MODEL_PATH):
            utils.download_trained_weights(COCO_MODEL_PATH)

        self._model.load_weights(model_path, by_name=True)

    def serve(self):
        """Start the service to server client requests.

        Parameters
        ----------

        Returns
        ----------

        """
        rospy.loginfo("Running as service...")
        rospy.Service(self._topic_and_srv,
                      mask_rcnn_ros.srv.MaskDetect,
                      self._srv_callback)
        rospy.loginfo("Mask RCNN service ready.")
        rospy.spin()

    def detecting(self):
        """Run the Mask RCNN algorithm to detect object from a image stream.

        Parameters
        ----------

        Returns
        ----------

        """
        rospy.loginfo("Detecting...")

        #
        # subscribe
        #
        rospy.Subscriber('~input', sensor_msgs.msg.Image,
                         self._topic_callback, queue_size=1)

        #
        # publish   
        #
        rate = rospy.Rate(self._publish_rate)
        while not rospy.is_shutdown():
            if self._msg_lock.acquire(False):
                msg = self._last_msg
                self._last_msg = None
                self._msg_lock.release()
            else:
                rate.sleep()
                continue
            if msg is not None:
                image = self._cv_bridge.imgmsg_to_cv2(msg, 'bgr8')

                #
                # detection
                #
                detections = self._model.detect([image], verbose=0)
                detection = detections[0]
                detection_msg = self._build_detection_msg(msg, detection)
                self._detection_pub.publish(detection_msg)

                #
                # visualization
                #
                if self._visualization:
                    cv_detection = self._visualize_cv(detection, image)
                    image_msg = self._cv_bridge.cv2_to_imgmsg(
                        cv_detection, 'bgr8')
                    self._vis_pub.publish(image_msg)
            rate.sleep()

    def detect(self, image_msg, verbose=False):
        """Run the Mask RCNN algorithm to detect object in a image.

        Parameters
        ----------
        - image_msg: sensor_msgs.msg.Image
            Raw image message transfer through specified topics.

        - verbose: bool (optional, default = False)
            Whether print model structure or not.

        Returns
        ----------
        - detection_msg: mask_rcnn_ros.msg.detection
            detection message for the detection.

        """
        rospy.loginfo("Detect...")

        #
        # detection
        #
        image = self._cv_bridge.imgmsg_to_cv2(image_msg, 'bgr8')
        with self._graph.as_default():
            detections = self._model.detect([image], verbose=verbose)
        detection = detections[0]
        detection_msg = self._build_detection_msg(image_msg, detection)

        #
        # visualization
        #
        if self._visualization:
            # plt_detection = self._visualize(detection, image)
            # self._display(plt_detection)
            cv_detection = self._visualize_cv(detection, image)
            image_msg = self._cv_bridge.cv2_to_imgmsg(cv_detection, 'bgr8')
            self._vis_pub.publish(image_msg)

        return detection_msg

    def _build_detection_msg(self, msg, detection):
        """Construct a detection message for the detection.

        Parameters
        ----------
        - msg: sensor_msgs.msg.Image
            Original image message.

        - detection: dict
            A single Mask RCNN detection.

        Returns
        ----------
        - detection_msg: mask_rcnn_ros.msg.detection
            The corresponding detection message of the detection.

        """
        detection_msg = mask_rcnn_ros.msg.Detection()
        detection_msg.header = msg.header
        for idx, (y1, x1, y2, x2) in enumerate(detection['rois']):
            box = sensor_msgs.msg.RegionOfInterest(
                x_offset=int(x1), y_offset=int(y1),
                height=int(y2 - y1), width=int(x2 - x1)
            )
            detection_msg.boxes.append(box)

            class_id = detection['class_ids'][idx]
            detection_msg.class_ids.append(class_id)

            class_name = self._class_names[class_id]
            detection_msg.class_names.append(class_name)

            score = detection['scores'][idx]
            detection_msg.scores.append(score)

            mask = sensor_msgs.msg.Image(
                header=msg.header,
                height=detection['masks'].shape[0],
                width=detection['masks'].shape[1],
                encoding='mono8',
                is_bigendian=False,
                step=detection['masks'].shape[1],
                data=(detection['masks'][:, :, idx] * 255).tobytes()
            )
            detection_msg.masks.append(mask)
        return detection_msg

    def _visualize(self, detection, image):
        """Generate a visual detection for a detection with matplotlib.

        Parameters
        ----------
        - detection: dict
            A single Mask RCNN detection

        - image: ndarray
            Original image.

        Returns
        ----------
        - vis_plt_detection:
            A visual detection.

        """
        fig = Figure()
        canvas = FigureCanvasAgg(fig)
        axes = fig.gca()
        visualize.display_instances(
            image, detection['rois'], detection['masks'],
            detection['class_ids'], CLASS_NAMES,
            detection['scores'], ax=axes, class_colors=self._class_colors
        )
        fig.tight_layout()
        canvas.draw()
        vis_plt_detection = np.fromstring(canvas.tostring_rgb(), dtype='uint8')

        _, _, w, h = fig.bbox.bounds
        vis_plt_detection = vis_plt_detection.reshape((int(h), int(w), 3))
        return vis_plt_detection

    def _visualize_cv(self, detection, image):
        """Generate a visual detection for a detection with OpenCV.

        Parameters
        ----------
        - detection: dict
            A single detection

        - image: ndarray
            Original image.

        Returns
        ----------
        - vis_cv_detection:
            A visual detection.

        """
        vis_cv_detection = visualize.display_instances_cv(
            image, detection['rois'], detection['masks'],
            detection['class_ids'], CLASS_NAMES,
            detection['scores'], class_colors=self._class_colors
        )

        return vis_cv_detection

    def _display(self, image, title=None):
        """Display image with matplotlib.

        Parameters
        ----------
        - detection: np.ndarray
            detection image.

        - title: str
            Title of the image.

        Returns
        ----------

        """
        title = title if title is not None else "Mask RCNN detection"

        fig, ax = plt.subplots(nrows=1, ncols=1)
        ax.set_title(title)
        ax.set_axis_off()
        if len(image.shape) == 1:
            ax.imshow(image, cmap=plt.get_cmap('gray'))
        elif len(image.shape) == 3:
            ax.imshow(image)
        else:
            raise RuntimeError("Cannot display image with invalid shape.")
        plt.pause(0.01)

    def _topic_callback(self, msg):
        """Callback of the Mask RCNN subscriber

        Parameters
        ----------

        Returns
        ----------

        """
        rospy.loginfo("Get an image from subscriber.")
        if self._msg_lock.acquire(False):
            self._last_msg = msg
            self._msg_lock.release()

    def _srv_callback(self, request):
        """Callback of the Mask RCNN service

        Parameters
        ----------
        - request: mask_rcnn_ros.srv.MaskDetectRequest
            Request from a client.

        Returns
        ----------
        - response: mask_rcnn_ros.srv.MaskDetectResponse
            Response of the service.

        Notes
        ----------
        This callback function is called when the service receive a request,
        it will run in another thread rather than the one running service. You
        need to save the tensorflow graph in service thread and use the exact
        same graph to handle the request.

        """
        rospy.loginfo("Get an image from client.")
        detection_msg = self.detect(request.input_image)
        response = mask_rcnn_ros.srv.MaskDetectResponse(detection_msg)
        return response
