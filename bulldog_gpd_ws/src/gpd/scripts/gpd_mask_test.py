#!/usr/bin/env python
import rospy
from sensor_msgs.msg import Image
from sensor_msgs.msg import PointCloud2
import sensor_msgs.point_cloud2 as PC2
from mask_rcnn_ros.srv import MaskDetect
from gpd.srv import detect_grasps
from gpd.msg import CloudIndexed
from gpd.msg import GraspConfigList
from geometry_msgs.msg import Point
from std_msgs.msg import Int64
import IPython
import numpy as np
import math
if __name__ == "__main__":
	rospy.init_node("test_service")

	print("getting image...")
	image = rospy.wait_for_message("/kinect2/qhd/image_color", Image)
	pc2 = rospy.wait_for_message("/kinect2/qhd/points", PointCloud2)
        
        points = PC2.read_points(pc2,skip_nans=False)
        points = list(points)
        #print(type(points[0][3]))
        for i in range(len(points)):    
            points[i] = (0 if math.isnan(points[i][0]) else points[i][0],
                        0 if math.isnan(points[i][1]) else points[i][1],
                        0 if math.isnan(points[i][2]) else points[i][2],
                        0 if math.isnan(points[i][3]) else points[i][3])
        pc2 = PC2.create_cloud(pc2.header,pc2.fields,points)

        print("waiting for service...")
	rospy.wait_for_service("mask_rcnn_srv")
	try:
		mask_srv = rospy.ServiceProxy("mask_rcnn_srv", MaskDetect)
		response = mask_srv(image)
                print("Succ mask rcnn\n")
	except rospy.ServiceException, e:
		print "service call failed: %s"%e

	cloudindexed = CloudIndexed()
	if len(response.result.masks) > 0:
            print(response.result.class_names)
            for i in range(len(response.result.masks)):
                if(response.result.class_names[i] == "bottle"):
                    break
            print(i)
	    mask = response.result.masks[i]
	    for i in range(mask.step * mask.height):
		if mask.data[i] == '\xff':
		    cloudindexed.indices.append(Int64(i))

        cloudindexed.cloud_sources.cloud = pc2
	cloudindexed.cloud_sources.view_points.append(Point(0,0,0))
	cloudindexed.cloud_sources.camera_source.append(Int64(0))

	print("generating grasp...")
	rospy.wait_for_service("/detect_grasps_server/detect_grasps")
	detect_grasp = rospy.ServiceProxy("/detect_grasps_server/detect_grasps", detect_grasps)
	graspConfigList = detect_grasp(cloudindexed)
	IPython.embed()
