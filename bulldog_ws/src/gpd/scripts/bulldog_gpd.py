#!/usr/bin/env python
import rospy
import numpy as np

from sensor_msgs.msg import Image
from sensor_msgs.msg import PointCloud2
from mask_rcnn_ros.srv import MaskDetect 
from gpd.srv import DetectGrasps
from gpd.srv import CloudTransform
from gpd.msg import CloudIndexed
from geometry_msgs.msg import Point
from std_msgs.msg import Int64

import moveit_commander
import geometry_msgs.msg


def cloud_transformation(srv, cloud):
	"""Transform point cloud into robot frame.

	Parameters
	----------
	- srv: str
		Name of the point cloud transform service.

	- cloud: sensor_msgs.msg.PointCloud2
		Point cloud in the local frame.

	Returns
	----------
	- cloud_transformed: sensor_msgs.msg.PointCloud2
		Point cloud in the robot frame.

	"""
	rospy.loginfo("Waiting for point cloud transform service...")
	rospy.wait_for_service(srv)
	rospy.loginfo("Point cloud transform service is available.")

	cloud_transform_response = None
	try:
		rospy.loginfo("Transforming point cloud...")
		cloud_transformer = rospy.ServiceProxy(srv, CloudTransform)
		cloud_transform_response = cloud_transformer(cloud)
	except rospy.ServiceException as e:
		rospy.logerr("Point cloud transform service call failed: %s" % e)
		raise SystemExit()
	cloud_transformed = cloud_transform_response.cloud_transformed
	
	return cloud_transformed


def mask_rcnn_detection(srv, image):
	"""Detection objects in a image by calling Mask RCNN.

	Parameters
	----------
	- srv: str
		Name of the Mask RCNN service.
	
	- image: sensor_msgs.msg.Image
		Image message acquired from the camera.

	Returns
	----------
	- detection: mask_rcnn_ros.msg.Detection
		Detection result of the image.

	"""
	rospy.loginfo("Waiting for Mask RCNN service...")
	rospy.wait_for_service(srv)
	rospy.loginfo("Mask RCNN service is available.")

	mask_rcnn_response = None
	try:
		rospy.loginfo("Mask RCNN Detecting...")
		mask_rcnn_detector = rospy.ServiceProxy(srv, MaskDetect)
		mask_rcnn_response = mask_rcnn_detector(image)
	except rospy.ServiceException as e:
		rospy.logerr("Mask RCNN service call failed: %s" % e)
		raise SystemExit()
	detection = mask_rcnn_response.detection

	return detection


def grasps_detection(srv, cloud_indexed):
	"""Find reasonable grasp candidates among all the samples.

	Parameters
	----------
	- srv:
		Name of the grasps detection service.

	- cloud_indexed: 

	Returns
	----------
	- grasp_configs: gpd.msg.GraspConfigList
		A list of grasp configurations each of which describes a grasp by its 
		6-DOF pose, consisting of a 3-DOF position and 3-DOF orientation, and 
		the opening width of the robot hand.

	"""
	rospy.loginfo("Waiting for grasp detection service...")
	rospy.wait_for_service(srv)
	rospy.loginfo("Grasp detection service is available.")

	detect_grasps_response = None
	try:
		rospy.loginfo("Generating grasp...")
		grasps_detector = rospy.ServiceProxy(srv, DetectGrasps)
		detect_grasps_response = grasps_detector(cloud_indexed)
	except rospy.ServiceException as e:
		rospy.logerr("Grasp detection service call failed: %s" % e)
		raise SystemExit()
	grasp_configs = detect_grasps_response.grasp_configs

	return grasp_configs


