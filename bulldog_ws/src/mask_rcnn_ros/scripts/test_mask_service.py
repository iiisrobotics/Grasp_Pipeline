#!/usr/bin/env python

from __future__ import absolute_import
from __future__ import print_function
from __future__ import division

import rospy
from sensor_msgs.msg import Image
from sensor_msgs.msg import PointCloud2
from mask_rcnn_ros.srv import MaskDetect


def main():
	"""Main entrance

	Parameters
	----------

	Returns
	----------

	"""
	rospy.init_node("test_mask_service")

	if not rospy.is_shutdown():
		rospy.loginfo("Waiting for images...")
		image = rospy.wait_for_message('/cv_camera/image_raw', Image)
		# image = rospy.wait_for_message("/camera/rgb/image_raw", Image)
		# pc2 = rospy.wait_for_message("/camera/depth/points", PointCloud2)

		rospy.loginfo("Waiting for Mask RCNN service...")
		rospy.wait_for_service('mask_rcnn_srv')
		try:
			mask_rcnn_srv = rospy.ServiceProxy('mask_rcnn_srv', MaskDetect)
			response = mask_rcnn_srv(image)
			rospy.loginfo("Fininsh detecting!")
		except rospy.ServiceException as e:
			rospy.loginfo("Mask RCNN Service call failed: %s" % e)


if __name__ == '__main__':
	main()
