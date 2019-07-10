#!/usr/bin/env python

import rospy

from mask_rcnn_node import MaskRCNNNode


def main():
    """Main entrance.

    Parameters
    ----------

    Returns
    ----------

    """
    rospy.init_node('mask_rcnn')
    mask_rcnn_node = MaskRCNNNode()
    mask_rcnn_node.serve()


if __name__ == '__main__':
    main()