def process_cloud(cloud_transformed, detection):
	"""Process the transformed point cloud with respect to the Mask RCNN 
	detection.
	
	Parameters
	----------
	- cloud_transformed: sensor_msgs.msg.PointCloud2
		Point cloud in the robot frame.

	- detection: mask_rcnn_ros.msg.Detection
		Detection result of the image.

	Returns
	----------
	- cloud_indexed: gpd.msg.CloudIndexed
		The transformed point cloud and a list of indices into it at which to
		sample grasp candidates. 

	"""
	cloud_indexed = CloudIndexed()

	if len(detection.masks) > 0:
		for class_name, mask in zip(detection.class_names,
									detection.masks):
			if class_name == 'bottle':
				mask_data = np.fromstring(mask.data, dtype=np.uint8)
				one_index = np.nonzero(mask_data)[0]
				cloud_indexed.indices = [Int64(idx) for idx in one_index]
				break
		else:
			rospy.logfatal("No bottle found!")
			raise SystemExit()
	else:
		rospy.logfatal("Detect nothing!")
		raise SystemExit()

	cloud_indexed.cloud_sources.cloud = cloud_transformed
	cloud_indexed.cloud_sources.view_points.append(Point(0, 0, 0))
	cloud_indexed.cloud_sources.camera_source.append(Int64(0))

	return cloud_indexed


def main():
	"""Main entrance

	Parameters
	----------

	Returns
	----------

	"""
	rospy.init_node("gpd_mask")

	rospy.loginfo("Getting image...")
	image = rospy.wait_for_message("camera/rgb/image_raw", Image)
	cloud = rospy.wait_for_message("camera/depth/points", PointCloud2)

	# tf_buffer = tf2_ros.Buffer()
	# tf_listener = tf2_ros.TransformListener(tf_buffer)
	# trans = tf_buffer.lookup_transform(
	# 	"base_link", pc2.header.frame_id, rospy.Time(), rospy.Duration(2.0))
	# pc2_new = do_transform_cloud(pc2, trans)
	# try:
	# 	mask_srv = rospy.ServiceProxy("pc_transform_srv", pc_transform)
	# 	pc_transform_res = mask_srv(pc2)
	# except rospy.ServiceException, e:
	# 	rospy.loginfo "service call failed: %s"%e
	# rospy.loginfo("transformed pc")
	# pc2 = pc_transform_res.out_cloud

	cloud_transformed = cloud_transformation(
		"cloud_transform_server/transformation",
		cloud
	)
	
	detection = mask_rcnn_detection("mask_rcnn/detection", image)

	cloud_indexed = process_cloud(cloud_transformed, detection)

	grasp_configs = grasps_detection("detect_grasps_server/detect_grasps",
									 cloud_indexed)

	# get transform from camera to bask link
	# listener = tf.TransformListener()
	# listener.waitForTransform(
	# 	pc2.header.frame_id, "base_link", rospy.Time(), rospy.Duration(2.0))
	# (trans, rot) = listener.lookupTransform(
	# 	"base_link",
	# 	pc2.header.frame_id,
	# 	rospy.Time.now(),
	# 	rospy.Duration(2.0)
	# )

	# bottom_stamped = PointStamped()
	# bottom_stamped.header.frame_id = pc2.header.frame_id
	# bottom_stamped.header.stamp = rospy.Time(0)
	# bottom_stamped.point = gpd_response.grasp_configs.grasps[0].bottom
	# p = listener.transformPoint("base_link", bottom_stamped)

	group = None
	try:
		moveit_commander.RobotCommander()
		group = moveit_commander.MoveGroupCommander("left_arm")
	except moveit_commander.MoveItCommanderException as e:
		rospy.logerr("%s", e)
		raise SystemExit()

	pose_target = geometry_msgs.msg.Pose()
	pose_target.orientation.x = 0
	pose_target.orientation.y = 0
	pose_target.orientation.z = 0.6
	pose_target.orientation.w = 0.8

	pose_target.position = grasp_configs.grasps[0].bottom
	group.set_pose_target(pose_target)

	plan = group.plan()

	rospy.loginfo("============ Waiting while RVIZ displays motion planning...")


if __name__ == "__main__":
	main()
