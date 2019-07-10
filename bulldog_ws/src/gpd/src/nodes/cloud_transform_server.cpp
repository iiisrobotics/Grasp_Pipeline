//server node to transform pointcloud from focal frame to base link frame
#include <ros/ros.h>
#include <tf/tf.h>
#include <pcl_ros/transforms.h>

#include <gpd/CloudTransform.h>

class CloudTransformServer
{
private:
	tf::TransformListener listener_;

public:
	CloudTransformServer()
	{
	}

	bool transformCloud(gpd::CloudTransform::Request &req,
		gpd::CloudTransform::Response &res)
	{
		ROS_INFO("Point cloud received.");
	
		try{
			// tf::StampedTransform stampedTransformed;

			// listener_.waitForTransform(
			// 	"base_link", 
			// 	req.cloud_to_transform.header.frame_id, 
			// 	req.cloud_to_transform.header.stamp, 
			// 	ros::Duration(10.0)
			// );
			// listener_.lookupTransform(
			// 	"base_link", 
			// 	req.cloud_to_transform.header.frame_id, 
			// 	req.cloud_to_transform.header.stamp, 
			// 	stampedTransformed
			// );
			pcl_ros::transformPointCloud(
				"base_link",
				req.cloud_to_transform, 
				res.cloud_transformed,
				listener_
			);
			ROS_INFO("Point cloud transformation completed.");
		}
		catch(tf::TransformException &e){
			ROS_ERROR("%s", e.what());
			ros::Duration(1.0).sleep();
		}

		return true;
	}
};


int main(int argc, char **argv){
	ros::init(argc, argv, "cloud_transform_server");
	
	ros::NodeHandle node("~");
	
	CloudTransformServer cloud_transform_server;
	ros::ServiceServer service = node.advertiseService(
        "transformation", 
		&CloudTransformServer::transformCloud, 
		&cloud_transform_server
	);
	ROS_INFO("Ready to transform point cloud...");
	
	ros::spin();
	
	return 0;
}
